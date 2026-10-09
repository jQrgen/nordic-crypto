// node --test tests/shouts.test.mjs — validation, one shared room, rate limit, reports, moderation.
// Uses node:sqlite as D1. No network, no secrets, nothing deployed.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import worker from "../src/worker.js";
import { checkShout, escapeHtml, plainText, spamHit, LIMITS } from "../src/shouts.js";

const IP = "203.0.113.50";
const ORIGIN = "https://nordiccrypto.no";
const ADMIN = "test-admin-token";

class SqliteD1 {
  constructor(db) { this.db = db; }
  prepare(sql) {
    const db = this.db;
    const bound = (...params) => ({
      run: async () => {
        const info = db.prepare(sql).run(...params);
        return { meta: { last_row_id: Number(info.lastInsertRowid), changes: info.changes } };
      },
      first: async () => db.prepare(sql).get(...params) ?? null,
      all: async () => ({ results: db.prepare(sql).all(...params) }),
    });
    return { bind: (...params) => bound(...params), ...bound() };
  }
  async batch(stmts) {
    const out = [];
    for (const s of stmts) out.push(await s.run());
    return out;
  }
}

function fresh() {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../migrations/0004_shouts.sql", import.meta.url), "utf8"));
  return db;
}

function env(db, over = {}) {
  return { DB: new SqliteD1(db), SHOUT_TEST: "1", SHOUT_ADMIN_TOKEN: ADMIN, ...over };
}

function dump(db) {
  const tables = db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map((r) => r.name);
  let blob = "";
  for (const name of tables) blob += JSON.stringify(db.prepare(`SELECT * FROM ${name}`).all());
  return blob;
}

async function call(db, path, { method = "GET", body, ip = IP, origin = ORIGIN, token, e } = {}) {
  const headers = {};
  if (origin) headers.origin = origin;
  if (ip) headers["cf-connecting-ip"] = ip;
  if (body !== undefined) headers["content-type"] = "application/json";
  if (token) headers.authorization = "Bearer " + token;
  const res = await worker.fetch(new Request("https://nordic-crypto-tips.nordiccrypto.workers.dev" + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  }), e || env(db));
  const text = await res.text();
  let json = null;
  try { json = JSON.parse(text); } catch { json = null; }
  return { status: res.status, json, text, headers: res.headers };
}

function post(db, body, opt) {
  return call(db, "/api/shouts", { method: "POST", body: { "cf-turnstile-response": "test-pass", ...body }, ...opt });
}

test("plain text strips tags and does not keep angle brackets", () => {
  assert.equal(plainText("  <script>alert(1)</script>hi  "), "hi");
  assert.equal(plainText("see <b>this</b>"), "see this");
  assert.equal(plainText("a < b > c"), "a < b > c");
  assert.equal(escapeHtml(`<>&"`), "&lt;&gt;&amp;&quot;");
  assert.equal(spamHit("hello from Oslo"), false);
  assert.equal(spamHit("claim your free btc"), true);
  assert.equal(checkShout("Ada", "Hello https://example.com/note", "sv")[0].message, "Hello https://example.com/note");
  assert.equal(checkShout("Ada", "<img src=x onerror=alert(1)>hi", "en")[0].message, "hi");
  assert.equal(checkShout("A", "hi", "en")[1], "nickname");
  assert.equal(checkShout("x".repeat(25), "hi", "en")[1], "nickname");
  assert.equal(checkShout("Ada", "", "en")[1], "message");
  assert.equal(checkShout("Ada", "x".repeat(281), "en")[1], "message");
  assert.equal(checkShout("Ada", "free bitcoin here", "en")[1], "spam");
  assert.equal(checkShout("Ada", "Hej", "not-a-lang")[0].lang, null);
  assert.equal(checkShout("Mäkinen", "Moi", "fi")[0].lang, "fi");
});

test("post validates, escapes by stripping, and never stores the raw IP", async () => {
  const db = fresh();
  const bad = await post(db, { nickname: "A", message: "hi" });
  assert.equal(bad.status, 400);
  assert.equal(bad.json.error, "nickname");
  const long = await post(db, { nickname: "Ada", message: "x".repeat(LIMITS.maxMessage + 1) });
  assert.equal(long.status, 400);
  assert.equal(long.json.error, "message");
  const spam = await post(db, { nickname: "Ada", message: "dm me for a guaranteed return" });
  assert.equal(spam.status, 400);
  assert.equal(spam.json.error, "spam");
  const html = await post(db, { nickname: "Ada", message: "<script>alert(1)</script>hello https://example.com/a", lang: "en" });
  assert.equal(html.status, 201);
  assert.equal(html.json.shout.message, "hello https://example.com/a");
  assert.equal(html.json.shout.message.includes("<"), false);
  assert.equal(html.json.shout.lang, "en");
  assert.equal("ip_hash" in html.json.shout, false);
  const honey = await post(db, { nickname: "Ada", message: "stored?", website: "https://spam.example" }, { ip: "203.0.113.9" });
  assert.equal(honey.status, 200);
  assert.equal(honey.json.shout, undefined);
  const blob = dump(db);
  assert.equal(blob.includes(IP), false);
  assert.equal(blob.includes("203.0.113.9"), false);
  assert.equal(blob.includes("<script"), false);
  assert.match(blob, /"ip_hash":"[0-9a-f]{64}"/);
});

test("turnstile is required and the siteverify call does not send the IP", async () => {
  const db = fresh();
  const missing = await post(db, { nickname: "Ada", message: "hi", "cf-turnstile-response": "" });
  assert.equal(missing.status, 400);
  assert.equal(missing.json.error, "turnstile");
  const fail = await post(db, { nickname: "Ada", message: "hi", "cf-turnstile-response": "test-fail" });
  assert.equal(fail.status, 400);
  const off = await post(db, { nickname: "Ada", message: "hi" }, { e: env(db, { SHOUT_TEST: "0", TURNSTILE_SECRET: "" }) });
  assert.equal(off.status, 503);
  const seen = [];
  const real = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    seen.push({ url: String(url), body: String(init.body) });
    return new Response(JSON.stringify({ success: true }));
  };
  try {
    const ok = await post(db, { nickname: "Ada", message: "checked" }, {
      e: env(db, { SHOUT_TEST: "0", TURNSTILE_SECRET: "secret-not-the-ip" }),
      ip: IP,
    });
    assert.equal(ok.status, 201, ok.text);
  } finally { globalThis.fetch = real; }
  assert.equal(seen.length, 1);
  assert.match(seen[0].url, /challenges\.cloudflare\.com\/turnstile\/v0\/siteverify$/);
  assert.equal(seen[0].body.includes(IP), false);
  assert.match(seen[0].body, /secret=secret-not-the-ip/);
});

test("one room: lang is a tag, never a filter", async () => {
  const db = fresh();
  const a = await post(db, { nickname: "Ada", message: "Hello from Oslo", lang: "en" }, { ip: "203.0.113.1" });
  const b = await post(db, { nickname: "Bjorn", message: "Hej från Stockholm", lang: "sv" }, { ip: "203.0.113.2" });
  const c = await post(db, { nickname: "Mikko", message: "Moi Helsingistä", lang: "fi" }, { ip: "203.0.113.3" });
  assert.equal(a.status, 201);
  assert.equal(b.json.shout.message, "Hej från Stockholm");
  assert.equal(c.json.shout.lang, "fi");
  for (const q of ["", "?lang=sv", "?lang=en", "?room=sv", "?channel=fi"]) {
    const res = await call(db, "/api/shouts" + q);
    assert.equal(res.status, 200);
    assert.deepEqual(res.json.shouts.map((s) => s.message), ["Hello from Oslo", "Hej från Stockholm", "Moi Helsingistä"]);
  }
  const se = await call(db, "/api/shouts", { origin: "https://nordiccrypto.se" });
  assert.equal(se.status, 200);
  assert.equal(se.headers.get("access-control-allow-origin"), "https://nordiccrypto.se");
  const evil = await call(db, "/api/shouts", { origin: "https://evil.example" });
  assert.equal(evil.status, 403);
});

test("rate limit is per daily hash and the sixth post is refused", async () => {
  const db = fresh();
  for (let i = 0; i < LIMITS.posts; i++) {
    const res = await post(db, { nickname: "Ada", message: "n" + i });
    assert.equal(res.status, 201, res.text);
  }
  const blocked = await post(db, { nickname: "Ada", message: "too many" });
  assert.equal(blocked.status, 429);
  assert.equal(blocked.json.error, "rate");
  const other = await post(db, { nickname: "Bo", message: "other" }, { ip: "203.0.113.77" });
  assert.equal(other.status, 201);
  const n = db.prepare("SELECT COUNT(*) AS n FROM shouts").get().n;
  assert.equal(n, LIMITS.posts + 1);
  assert.equal(dump(db).includes(IP), false);
});

test("a ban matches only the current day's hash", async () => {
  const db = fresh();
  const first = await post(db, { nickname: "Ada", message: "first" });
  assert.equal(first.status, 201);
  const old = db.prepare("SELECT ip_hash FROM shouts WHERE id = ?").get(first.json.shout.id).ip_hash;
  db.prepare("UPDATE shout_salt SET salt = ?").run("rotated-salt-value");
  db.prepare("INSERT INTO shout_bans (ip_hash, created_at) VALUES (?, ?)").run(old, "2026-10-07T00:00:00+00:00");
  const again = await post(db, { nickname: "Ada", message: "after rotation" });
  assert.equal(again.status, 201, again.text);
  const neu = db.prepare("SELECT ip_hash FROM shouts WHERE message = 'after rotation'").get().ip_hash;
  assert.notEqual(neu, old);
  const ban = await call(db, "/api/shouts/admin", {
    method: "POST", token: ADMIN, body: { action: "ban", hash: neu },
  });
  assert.equal(ban.status, 200);
  const denied = await post(db, { nickname: "Ada", message: "banned now" });
  assert.equal(denied.status, 403);
  assert.equal(denied.json.error, "banned");
  assert.equal(dump(db).includes(IP), false);
});

test("pagination returns the latest 50 and still every language", async () => {
  const db = fresh();
  const ins = db.prepare("INSERT INTO shouts (created_at, nickname, message, lang, ip_hash, status, reports) VALUES (?, ?, ?, ?, ?, 'visible', 0)");
  for (let i = 1; i <= 55; i++) {
    ins.run("2026-10-07T12:00:00+00:00", "Ada", "m" + i, i % 2 ? "en" : "sv", "ab".repeat(32));
  }
  const page = await call(db, "/api/shouts?lang=fi");
  assert.equal(page.json.shouts.length, 50);
  assert.equal(page.json.shouts[0].id, 6);
  assert.equal(page.json.shouts[49].id, 55);
  assert.equal(page.json.shouts.some((s) => s.lang === "en"), true);
  assert.equal(page.json.shouts.some((s) => s.lang === "sv"), true);
  assert.equal("ip_hash" in page.json.shouts[0], false);
  const older = await call(db, "/api/shouts?before=6");
  assert.deepEqual(older.json.shouts.map((s) => s.id), [1, 2, 3, 4, 5]);
  const after = await call(db, "/api/shouts?after=55");
  assert.deepEqual(after.json.shouts, []);
});

test("reports from distinct hashes hide the message; one hash counts once", async () => {
  const db = fresh();
  const made = await post(db, { nickname: "Ada", message: "please review" }, { ip: "203.0.113.10" });
  const id = made.json.shout.id;
  const report = (ip) => call(db, "/api/shouts/report", { method: "POST", ip, body: { id } });
  assert.equal((await report("203.0.113.11")).status, 200);
  assert.equal((await report("203.0.113.11")).status, 200);
  assert.equal((await report("203.0.113.12")).status, 200);
  let listed = await call(db, "/api/shouts");
  assert.equal(listed.json.shouts.some((s) => s.id === id), true);
  assert.equal((await report("203.0.113.13")).status, 200);
  listed = await call(db, "/api/shouts");
  assert.equal(listed.json.shouts.some((s) => s.id === id), false);
  const row = db.prepare("SELECT status, reports FROM shouts WHERE id = ?").get(id);
  assert.equal(row.status, "hidden");
  assert.equal(row.reports, LIMITS.hideAfter);
  assert.equal(dump(db).includes("203.0.113.11"), false);
});

test("admin bearer token hides, deletes and bans; the queue is not public", async () => {
  const db = fresh();
  const made = await post(db, { nickname: "Ada", message: "hide me" }, { ip: "198.51.100.8" });
  const id = made.json.shout.id;
  const no = await call(db, "/api/shouts/admin", { token: "nope" });
  assert.equal(no.status, 401);
  assert.equal(no.headers.get("access-control-allow-origin"), null);
  const hidden = await call(db, "/api/shouts/admin", { method: "POST", token: ADMIN, body: { action: "hide", id } });
  assert.equal(hidden.status, 200);
  assert.equal((await call(db, "/api/shouts")).json.shouts.length, 0);
  const queue = await call(db, "/api/shouts/admin", { token: ADMIN });
  assert.equal(queue.json.shouts.length, 1);
  assert.match(queue.json.shouts[0].ip_hash, /^[0-9a-f]{64}$/);
  const back = await call(db, "/api/shouts/admin", { method: "POST", token: ADMIN, body: { action: "restore", id } });
  assert.equal(back.status, 200);
  assert.equal((await call(db, "/api/shouts")).json.shouts.length, 1);
  const hash = db.prepare("SELECT ip_hash FROM shouts WHERE id = ?").get(id).ip_hash;
  const banned = await call(db, "/api/shouts/admin", { method: "POST", token: ADMIN, body: { action: "ban", id } });
  assert.equal(banned.status, 200);
  assert.equal((await post(db, { nickname: "Ada", message: "nope" }, { ip: "198.51.100.8" })).status, 403);
  const gone = await call(db, "/api/shouts/admin", { method: "POST", token: ADMIN, body: { action: "delete", id } });
  assert.equal(gone.status, 200);
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM shouts").get().n, 0);
  const unban = await call(db, "/api/shouts/admin", { method: "POST", token: ADMIN, body: { action: "unban", hash } });
  assert.equal(unban.status, 200);
  const again = await post(db, { nickname: "Ada", message: "back" }, { ip: "198.51.100.8" });
  assert.equal(again.status, 201, again.text);
  const opt = await call(db, "/api/shouts", { method: "OPTIONS", origin: ORIGIN });
  assert.equal(opt.status, 204);
  assert.match(opt.headers.get("access-control-allow-methods"), /GET/);
});

test("migration stores a hash, not a raw IP column", () => {
  const sql = readFileSync(new URL("../migrations/0004_shouts.sql", import.meta.url), "utf8");
  assert.match(sql, /ip_hash TEXT NOT NULL/);
  assert.equal(/^\s+ip\s+TEXT/im.test(sql), false);
  const src = readFileSync(new URL("../src/shouts.js", import.meta.url), "utf8");
  assert.equal(src.includes("console."), false);
  assert.equal(src.includes("remoteip"), false);
});
