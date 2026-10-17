// node --test tests/private_tips.test.mjs — columnist applications: validation, Turnstile, honeypot, rate limit,
// bearer read API and webhook. Uses node:sqlite as D1. No network, no secrets, nothing deployed.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import worker from "../src/worker.js";
import { validateColumnist } from "../src/columnist.js";
import { TEST_OUTBOX } from "../src/mailer.js";

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
  for (const m of ["0001_tips.sql", "0005_private_tips.sql", "0006_columnist.sql"]) db.exec(readFileSync(new URL("../migrations/" + m, import.meta.url), "utf8"));
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
const good = { name: "Kari", email: "kari@example.no", languages: "nynorsk, English", pitch: "Bitcoin mining in Norway", sample: "https://example.no/a", why: "Nordic angle", language: "nn", "cf-turnstile-response": "test-pass" };
const cenv = (db, over = {}) => env(db, { SUBSCRIBE_TEST: "1", COLUMNIST_TO: "editor@example.no", MAIL_FROM_NORDIC_CRYPTO: "NC <news@example.no>", ...over });

test("valid application is stored privately and forwarded with Reply-To", async () => {
  const db = fresh(); TEST_OUTBOX.length = 0;
  const r = await call(db, "/api/columnist", { method: "POST", body: good, e: cenv(db) });
  assert.equal(r.status, 201); assert.equal(r.j.ok, true); assert.equal(r.j.id, undefined);
  const row = db.prepare("SELECT * FROM columnist_applications").get();
  assert.equal(row.email, "kari@example.no"); assert.equal(row.pitch, good.pitch);
  assert.equal(TEST_OUTBOX.length, 1); assert.equal(TEST_OUTBOX[0].to, "editor@example.no"); assert.equal(TEST_OUTBOX[0].replyTo, "kari@example.no");
  assert.match(TEST_OUTBOX[0].text, /Bitcoin mining in Norway/);
});
test("no COLUMNIST_TO: stored, nothing sent", async () => {
  const db = fresh(); TEST_OUTBOX.length = 0;
  const r = await call(db, "/api/columnist", { method: "POST", body: good, e: cenv(db, { COLUMNIST_TO: "" }) });
  assert.equal(r.status, 201); assert.equal(TEST_OUTBOX.length, 0);
});
test("validation, turnstile, honeypot, origin, rate", async () => {
  const db = fresh();
  assert.equal(validateColumnist({ ...good, email: "nope" })[1], "bad_email");
  assert.equal(validateColumnist({ ...good, pitch: "" })[1], "empty");
  assert.equal(validateColumnist({ ...good, sample: "javascript:x" })[1], "bad_link");
  assert.equal(validateColumnist({ ...good, why: "x".repeat(801) })[1], "too_long");
  assert.equal((await call(db, "/api/columnist", { method: "POST", body: { ...good, "cf-turnstile-response": "bad" }, e: cenv(db) })).j.error, "turnstile");
  assert.equal((await call(db, "/api/columnist", { method: "POST", body: good, e: cenv(db, { TIP_TEST: "0", TURNSTILE_SECRET: "" }) })).status, 503);
  assert.equal((await call(db, "/api/columnist", { method: "POST", body: good, origin: "https://evil.example", e: cenv(db) })).status, 403);
  const hp = await call(db, "/api/columnist", { method: "POST", body: { ...good, website: "x" }, e: cenv(db) });
  assert.equal(hp.status, 200);
  assert.equal(db.prepare("SELECT COUNT(*) n FROM columnist_applications").get().n, 0);
  const st = []; for (let i = 0; i < 4; i++) st.push((await call(db, "/api/columnist", { method: "POST", body: good, form: true, e: cenv(db) })).status);
  assert.deepEqual(st, [201, 201, 201, 429]);
  const pf = await call(db, "/api/columnist", { method: "OPTIONS" }); assert.equal(pf.res.status, 204);
});
