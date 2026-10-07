import assert from "node:assert/strict";
import test from "node:test";
import worker, { safeEqual } from "../src/worker.js";
import { COPY } from "../src/copy.js";

class Mem {
  constructor() {
    this.tips = [];
    this.next = 1;
    this.salt = null;
    this.hits = [];
  }
  prepare(sql) {
    const self = this;
    return {
      args: [],
      bind(...a) { this.args = a; return this; },
      async run() { return self.exec(sql, this.args, "run"); },
      async first() { return self.exec(sql, this.args, "first"); },
      async all() { return { results: self.exec(sql, this.args, "all") }; },
    };
  }
  exec(sql, args, mode) {
    const s = sql.replace(/\s+/g, " ").trim();
    let result = null;
    if (s === "SELECT 1") result = { ok: 1 };
    else if (s.startsWith("DELETE FROM rate_hits WHERE")) {
      this.hits = this.hits.filter((h) => h.ts > args[0]);
      result = { success: true };
    } else if (s === "DELETE FROM rate_hits") {
      this.hits = [];
      result = { success: true };
    } else if (s.startsWith("SELECT salt")) result = this.salt;
    else if (s.startsWith("INSERT INTO rate_salt")) {
      this.salt = { salt: args[0], expires_at: args[1] };
      result = { success: true };
    } else if (s.includes("FROM rate_hits WHERE h = ?")) {
      result = { n: this.hits.filter((h) => h.h === args[0] && h.ts > args[1]).length };
    } else if (s.startsWith("SELECT COUNT(*) AS n FROM rate_hits WHERE ts")) {
      result = { n: this.hits.filter((h) => h.ts > args[0]).length };
    } else if (s.startsWith("INSERT INTO rate_hits")) {
      this.hits.push({ h: args[0], ts: args[1] });
      result = { success: true };
    } else if (s.startsWith("INSERT INTO tips")) {
      const row = {
        id: this.next++, created_at: args[0], language: args[1], page: args[2], tip: args[3],
        contact: args[4], attachments: args[5], status: "new", editor_notes: null,
      };
      this.tips.push(row);
      result = { id: row.id };
    } else if (s.includes("FROM tips WHERE status")) {
      result = this.tips.filter((t) => t.status === args[0]).sort((a, b) => a.id - b.id).slice(0, args[1]);
    } else if (s.includes("FROM tips ORDER BY id")) {
      result = [...this.tips].sort((a, b) => a.id - b.id).slice(0, args[0]);
    } else if (s.startsWith("UPDATE tips")) {
      const row = this.tips.find((t) => t.id === args[2]);
      if (row) { row.status = args[0]; row.editor_notes = args[1]; }
      result = { success: true };
    } else if (s.includes("FROM tips WHERE id = ?")) {
      result = this.tips.find((t) => t.id === args[0]) || null;
    } else throw new Error("unhandled sql: " + s);
    if (mode === "all") return Array.isArray(result) ? result : [];
    if (mode === "first") return Array.isArray(result) ? (result[0] || null) : result;
    return result || { success: true };
  }
}

const READ = "read-token-0123456789abcdef";
const IP = "203.0.113.50";

function baseEnv(db, extra = {}) {
  return {
    DB: db,
    TURNSTILE_SECRET: "test-secret",
    READ_TOKEN: READ,
    ...extra,
  };
}

const seen = [];
globalThis.fetch = async (url, opts) => {
  seen.push({ url: String(url), body: opts && opts.body });
  if (String(url).includes("siteverify")) {
    const params = new URLSearchParams(opts.body);
    return new Response(JSON.stringify({ success: params.get("response") === "ok-token" }), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  }
  return new Response("ok", { status: 204 });
};

async function post(db, path, json, headers = {}, extraEnv = {}) {
  const req = new Request("https://tips.nordiccrypto.no" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: "https://nordiccrypto.no", "CF-Connecting-IP": IP, ...headers },
    body: JSON.stringify(json),
  });
  return worker.fetch(req, baseEnv(db, extraEnv));
}

const tipBody = (over = {}) => ({
  tip: "A story on bitcoin in Denmark we have not covered.",
  language: "da",
  page: "/da/tip/",
  contact: "",
  attachments: "https://example.com/story",
  "cf-turnstile-response": "ok-token",
  ...over,
});

test("health", async () => {
  const res = await worker.fetch(new Request("https://tips.nordiccrypto.no/api/health"), baseEnv(new Mem()));
  assert.equal(res.status, 200);
  assert.equal((await res.json()).service, "nordic-crypto-tip-intake");
});

test("stores a tip without the IP and lists it for the read token", async () => {
  const db = new Mem();
  seen.length = 0;
  const res = await post(db, "/api/tip", tipBody(), {}, { TIP_WEBHOOK_URL: "https://hooks.example/tip", TIP_WEBHOOK_BEARER: "whsec" });
  assert.equal(res.status, 201);
  const created = await res.json();
  assert.equal(created.ok, true);
  assert.equal(db.tips.length, 1);
  const blob = JSON.stringify({ tips: db.tips, hits: db.hits, salt: db.salt });
  assert.equal(blob.includes(IP), false);
  assert.equal(db.tips[0].status, "new");
  assert.equal(db.tips[0].language, "da");
  assert.equal(JSON.parse(db.tips[0].attachments)[0], "https://example.com/story");
  assert.equal(db.tips[0].contact, null);
  const hook = seen.find((c) => c.url.startsWith("https://hooks.example"));
  assert.ok(hook);
  const raw = String(hook.body);
  assert.equal(raw.includes(IP), false);
  assert.equal(raw.includes("bitcoin in Denmark"), true);
  const denied = await worker.fetch(new Request("https://tips.nordiccrypto.no/api/tips"), baseEnv(db));
  assert.equal(denied.status, 401);
  const list = await worker.fetch(new Request("https://tips.nordiccrypto.no/api/tips?status=new", {
    headers: { Authorization: "Bearer " + READ },
  }), baseEnv(db));
  assert.equal(list.status, 200);
  const listed = await list.json();
  assert.equal(listed.tips.length, 1);
  assert.equal(listed.tips[0].id, created.id);
  const mark = await post(db, "/api/tips/" + created.id, { status: "handled", editor_notes: "forwarded to the newsroom editor" }, {
    Authorization: "Bearer " + READ, Origin: "",
  });
  assert.equal(mark.status, 200);
  assert.equal((await mark.json()).tip.status, "handled");
  assert.equal(db.tips[0].editor_notes, "forwarded to the newsroom editor");
});

test("rejects a missing spam check, a bad link, and a foreign origin", async () => {
  const db = new Mem();
  const noToken = await post(db, "/api/tip", tipBody({ "cf-turnstile-response": "" }));
  assert.equal(noToken.status, 400);
  assert.equal((await noToken.json()).error, "turnstile");
  const bad = await post(db, "/api/tip", tipBody({ attachments: "javascript:alert(1)" }));
  assert.equal(bad.status, 400);
  assert.equal((await bad.json()).error, "bad_attachment");
  const evil = await post(db, "/api/tip", tipBody(), { Origin: "https://evil.example" });
  assert.equal(evil.status, 403);
  assert.equal(db.tips.length, 0);
});

test("honeypot stores nothing", async () => {
  const db = new Mem();
  const honey = await post(db, "/api/tip", tipBody({ website: "https://spam.example" }));
  assert.equal(honey.status, 200);
  assert.equal(db.tips.length, 0);
});

test("the sixth tip in the window is limited", async () => {
  const db = new Mem();
  for (let i = 0; i < 5; i++) {
    const res = await post(db, "/api/tip", tipBody({ tip: "tip " + i }));
    assert.equal(res.status, 201);
  }
  const blocked = await post(db, "/api/tip", tipBody({ tip: "one more" }));
  assert.equal(blocked.status, 429);
  assert.equal(db.tips.length, 5);
});

test("onion bearer skips Turnstile and does not hash the VPS address", async () => {
  const db = new Mem();
  const ingest = "ingest-" + "0123456789abcdef";
  const addr = "http://" + "b".repeat(56) + ".onion/da/";
  const res = await post(db, "/api/tip", tipBody({ "cf-turnstile-response": "", page: addr }), {
    Authorization: "Bearer " + ingest,
  }, { ONION_INGEST_TOKEN: ingest });
  assert.equal(res.status, 201);
  assert.equal(JSON.stringify(db.hits).includes(IP), false);
  assert.equal(db.tips[0].page, addr);
  const same = await post(db, "/api/tip", tipBody({ "cf-turnstile-response": "" }), {
    Authorization: "Bearer " + READ,
  }, { ONION_INGEST_TOKEN: READ, READ_TOKEN: READ });
  assert.equal(same.status, 400);
});

test("form POST returns a left-aligned confirmation", async () => {
  const db = new Mem();
  const body = new URLSearchParams({
    tip: "Et tip om bitcoin.",
    language: "nb",
    page: "/nb/tip/",
    contact: "redaksjonen@example.com",
    "cf-turnstile-response": "ok-token",
  });
  const req = new Request("https://tips.nordiccrypto.no/api/tip", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Origin: "https://nordiccrypto.no",
      "CF-Connecting-IP": IP,
    },
    body,
  });
  const res = await worker.fetch(req, baseEnv(db));
  assert.equal(res.status, 201);
  const html = await res.text();
  assert.match(html, /text-align:left/);
  assert.match(html, /kunstig intelligens/);
  assert.equal(html.includes("text-align:center"), false);
  assert.equal(html.includes(IP), false);
  assert.equal(html.includes("github.com"), false);
});

test("salt expiry drops old hashes", async () => {
  const db = new Mem();
  assert.equal((await post(db, "/api/tip", tipBody())).status, 201);
  assert.equal(db.hits.length, 1);
  db.salt.expires_at = 1;
  assert.equal((await post(db, "/api/tip", tipBody({ tip: "after rotation" }))).status, 201);
  assert.equal(db.hits.length, 1);
});

test("norwegian confirmation copy does not use AI or KI", () => {
  const bad = /(?<![\w-])(?:AI|KI)(?![\w])/;
  for (const lang of ["nn", "nb"]) {
    assert.equal(bad.test(JSON.stringify(COPY[lang])), false, lang);
  }
});

test("safeEqual", () => {
  assert.equal(safeEqual("read-token-0123456789abcdef", READ), true);
  assert.equal(safeEqual("read-token-0123456789abcdee", READ), false);
  assert.equal(safeEqual("short", READ), false);
  assert.equal(safeEqual("", READ), false);
});
