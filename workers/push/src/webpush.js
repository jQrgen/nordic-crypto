// Web Push (RFC 8291 aes128gcm + RFC 8292 VAPID) using Web Crypto only.
// No third-party push library. Nothing here reads or stores an IP address.

const te = new TextEncoder();

export function bytesToB64url(bytes) {
  let s = "";
  const u = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function b64urlToBytes(s) {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  const bin = atob(String(s).replace(/-/g, "+").replace(/_/g, "/") + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function concat(...parts) {
  const list = parts.map((p) => (p instanceof Uint8Array ? p : new Uint8Array(p)));
  const n = list.reduce((a, p) => a + p.length, 0);
  const out = new Uint8Array(n);
  let o = 0;
  for (const p of list) { out.set(p, o); o += p.length; }
  return out;
}

async function hmac(keyBytes, data) {
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, data));
}

async function hkdf(salt, ikm, info, length) {
  const prk = await hmac(salt, ikm);
  const okm = await hmac(prk, concat(info, new Uint8Array([1])));
  return okm.slice(0, length);
}

export async function importVapidPrivateKey(publicB64, privateB64) {
  const pub = b64urlToBytes(publicB64);
  if (pub.length !== 65 || pub[0] !== 0x04) throw new Error("VAPID public key must be the uncompressed P-256 point");
  const jwk = {
    kty: "EC",
    crv: "P-256",
    x: bytesToB64url(pub.slice(1, 33)),
    y: bytesToB64url(pub.slice(33, 65)),
    d: privateB64,
  };
  const privateKey = await crypto.subtle.importKey(
    "jwk", jwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"],
  );
  return privateKey;
}

export async function vapidJwt(privateKey, publicB64, origin, subject, nowSec) {
  const exp = (nowSec || Math.floor(Date.now() / 1000)) + 12 * 60 * 60;
  const header = bytesToB64url(te.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const payload = bytesToB64url(te.encode(JSON.stringify({ aud: origin, exp, sub: subject })));
  const signingInput = te.encode(`${header}.${payload}`);
  const sig = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, privateKey, signingInput));
  if (sig.length !== 64) throw new Error("unexpected ECDSA signature length");
  return `${header}.${payload}.${bytesToB64url(sig)}`;
}

// Encrypt `payload` (Uint8Array) for a browser push subscription.
// userPublic is the raw uncompressed P-256 key (65 bytes), userAuth is the 16-byte auth secret.
export async function encryptPayload(userPublic, userAuth, payload) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const local = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const uaKey = await crypto.subtle.importKey("raw", userPublic, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: uaKey }, local.privateKey, 256));
  const localPub = new Uint8Array(await crypto.subtle.exportKey("raw", local.publicKey));
  const keyInfo = concat(te.encode("WebPush: info\0"), userPublic, localPub);
  const ikm = await hkdf(userAuth, shared, keyInfo, 32);
  const cek = await hkdf(salt, ikm, te.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(salt, ikm, te.encode("Content-Encoding: nonce\0"), 12);
  const recordSize = 4096;
  const padded = concat(payload, new Uint8Array([2]));
  if (padded.length + 16 > recordSize) throw new Error("push payload too large");
  const aes = await crypto.subtle.importKey("raw", cek, { name: "AES-GCM" }, false, ["encrypt"]);
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, aes, padded));
  const rs = new Uint8Array(4);
  new DataView(rs.buffer).setUint32(0, recordSize);
  return concat(salt, rs, new Uint8Array([localPub.length]), localPub, ciphertext);
}

export async function sendWebPush(subscription, payloadBytes, env) {
  const endpoint = subscription.endpoint;
  const origin = new URL(endpoint).origin;
  const userPublic = b64urlToBytes(subscription.keys.p256dh);
  const userAuth = b64urlToBytes(subscription.keys.auth);
  const privateKey = await importVapidPrivateKey(env.VAPID_PUBLIC_KEY, env.VAPID_PRIVATE_KEY);
  const jwt = await vapidJwt(privateKey, env.VAPID_PUBLIC_KEY, origin, env.VAPID_SUBJECT, Math.floor(Date.now() / 1000));
  const body = await encryptPayload(userPublic, userAuth, payloadBytes);
  const res = await fetch(endpoint, {
    method: "POST",
    headers: {
      Authorization: `vapid t=${jwt}, k=${env.VAPID_PUBLIC_KEY}`,
      "Content-Encoding": "aes128gcm",
      "Content-Type": "application/octet-stream",
      TTL: "86400",
      Urgency: "normal",
      // One topic so a push service can replace a notification that was not delivered yet.
      Topic: "nordic-crypto",
    },
    body,
  });
  return res;
}
