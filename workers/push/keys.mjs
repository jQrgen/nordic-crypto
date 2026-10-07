// Print a fresh VAPID key pair and a publish token to stdout.
// Do not redirect this into a file inside the repo. Paste the values into
// `wrangler secret put` and into the publish host's environment. See README.md.
function bytesToB64url(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function b64urlToBytes(s) {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  const bin = atob(String(s).replace(/-/g, "+").replace(/_/g, "/") + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign"]);
const pubJwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
const privJwk = await crypto.subtle.exportKey("jwk", pair.privateKey);
const x = b64urlToBytes(pubJwk.x);
const y = b64urlToBytes(pubJwk.y);
const pub = new Uint8Array(65);
pub[0] = 4;
pub.set(x, 1);
pub.set(y, 33);
const token = crypto.getRandomValues(new Uint8Array(32));
process.stdout.write(
  "VAPID_PUBLIC_KEY=" + bytesToB64url(pub) + "\n" +
  "VAPID_PRIVATE_KEY=" + privJwk.d + "\n" +
  "PUBLISH_TOKEN=" + bytesToB64url(token) + "\n",
);
