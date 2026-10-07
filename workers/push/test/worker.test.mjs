// Local tests: subscription storage, one notification per publish, country filter,
// feed JSON, and a Web Push encrypt/decrypt round trip. No network.
import assert from "node:assert/strict";
import { test } from "node:test";
import worker, { feedDocument, notificationFor, storiesFor, originAllowed } from "../src/worker.js";
import { b64urlToBytes, bytesToB64url, encryptPayload, vapidJwt, importVapidPrivateKey } from "../src/webpush.js";

class MemKV {
  constructor() { this.map = new Map(); }
  async get(k) { return this.map.has(k) ? this.map.get(k) : null; }
  async put(k, v) { this.map.set(k, String(v)); }
  async delete(k) { this.map.delete(k); }
  async list({ prefix }) {
    const keys = [...this.map.keys()].filter((k) => k.startsWith(prefix || "")).sort();
    return { keys: keys.map((name) => ({ name })), list_complete: true };
  }
}

function env(over) {
  return {
    SUBSCRIPTIONS: new MemKV(),
    VAPID_PUBLIC_KEY: "B" + "A".repeat(86),
    VAPID_PRIVATE_KEY: "priv",
    VAPID_SUBJECT: "mailto:push@cryptonordic.no",
    PUBLISH_TOKEN: "test-token",
    ...over,
  };
}

function req(path, { method = "GET", origin = "https://cryptonordic.no", body, token } = {}) {
  const headers = { origin };
  if (body !== undefined) headers["content-type"] = "application/json";
  if (token) headers.authorization = "Bearer " + token;
  return new Request("https://push.example" + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

const SUB = {
  endpoint: "https://push.example/subscription/abc",
  keys: { p256dh: "A".repeat(87), auth: "B".repeat(22) },
  lang: "nn",
  countries: ["NO"],
};

test("origin allow list", () => {
  assert.equal(originAllowed("https://cryptonordic.no"), true);
  assert.equal(originAllowed("https://jqrgen.github.io"), true);
  assert.equal(originAllowed("http://127.0.0.1:8765"), true);
  assert.equal(originAllowed("https://evil.example"), false);
  assert.equal(originAllowed(""), false);
});

test("subscribe stores only the subscription", async () => {
  const e = env();
  const res = await worker.fetch(req("/api/push/subscribe", { method: "POST", body: SUB }), e);
  assert.equal(res.status, 200);
  const keys = [...e.SUBSCRIPTIONS.map.keys()];
  assert.equal(keys.length, 1);
  assert.ok(keys[0].startsWith("sub:"));
  const stored = JSON.parse(e.SUBSCRIPTIONS.map.get(keys[0]));
  assert.deepEqual(Object.keys(stored).sort(), ["countries", "endpoint", "keys", "lang", "updated_at"]);
  assert.equal(stored.endpoint, SUB.endpoint);
  assert.deepEqual(stored.keys, SUB.keys);
  assert.equal(stored.lang, "nn");
  assert.deepEqual(stored.countries, ["NO"]);
  assert.equal(JSON.stringify(stored).includes("203.0.113"), false);
});

test("subscribe rejects a missing origin and a bad key", async () => {
  const e = env();
  const noOrigin = new Request("https://push.example/api/push/subscribe", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(SUB),
  });
  assert.equal((await worker.fetch(noOrigin, e)).status, 403);
  const bad = await worker.fetch(req("/api/push/subscribe", {
    method: "POST",
    body: { ...SUB, keys: { p256dh: "short", auth: SUB.keys.auth } },
  }), e);
  assert.equal(bad.status, 400);
  assert.equal(e.SUBSCRIPTIONS.map.size, 0);
});

test("unsubscribe deletes the row and is safe to repeat", async () => {
  const e = env();
  await worker.fetch(req("/api/push/subscribe", { method: "POST", body: SUB }), e);
  const off = await worker.fetch(req("/api/push/unsubscribe", { method: "POST", body: { endpoint: SUB.endpoint } }), e);
  assert.equal(off.status, 200);
  assert.equal(e.SUBSCRIPTIONS.map.size, 0);
  const again = await worker.fetch(req("/api/push/unsubscribe", { method: "POST", body: { endpoint: SUB.endpoint } }), e);
  assert.equal(again.status, 200);
});

test("country filter and one batched notification", () => {
  const stories = [
    { title: "Oslo", url: "https://cryptonordic.no/a", country: "NO", summaries: { en: "A", nn: "Aa" }, titles: { en: "Oslo" } },
    { title: "Stockholm", url: "https://cryptonordic.no/b", country: "SE", summaries: { en: "B" }, titles: { en: "Stockholm" } },
  ];
  assert.equal(storiesFor({ countries: ["NO"] }, stories).length, 1);
  assert.equal(storiesFor({ countries: [] }, stories).length, 2);
  const one = notificationFor(storiesFor({ countries: ["NO"] }, stories), "nn");
  assert.equal(one.title, "Oslo");
  assert.equal(one.body, "Aa");
  const many = notificationFor(stories, "en");
  assert.equal(many.title, "2 new stories");
  assert.match(many.body, /Oslo/);
  assert.match(many.body, /Stockholm/);
  assert.equal(many.url, "https://cryptonordic.no/");
  assert.equal(many.tag, "nordic-crypto-latest");
});

test("publish requires the token and sends one push per matching subscription", async () => {
  const calls = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    return new Response(null, { status: 201 });
  };
  try {
    const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign"]);
    const pubJwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
    const privJwk = await crypto.subtle.exportKey("jwk", pair.privateKey);
    const x = b64urlToBytes(pubJwk.x);
    const y = b64urlToBytes(pubJwk.y);
    const pub = new Uint8Array(65);
    pub[0] = 4; pub.set(x, 1); pub.set(y, 33);
    const ua = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
    const uaPub = new Uint8Array(await crypto.subtle.exportKey("raw", ua.publicKey));
    const auth = crypto.getRandomValues(new Uint8Array(16));
    const e = env({
      VAPID_PUBLIC_KEY: bytesToB64url(pub),
      VAPID_PRIVATE_KEY: privJwk.d,
    });
    const sub = {
      endpoint: "https://fcm.googleapis.com/fcm/send/abc",
      keys: { p256dh: bytesToB64url(uaPub), auth: bytesToB64url(auth) },
      lang: "en",
      countries: ["SE"],
    };
    const other = {
      endpoint: "https://fcm.googleapis.com/fcm/send/other",
      keys: { p256dh: bytesToB64url(uaPub), auth: bytesToB64url(auth) },
      lang: "sv",
      countries: ["DK"],
    };
    await worker.fetch(req("/api/push/subscribe", { method: "POST", body: sub }), e);
    await worker.fetch(req("/api/push/subscribe", { method: "POST", body: other }), e);
    const denied = await worker.fetch(req("/api/push/publish", {
      method: "POST", origin: null, token: "nope",
      body: { stories: [{ title: "T", summary: "S", url: "https://cryptonordic.no/x", country: "SE" }] },
    }), e);
    assert.equal(denied.status, 401);
    const res = await worker.fetch(req("/api/push/publish", {
      method: "POST",
      token: "test-token",
      body: {
        stories: [
          { title: "Stockholm story", summary: "Short.", url: "https://example.se/a", country: "SE", titles: { en: "Stockholm story" }, summaries: { en: "Short.", sv: "Kort." } },
          { title: "Oslo story", summary: "Also.", url: "https://example.no/b", country: "NO" },
        ],
      },
    }), e);
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.equal(body.ok, true);
    assert.equal(body.stories, 2);
    assert.equal(body.sent, 1);
    assert.equal(body.skipped, 1);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].init.headers.Topic, "nordic-crypto");
    assert.match(calls[0].init.headers.Authorization, /^vapid t=/);
    const feed = await (await worker.fetch(req("/api/push/feed.json"), e)).json();
    assert.equal(feed.apns, "not implemented");
    assert.equal(feed.batches.length, 1);
    assert.equal(feed.batches[0].stories.length, 2);
    assert.equal(JSON.stringify(feed).includes("fcm.googleapis.com"), false);
  } finally {
    globalThis.fetch = realFetch;
  }
});

test("gone subscription is deleted", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(null, { status: 410 });
  try {
    const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign"]);
    const pubJwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
    const privJwk = await crypto.subtle.exportKey("jwk", pair.privateKey);
    const x = b64urlToBytes(pubJwk.x);
    const y = b64urlToBytes(pubJwk.y);
    const pub = new Uint8Array(65);
    pub[0] = 4; pub.set(x, 1); pub.set(y, 33);
    const ua = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
    const uaPub = new Uint8Array(await crypto.subtle.exportKey("raw", ua.publicKey));
    const auth = crypto.getRandomValues(new Uint8Array(16));
    const e = env({ VAPID_PUBLIC_KEY: bytesToB64url(pub), VAPID_PRIVATE_KEY: privJwk.d });
    await worker.fetch(req("/api/push/subscribe", {
      method: "POST",
      body: {
        endpoint: "https://updates.push.services.mozilla.com/wpush/v2/abc",
        keys: { p256dh: bytesToB64url(uaPub), auth: bytesToB64url(auth) },
        lang: "en",
        countries: [],
      },
    }), e);
    const res = await worker.fetch(req("/api/push/publish", {
      method: "POST",
      token: "test-token",
      body: { stories: [{ title: "One", summary: "S", url: "https://cryptonordic.no/z", country: "IS" }] },
    }), e);
    const body = await res.json();
    assert.equal(body.removed, 1);
    assert.equal([...e.SUBSCRIPTIONS.map.keys()].filter((k) => k.startsWith("sub:")).length, 0);
  } finally {
    globalThis.fetch = realFetch;
  }
});

test("aes128gcm round trip", async () => {
  const ua = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const uaPub = new Uint8Array(await crypto.subtle.exportKey("raw", ua.publicKey));
  const auth = crypto.getRandomValues(new Uint8Array(16));
  const payload = new TextEncoder().encode(JSON.stringify({ title: "Hello", body: "There" }));
  const body = await encryptPayload(uaPub, auth, payload);
  const salt = body.slice(0, 16);
  const rs = new DataView(body.buffer, body.byteOffset + 16, 4).getUint32(0);
  assert.equal(rs, 4096);
  const idlen = body[20];
  const asPub = body.slice(21, 21 + idlen);
  const ciphertext = body.slice(21 + idlen);
  const asKey = await crypto.subtle.importKey("raw", asPub, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: asKey }, ua.privateKey, 256));
  async function hmac(keyBytes, data) {
    const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    return new Uint8Array(await crypto.subtle.sign("HMAC", key, data));
  }
  async function hkdf(saltBytes, ikm, info, length) {
    const prk = await hmac(saltBytes, ikm);
    const okm = await hmac(prk, concat(info, new Uint8Array([1])));
    return okm.slice(0, length);
  }
  function concat(...parts) {
    const n = parts.reduce((a, p) => a + p.length, 0);
    const out = new Uint8Array(n);
    let o = 0;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  }
  const te = new TextEncoder();
  const keyInfo = concat(te.encode("WebPush: info\0"), uaPub, asPub);
  const ikm = await hkdf(auth, shared, keyInfo, 32);
  const cek = await hkdf(salt, ikm, te.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(salt, ikm, te.encode("Content-Encoding: nonce\0"), 12);
  const aes = await crypto.subtle.importKey("raw", cek, { name: "AES-GCM" }, false, ["decrypt"]);
  const plain = new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce }, aes, ciphertext));
  assert.equal(plain[plain.length - 1], 2);
  const text = new TextDecoder().decode(plain.slice(0, -1));
  assert.equal(JSON.parse(text).title, "Hello");
});

test("vapid jwt audience is the push service origin", async () => {
  const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign"]);
  const pubJwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  const privJwk = await crypto.subtle.exportKey("jwk", pair.privateKey);
  const x = b64urlToBytes(pubJwk.x);
  const y = b64urlToBytes(pubJwk.y);
  const pub = new Uint8Array(65);
  pub[0] = 4; pub.set(x, 1); pub.set(y, 33);
  const publicB64 = bytesToB64url(pub);
  const key = await importVapidPrivateKey(publicB64, privJwk.d);
  const jwt = await vapidJwt(key, publicB64, "https://fcm.googleapis.com", "mailto:push@cryptonordic.no", 1_700_000_000);
  const payload = JSON.parse(new TextDecoder().decode(b64urlToBytes(jwt.split(".")[1])));
  assert.equal(payload.aud, "https://fcm.googleapis.com");
  assert.equal(payload.sub, "mailto:push@cryptonordic.no");
  assert.equal(payload.exp, 1_700_000_000 + 12 * 60 * 60);
});

test("feed document names APNs as out of scope", () => {
  const doc = feedDocument([]);
  assert.equal(doc.apns, "not implemented");
  assert.match(doc.note, /APNs/);
  assert.match(doc.privacy, /subscriptions are not included/);
});
