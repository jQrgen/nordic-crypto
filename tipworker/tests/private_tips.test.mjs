// node --test tests/private_tips.test.mjs — private tip inbox: validation, Turnstile, honeypot, rate limit, privacy,
// bearer read API and webhook. Uses node:sqlite as D1. No network, no secrets, nothing deployed.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import worker from "../src/worker.js";
import { validatePrivateTip, pageOk, goodUrl, PLIMITS } from "../src/private_tips.js";

const IP = "203.0.113.77";
const ORIGIN = "https://nordiccrypto.no";
const READ = "test-read-token-123";
const ORIGINS = new Set([ORIGIN, "https://jqrgen.github.io"]);

class SqliteD1 {
  constructor(db) { this.db = db; }
  prepare(sql) {
    const db = this.db;
    const bound = (...params) => ({
      run: async () => { const i = db.prepare(sql).run(...params); return { meta: { last_row_id: Number(i.lastInsertRowid), changes: i.changes } }; },
      first: async () => db.prepare(sql).get(...params) ?? null,
      all: async () => ({ results: db.prepare(sql).all(...params) }),
    });
    return { bind: (...params) => bound(...params), ...bound() };
  }
  async batch(stmts) { const out = []; for (const s of stmts) out.push(await s.run()); return out; }
}

function fresh() {
  const db = new DatabaseSync(":memory:");
  for (const m of ["0001_tips.sql", "0005_private_tips.sql"]) db.exec(readFileSync(new URL("../migrations/" + m, import.meta.url), "utf8"));
  return db;
}
const env = (db, over = {}) => ({ DB: new SqliteD1(db), TIP_TEST: "1", PRIVATE_TIPS_READ_TOKEN: READ, ...over });

async function call(db, path, { method = "GET", body, ip = IP, origin = ORIGIN, token, e, form } = {}) {
  const headers = {};
  if (origin) headers.origin = origin;
  if (ip) headers["cf-connecting-ip"] = ip;
  if (body !== undefined) headers["content-type"] = form ? "application/x-www-form-urlencoded" : "application/json";
  if (token) headers.authorization = "Bearer " + token;
  const payload = body === undefined ? undefined : form ? new URLSearchParams(body).toString() : JSON.stringify(body);
  const res = await worker.fetch(new Request("https://nordic-crypto-tips.nordiccrypto.workers.dev" + path, { method, headers, body: payload }), e || env(db));
  let j = null; try { j = await res.json(); } catch { /* empty */ }
  return { status: res.status, j, res };
}
const good = (over = {}) => ({ tip: "A regulator letter about a Norwegian exchange.", contact: "", language: "nb", page: "/nb/tip/",
  attachments: "https://example.no/a\nhttps://example.no/b", website: "", "cf-turnstile-response": "test-pass", ...over });

test("validation", () => {
  assert.equal(validatePrivateTip(good(), ORIGINS)[1], null);
  assert.equal(validatePrivateTip(good({ tip: "  " }), ORIGINS)[1], "empty_tip");
  assert.equal(validatePrivateTip(good({ tip: "x".repeat(PLIMITS.maxTip + 1) }), ORIGINS)[1], "tip_long");
  assert.equal(validatePrivateTip(good({ attachments: "ftp://x.no/a" }), ORIGINS)[1], "bad_attachment");
  assert.equal(validatePrivateTip(good({ attachments: Array(11).fill("https://a.no/") }), ORIGINS)[1], "bad_attachment");
  assert.equal(validatePrivateTip(good({ page: "/news/" }), ORIGINS)[1], "bad_page");
  assert.equal(validatePrivateTip(good({ language: "x1" }), ORIGINS)[1], "bad_language");
  assert.equal(validatePrivateTip(good({ contact: "c".repeat(501) }), ORIGINS)[1], "bad_contact");
  assert.equal(validatePrivateTip(good({ tip: 5 }), ORIGINS)[1], "bad_body");
  assert.ok(pageOk("https://nordiccrypto.no/sv/tip/", ORIGINS));
  assert.ok(pageOk("https://jqrgen.github.io/nordic-crypto/tip/", ORIGINS));
  assert.ok(!pageOk("https://evil.example/tip/", ORIGINS));
  assert.ok(!pageOk("https://nordiccrypto.no/tip/?x=1", ORIGINS));
  assert.ok(!goodUrl("https://user:pw@example.no/"));
});

test("stores a tip without the IP and lists it with the bearer token", async () => {
  const db = fresh();
  const r = await call(db, "/api/private-tip", { method: "POST", body: good() });
  assert.equal(r.status, 201); assert.equal(r.j.ok, true);
  assert.equal(r.res.headers.get("access-control-allow-origin"), ORIGIN);
  const blob = JSON.stringify(db.prepare("SELECT * FROM private_tips").all()) + JSON.stringify(db.prepare("SELECT * FROM rate_hits").all());
  assert.ok(!blob.includes(IP), "raw IP never stored");
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM tips").get().n, 0, "URL-tip table untouched");
  const l = await call(db, "/api/private-tips", { token: READ, origin: null });
  assert.equal(l.status, 200); assert.equal(l.j.tips.length, 1);
  assert.deepEqual(l.j.tips[0].attachments, ["https://example.no/a", "https://example.no/b"]);
  assert.equal(l.j.tips[0].contact, null);
  assert.equal(l.res.headers.get("access-control-allow-origin"), null, "read API has no CORS");
});

test("form-encoded body works", async () => {
  const r = await call(fresh(), "/api/private-tip", { method: "POST", body: good(), form: true });
  assert.equal(r.status, 201);
});

test("turnstile and honeypot", async () => {
  const db = fresh();
  assert.equal((await call(db, "/api/private-tip", { method: "POST", body: good({ "cf-turnstile-response": "nope" }) })).j.error, "turnstile");
  const off = await call(db, "/api/private-tip", { method: "POST", body: good(), e: { DB: new SqliteD1(db) } });
  assert.equal(off.status, 503, "no TURNSTILE_SECRET -> refuse, store nothing");
  const hp = await call(db, "/api/private-tip", { method: "POST", body: good({ website: "spam" }) });
  assert.equal(hp.status, 200);
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM private_tips").get().n, 0);
});

test("origin and rate limit", async () => {
  const db = fresh();
  assert.equal((await call(db, "/api/private-tip", { method: "POST", body: good(), origin: "https://evil.example" })).status, 403);
  for (let i = 0; i < 5; i++) assert.equal((await call(db, "/api/private-tip", { method: "POST", body: good() })).status, 201);
  assert.equal((await call(db, "/api/private-tip", { method: "POST", body: good() })).status, 429);
});

test("read API auth and marking", async () => {
  const db = fresh();
  await call(db, "/api/private-tip", { method: "POST", body: good() });
  assert.equal((await call(db, "/api/private-tips", { token: "wrong" })).status, 401);
  assert.equal((await call(db, "/api/private-tips", { token: READ, e: { DB: new SqliteD1(db) } })).status, 503);
  const m = await call(db, "/api/private-tips/1", { method: "POST", token: READ, body: { status: "handled", editor_notes: "checked" } });
  assert.equal(m.status, 200); assert.equal(m.j.tip.status, "handled");
  assert.equal((await call(db, "/api/private-tips/1", { method: "POST", token: READ, body: { status: "bogus" } })).status, 400);
  assert.equal((await call(db, "/api/private-tips/99", { method: "POST", token: READ, body: { status: "read" } })).status, 404);
  assert.equal((await call(db, "/api/private-tips?status=new", { token: READ })).j.tips.length, 0);
});

test("webhook gets the stored tip", async () => {
  const db = fresh();
  const seen = [];
  const real = globalThis.fetch;
  globalThis.fetch = async (url, init) => { seen.push({ url: String(url), init }); return new Response("{}"); };
  try {
    const r = await call(db, "/api/private-tip", { method: "POST", body: good(),
      e: env(db, { TIP_WEBHOOK_URL: "https://hooks.example/tip", TIP_WEBHOOK_BEARER: "hb" }) });
    assert.equal(r.status, 201);
  } finally { globalThis.fetch = real; }
  assert.equal(seen.length, 1);
  assert.equal(seen[0].init.headers.Authorization, "Bearer hb");
  assert.equal(JSON.parse(seen[0].init.body).tip.language, "nb");
});

test("onion forwarder: bearer skips Turnstile, shared rate key, onion page", async () => {
  const db = fresh();
  const e = env(db, { TIP_TEST: "0", ONION_INGEST_TOKEN: "onion-secret-1" });
  const onionPage = "http://" + "a".repeat(56) + ".onion/sv/";
  const body = good({ "cf-turnstile-response": "", page: onionPage });
  const ok = await call(db, "/api/private-tip", { method: "POST", body, origin: null, token: "onion-secret-1", e });
  assert.equal(ok.status, 201);
  assert.equal(db.prepare("SELECT page FROM private_tips").get().page, onionPage);
  const wrong = await call(db, "/api/private-tip", { method: "POST", body, origin: null, token: "nope", e });
  assert.equal(wrong.status, 400, "without the bearer the onion page is not a valid page");
  const same = env(db, { TIP_TEST: "0", ONION_INGEST_TOKEN: READ });
  assert.equal((await call(db, "/api/private-tip", { method: "POST", body, origin: null, token: READ, e: same })).status, 400,
    "ingest token equal to the read token is refused");
  assert.ok(pageOk("/da/", ORIGINS, true)); assert.ok(!pageOk("/da/", ORIGINS));
  assert.ok(!pageOk("https://" + "a".repeat(56) + ".onion/", ORIGINS, true));
});
