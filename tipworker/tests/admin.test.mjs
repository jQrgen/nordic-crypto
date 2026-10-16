// node --test tests/admin.test.mjs — admin magic-link login, sessions, domain allowlist, subscriber list. node:sqlite as D1,
// mail goes to the in-memory test outbox (SUBSCRIBE_TEST=1). No network, nothing deployed, no email sent.
import test from "node:test"; import assert from "node:assert/strict";
import { readFileSync } from "node:fs"; import { DatabaseSync } from "node:sqlite";
import worker from "../src/worker.js";
import { allowedAdmin, PER_EMAIL_N } from "../src/admin.js";
import { TEST_OUTBOX } from "../src/mailer.js";

class SqliteD1 {
  constructor(db) { this.db = db; }
  prepare(sql) { const db = this.db; const b = (...p) => ({
      run: async () => { const i = db.prepare(sql).run(...p); return { meta: { last_row_id: Number(i.lastInsertRowid), changes: i.changes } }; },
      first: async () => db.prepare(sql).get(...p) ?? null, all: async () => ({ results: db.prepare(sql).all(...p) }) });
    return { bind: (...p) => b(...p), ...b() }; }
  async batch(s) { const o = []; for (const x of s) o.push(await x.run()); return o; }
}
const O = "https://nordiccrypto.no";
function env(extra = {}) {
  const db = new DatabaseSync(":memory:");
  for (const m of ["0001_tips.sql", "0003_subscribers.sql", "0006_admin.sql"]) db.exec(readFileSync(new URL("../migrations/" + m, import.meta.url), "utf8"));
  return { DB: new SqliteD1(db), raw: db, SUBSCRIBE_TEST: "1", ...extra };
}
let ipn = 1;
const call = (e, method, path, { body, token, origin = O, ip } = {}) => worker.fetch(new Request("https://w.test" + path, { method,
  headers: { "Content-Type": "application/json", "CF-Connecting-IP": ip || "203.0.113." + (ipn++ % 250), ...(origin ? { Origin: origin } : {}), ...(token ? { Authorization: "Bearer " + token } : {}) },
  body: body ? JSON.stringify(body) : undefined }), e);
const linkToken = () => TEST_OUTBOX.at(-1).text.match(/#t=([A-Za-z0-9_-]+)/)[1];

test("allowedAdmin: exact domain only", () => {
  assert.equal(allowedAdmin(" JQrgen@NordicCrypto.no ", {}), "jqrgen@nordiccrypto.no");
  assert.equal(allowedAdmin("anyone@nordiccrypto.no", {}), "anyone@nordiccrypto.no");
  for (const e of ["x@evil-nordiccrypto.no", "x@nordiccrypto.no.evil.com", "x@a.nordiccrypto.no", "x@nordiccrypto.no.", "x@@nordiccrypto.no",
    "a@b@nordiccrypto.no", "x@nordiccrypto.com", "@nordiccrypto.no", "x y@nordiccrypto.no", "<x@nordiccrypto.no>", ".x@nordiccrypto.no",
    "x..y@nordiccrypto.no", "nordiccrypto.no", "", null, 5, ["x@nordiccrypto.no"]])
    assert.equal(allowedAdmin(e, {}), null, String(e));
  assert.equal(allowedAdmin("x@other.no", { ADMIN_EMAIL_DOMAIN: "Other.no" }), "x@other.no");
  assert.equal(allowedAdmin("x@nordiccrypto.no", { ADMIN_EMAIL_DOMAIN: "other.no" }), null);
});

test("login: same answer for every address, link only for the domain, single use, session works, logout", async () => {
  const e = env(); const before = TEST_OUTBOX.length;
  const a = await call(e, "POST", "/api/admin/login", { body: { email: "x@evil-nordiccrypto.no" } });
  const b = await call(e, "POST", "/api/admin/login", { body: { email: "JQrgen@nordiccrypto.no" } });
  assert.equal(a.status, 202); assert.equal(b.status, 202); assert.deepEqual(await a.json(), await b.json());
  assert.equal(TEST_OUTBOX.length, before + 1); assert.equal(TEST_OUTBOX.at(-1).to, "jqrgen@nordiccrypto.no");
  assert.ok(TEST_OUTBOX.at(-1).text.includes(O + "/admin/#t="));
  assert.equal(b.headers.get("Access-Control-Allow-Origin"), O);
  const tok = linkToken();
  assert.equal(e.raw.prepare("SELECT COUNT(*) n FROM admin_login_tokens WHERE token_hash = ?").get(tok).n, 0, "token stored hashed");
  const v = await call(e, "POST", "/api/admin/verify", { body: { token: tok } }); assert.equal(v.status, 200);
  const s = await v.json(); assert.equal(s.email, "jqrgen@nordiccrypto.no"); assert.ok(s.expires - Date.now() / 1000 > 6.9 * 86400);
  assert.equal((await call(e, "POST", "/api/admin/verify", { body: { token: tok } })).status, 401, "single use");
  assert.equal(e.raw.prepare("SELECT email FROM admin_logins").get().email, "jqrgen@nordiccrypto.no");
  const me = await call(e, "GET", "/api/admin/me", { token: s.token }); assert.equal((await me.json()).email, "jqrgen@nordiccrypto.no");
  assert.equal((await call(e, "POST", "/api/admin/logout", { token: s.token })).status, 200);
  assert.equal((await call(e, "GET", "/api/admin/me", { token: s.token })).status, 401);
});

test("expired link and expired session are refused; unauthenticated list is refused", async () => {
  const e = env();
  await call(e, "POST", "/api/admin/login", { body: { email: "a@nordiccrypto.no" } });
  const tok = linkToken(); e.raw.exec("UPDATE admin_login_tokens SET expires_at = 1");
  assert.equal((await call(e, "POST", "/api/admin/verify", { body: { token: tok } })).status, 401);
  await call(e, "POST", "/api/admin/login", { body: { email: "a@nordiccrypto.no" } });
  const s = await (await call(e, "POST", "/api/admin/verify", { body: { token: linkToken() } })).json();
  e.raw.exec("UPDATE admin_sessions SET expires_at = 1");
  assert.equal((await call(e, "GET", "/api/admin/subscribers", { token: s.token })).status, 401);
  assert.equal((await call(e, "GET", "/api/admin/subscribers")).status, 401);
  assert.equal((await call(e, "GET", "/api/admin/subscribers", { token: "x".repeat(43) })).status, 401);
});

test("CORS: only https://nordiccrypto.no", async () => {
  const e = env();
  assert.equal((await call(e, "POST", "/api/admin/login", { body: { email: "a@nordiccrypto.no" }, origin: "https://evil.example" })).status, 403);
  assert.equal((await call(e, "OPTIONS", "/api/admin/subscribers", { origin: "https://jqrgen.github.io" })).status, 403);
  const p = await call(e, "OPTIONS", "/api/admin/subscribers"); assert.equal(p.status, 204);
  assert.match(p.headers.get("Access-Control-Allow-Headers"), /Authorization/);
});

test("rate limits: per address (silent) and per IP", async () => {
  const e = env(); const n0 = TEST_OUTBOX.length;
  for (let i = 0; i < PER_EMAIL_N + 2; i++) assert.equal((await call(e, "POST", "/api/admin/login", { body: { email: "r@nordiccrypto.no" } })).status, 202);
  assert.equal(TEST_OUTBOX.length - n0, PER_EMAIL_N);
  const codes = []; for (let i = 0; i < 7; i++) codes.push((await call(e, "POST", "/api/admin/login", { body: { email: "z@x.no" }, ip: "198.51.100.9" })).status);
  assert.deepEqual(codes, [202, 202, 202, 202, 202, 429, 429]);
});

test("subscriber list with issues, and the delivery endpoint needs its secret", async () => {
  const e = env({ ADMIN_DELIVERY_TOKEN: "d".repeat(40) });
  e.raw.exec(`INSERT INTO subscribers (email, site, lang, status, created_at, confirmed_at) VALUES
    ('a@x.no','nordic-crypto','nb','confirmed','2026-10-01T00:00:00+00:00','2026-10-01T01:00:00+00:00'),
    ('b@x.no','nordic-crypto','en','pending','2026-10-02T00:00:00+00:00',NULL)`);
  const bad = await call(e, "POST", "/api/admin/deliveries", { token: "e".repeat(40), body: { deliveries: [{ subscriber_id: 1, issue: 1 }] }, origin: null });
  assert.equal(bad.status, 401);
  const ok = await call(e, "POST", "/api/admin/deliveries", { token: "d".repeat(40), body: { deliveries: [{ subscriber_id: 1, issue: 1 }, { subscriber_id: 1, issue: 2 }, { subscriber_id: 1, issue: 2 }] }, origin: null });
  assert.equal(ok.status, 200);
  await call(e, "POST", "/api/admin/login", { body: { email: "j@nordiccrypto.no" } });
  const s = await (await call(e, "POST", "/api/admin/verify", { body: { token: linkToken() } })).json();
  const l = await (await call(e, "GET", "/api/admin/subscribers", { token: s.token })).json();
  assert.equal(l.email, "j@nordiccrypto.no");
  assert.deepEqual(l.totals, { all: 2, pending: 1, confirmed: 1, unsubscribed: 0, deliveries: 2 });
  assert.deepEqual(l.rows[0].issues, [1, 2]); assert.equal(l.rows[0].last_issue, 2); assert.equal(l.rows[1].last_issue, null);
  assert.equal(l.last_issue, 2);
});
