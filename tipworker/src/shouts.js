// Shared shoutbox for Nordic Crypto. One room: lang is a tag for the page a message was
// posted from, never a filter. GET /api/shouts ignores lang, room and channel.
//   GET  /api/shouts?limit=50&before=<id>&after=<id>   visible rows, oldest-first in the page
//   POST /api/shouts                                   nickname, message, optional lang, Turnstile
//   POST /api/shouts/report                            {id} — N distinct daily hashes hide it
//   GET  /api/shouts/admin                             hidden queue (bearer token, no CORS)
//   POST /api/shouts/admin                             hide | delete | restore | ban | unban
// Plain text: tags and angle brackets are removed before storage. The page inserts messages
// with textContent (the browser escapes them) and does not turn URLs into links.
// Privacy: the module never logs. ip_hash = SHA-256(daily salt | IP). The salt is replaced
// every UTC day and the previous salt is deleted, so a ban of a hash lasts only that day.
// Same codes as i18n.ALL_LANGS. A tag outside this set is stored as null; the post still lands
// in the one shared room.
const LANGS = new Set("en nn nb sv da fi is zh hi es fr ar bn pt ru ur id de ja sw mr".split(" "));

export const LIMITS = {
  posts: 5,
  windowSec: 600,
  globalPosts: 100,
  reports: 30,
  hideAfter: 3,
  maxMessage: 280,
  minNick: 2,
  maxNick: 24,
  maxBody: 4096,
};

const enc = new TextEncoder();
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const clen = (s) => [...s].length;
const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");

const SPAM = [
  /seed ?phrase/i,
  /private ?key/i,
  /guaranteed (profit|returns?|gains)/i,
  /double your (btc|bitcoin|crypto|money|eth)/i,
  /airdrop/i,
  /referral (code|link|bonus)/i,
  /whatsapp/i,
  /t\.me\//i,
  /bit\.ly\//i,
  /pump and dump/i,
  /\bdm me\b/i,
  /free (btc|bitcoin|crypto)/i,
  /(.)\1{11,}/,
];

export function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** Tags removed, angle brackets removed, whitespace collapsed. What remains is plain text. */
export function plainText(s) {
  return String(s)
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<\/?[a-z!][^>]*>/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function spamHit(text) {
  const urls = text.match(/https?:\/\/|www\./gi);
  if (urls && urls.length > 2) return true;
  return SPAM.some((re) => re.test(text));
}

export function checkShout(nickname, message, lang) {
  if (typeof nickname !== "string" || typeof message !== "string") return [null, "invalid"];
  const nick = plainText(nickname);
  const msg = plainText(message);
  if (clen(nick) < LIMITS.minNick || clen(nick) > LIMITS.maxNick) return [null, "nickname"];
  if (!/^[\p{L}\p{N}][\p{L}\p{N} ._'’-]{0,23}$/u.test(nick)) return [null, "nickname"];
  if (/https?:|www\.|t\.me/i.test(nick)) return [null, "nickname"];
  if (clen(msg) < 1 || clen(msg) > LIMITS.maxMessage) return [null, "message"];
  if (spamHit(nick + "\n" + msg)) return [null, "spam"];
  let tag = null;
  if (typeof lang === "string") {
    const code = lang.trim().toLowerCase();
    if (LANGS.has(code)) tag = code;
  }
  return [{ nickname: nick, message: msg, lang: tag }, null];
}

function safeEqual(a, b) {
  const aa = enc.encode(String(a));
  const bb = enc.encode(String(b));
  if (!aa.length || aa.length !== bb.length) return false;
  // Same-length XOR. Workers and Node do not share one timingSafeEqual entry point.
  let d = 0;
  for (let i = 0; i < aa.length; i++) d |= aa[i] ^ bb[i];
  return d === 0;
}

function bearer(req) {
  const m = (req.headers.get("Authorization") || "").match(/^Bearer\s+(\S+)\s*$/i);
  return m ? m[1] : "";
}

function clientIp(req) {
  return (req.headers.get("CF-Connecting-IP") || "unknown").trim().slice(0, 64);
}

export async function turnstileOk(env, token) {
  if (env && env.SHOUT_TEST === "1") return token === "test-pass" ? "ok" : "bad";
  const secret = env && env.TURNSTILE_SECRET;
  if (!secret) return "unconfigured";
  if (!token || typeof token !== "string") return "bad";
  let res;
  try {
    res = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ secret, response: token.slice(0, 2048) }),
    });
  } catch {
    return "bad";
  }
  let data;
  try { data = await res.json(); } catch { return "bad"; }
  return data && data.success === true ? "ok" : "bad";
}

async function dailyHash(db, ip) {
  const now = Math.floor(Date.now() / 1000);
  const day = new Date().toISOString().slice(0, 10);
  const fresh = hex(crypto.getRandomValues(new Uint8Array(32)));
  await db.batch([
    db.prepare("DELETE FROM shout_hits WHERE ts <= ?").bind(now - LIMITS.windowSec),
    db.prepare("DELETE FROM shout_salt WHERE day <> ?").bind(day),
    db.prepare("INSERT OR IGNORE INTO shout_salt (day, salt) VALUES (?, ?)").bind(day, fresh),
  ]);
  const row = await db.prepare("SELECT salt FROM shout_salt WHERE day = ?").bind(day).first();
  const hash = hex(await crypto.subtle.digest("SHA-256", enc.encode(row.salt + "|" + ip)));
  return { hash, now };
}

async function limited(db, hash, now, kind, max, globalMax) {
  const c = await db.prepare(
    "SELECT (SELECT COUNT(*) FROM shout_hits WHERE h = ? AND kind = ? AND ts > ?) AS mine, (SELECT COUNT(*) FROM shout_hits WHERE kind = ? AND ts > ?) AS total"
  ).bind(hash, kind, now - LIMITS.windowSec, kind, now - LIMITS.windowSec).first();
  if ((c.mine || 0) >= max || (globalMax && (c.total || 0) >= globalMax)) return false;
  await db.prepare("INSERT INTO shout_hits (h, ts, kind) VALUES (?, ?, ?)").bind(hash, now, kind).run();
  return true;
}

function posInt(v) {
  const n = Number(v);
  return Number.isInteger(n) && n > 0 ? n : 0;
}

function originOk(req, H) {
  const origin = req.headers.get("Origin");
  if (origin !== null && !H.ORIGINS.has(origin)) return false;
  return true;
}

async function readJson(req, H) {
  const cl = req.headers.get("Content-Length");
  if (cl !== null && !(Number(cl) <= LIMITS.maxBody)) return [null, 413];
  const raw = await H.readCapped(req, LIMITS.maxBody);
  if (raw === null) return [null, 413];
  const ctype = (req.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  if (ctype !== "application/json") return [null, 415];
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(raw);
    const f = JSON.parse(text);
    if (f === null || typeof f !== "object" || Array.isArray(f)) return [null, 400];
    return [f, 0];
  } catch {
    return [null, 400];
  }
}

function publicRow(r) {
  return { id: r.id, nickname: r.nickname, message: r.message, created_at: r.created_at, lang: r.lang || null };
}

async function list(req, env, H) {
  if (!originOk(req, H)) return H.send(req, 403, { ok: false, error: "Origin not allowed." });
  const u = new URL(req.url);
  // lang, room and channel are ignored on purpose: one shared stream.
  const before = posInt(u.searchParams.get("before"));
  const after = posInt(u.searchParams.get("after"));
  let limit = posInt(u.searchParams.get("limit")) || 50;
  if (limit > 50) limit = 50;
  let sql = "SELECT id, created_at, nickname, message, lang FROM shouts WHERE status = 'visible'";
  const binds = [];
  if (before) { sql += " AND id < ?"; binds.push(before); }
  if (after) { sql += " AND id > ?"; binds.push(after); }
  sql += " ORDER BY id DESC LIMIT ?";
  binds.push(limit);
  try {
    const res = await env.DB.prepare(sql).bind(...binds).all();
    const rows = (res.results || []).slice().reverse().map(publicRow);
    return H.send(req, 200, { ok: true, shouts: rows });
  } catch {
    return H.send(req, 503, { ok: false, error: "offline" });
  }
}

async function create(req, env, H) {
  if (!originOk(req, H)) return H.send(req, 403, { ok: false, error: "Origin not allowed." });
  const [f, code] = await readJson(req, H);
  if (code) return H.send(req, code === 400 ? 400 : code, { ok: false, error: code === 415 ? "json" : code === 413 ? "length" : "json" });
  const hp = f.website;
  if (hp && (typeof hp !== "string" || hp.trim())) return H.send(req, 200, { ok: true });
  const lang = Object.prototype.hasOwnProperty.call(f, "lang") ? f.lang : "";
  const nickIn = Object.prototype.hasOwnProperty.call(f, "nickname") ? f.nickname : "";
  const msgIn = Object.prototype.hasOwnProperty.call(f, "message") ? f.message : "";
  if (typeof nickIn !== "string" || typeof msgIn !== "string" || (lang !== "" && typeof lang !== "string"))
    return H.send(req, 400, { ok: false, error: "invalid" });
  const [row, err] = checkShout(nickIn, msgIn, typeof lang === "string" ? lang : "");
  if (err) return H.send(req, 400, { ok: false, error: err });
  const token = typeof f["cf-turnstile-response"] === "string" ? f["cf-turnstile-response"] : (typeof f.turnstile === "string" ? f.turnstile : "");
  let gate;
  try { gate = await turnstileOk(env, token); }
  catch { gate = "bad"; }
  if (gate === "unconfigured") return H.send(req, 503, { ok: false, error: "turnstile" });
  if (gate !== "ok") return H.send(req, 400, { ok: false, error: "turnstile" });
  const ip = clientIp(req);
  try {
    const { hash, now } = await dailyHash(env.DB, ip);
    const ban = await env.DB.prepare("SELECT 1 AS banned FROM shout_bans WHERE ip_hash = ?").bind(hash).first();
    if (ban) return H.send(req, 403, { ok: false, error: "banned" });
    if (!(await limited(env.DB, hash, now, "post", LIMITS.posts, LIMITS.globalPosts)))
      return H.send(req, 429, { ok: false, error: "rate" });
    const created = nowIso();
    const ins = await env.DB.prepare(
      "INSERT INTO shouts (created_at, nickname, message, lang, ip_hash, status, reports) VALUES (?, ?, ?, ?, ?, 'visible', 0)"
    ).bind(created, row.nickname, row.message, row.lang, hash).run();
    const id = Number(ins.meta && ins.meta.last_row_id);
    return H.send(req, 201, { ok: true, shout: { id, nickname: row.nickname, message: row.message, created_at: created, lang: row.lang } });
  } catch {
    return H.send(req, 503, { ok: false, error: "offline" });
  }
}

async function report(req, env, H) {
  if (!originOk(req, H)) return H.send(req, 403, { ok: false, error: "Origin not allowed." });
  const [f, code] = await readJson(req, H);
  if (code) return H.send(req, code === 400 ? 400 : code, { ok: false, error: "json" });
  const id = posInt(f.id);
  if (!id) return H.send(req, 400, { ok: false, error: "id" });
  const ip = clientIp(req);
  try {
    const row = await env.DB.prepare("SELECT id, status FROM shouts WHERE id = ?").bind(id).first();
    if (!row) return H.send(req, 404, { ok: false, error: "missing" });
    if (row.status !== "visible") return H.send(req, 200, { ok: true });
    const { hash, now } = await dailyHash(env.DB, ip);
    if (!(await limited(env.DB, hash, now, "report", LIMITS.reports, 0)))
      return H.send(req, 429, { ok: false, error: "rate" });
    const ins = await env.DB.prepare(
      "INSERT OR IGNORE INTO shout_reports (shout_id, ip_hash, created_at) VALUES (?, ?, ?)"
    ).bind(id, hash, nowIso()).run();
    if (ins.meta && ins.meta.changes) {
      await env.DB.prepare("UPDATE shouts SET reports = reports + 1 WHERE id = ?").bind(id).run();
      await env.DB.prepare(
        "UPDATE shouts SET status = 'hidden' WHERE id = ? AND reports >= ? AND status = 'visible'"
      ).bind(id, LIMITS.hideAfter).run();
    }
    return H.send(req, 200, { ok: true });
  } catch {
    return H.send(req, 503, { ok: false, error: "offline" });
  }
}

function adminSend(code, obj) {
  return new Response(JSON.stringify(obj), {
    status: code,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
    },
  });
}

async function admin(req, env) {
  const token = env && typeof env.SHOUT_ADMIN_TOKEN === "string" ? env.SHOUT_ADMIN_TOKEN : "";
  if (!token || !safeEqual(bearer(req), token)) return adminSend(401, { ok: false, error: "unauthorized" });
  if (req.method === "GET" || req.method === "HEAD") {
    if (req.method === "HEAD") return new Response(null, { status: 200, headers: { "Cache-Control": "no-store" } });
    try {
      const res = await env.DB.prepare(
        "SELECT id, created_at, nickname, message, lang, ip_hash, status, reports FROM shouts WHERE status = 'hidden' ORDER BY id DESC LIMIT 50"
      ).bind().all();
      return adminSend(200, { ok: true, shouts: res.results || [] });
    } catch {
      return adminSend(503, { ok: false, error: "offline" });
    }
  }
  if (req.method !== "POST") return adminSend(405, { ok: false, error: "method" });
  const raw = await req.json().catch(() => null);
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return adminSend(400, { ok: false, error: "json" });
  const action = typeof raw.action === "string" ? raw.action : "";
  const id = posInt(raw.id);
  let hash = typeof raw.hash === "string" ? raw.hash.trim().toLowerCase() : "";
  if (!["hide", "delete", "restore", "ban", "unban"].includes(action)) return adminSend(400, { ok: false, error: "action" });
  try {
    if (action === "hide" || action === "delete" || action === "restore" || (action === "ban" && id && !hash)) {
      if (!id) return adminSend(400, { ok: false, error: "id" });
      const row = await env.DB.prepare("SELECT id, ip_hash FROM shouts WHERE id = ?").bind(id).first();
      if (!row) return adminSend(404, { ok: false, error: "missing" });
      if (action === "ban") hash = row.ip_hash;
      if (action === "hide") {
        await env.DB.prepare("UPDATE shouts SET status = 'hidden' WHERE id = ?").bind(id).run();
      } else if (action === "restore") {
        await env.DB.prepare("UPDATE shouts SET status = 'visible', reports = 0 WHERE id = ?").bind(id).run();
      } else if (action === "delete") {
        await env.DB.batch([
          env.DB.prepare("DELETE FROM shout_reports WHERE shout_id = ?").bind(id),
          env.DB.prepare("DELETE FROM shouts WHERE id = ?").bind(id),
        ]);
      }
    }
    if (action === "ban" || action === "unban") {
      if (!/^[0-9a-f]{64}$/.test(hash)) return adminSend(400, { ok: false, error: "hash" });
      if (action === "ban") {
        await env.DB.prepare("INSERT OR REPLACE INTO shout_bans (ip_hash, created_at) VALUES (?, ?)").bind(hash, nowIso()).run();
        await env.DB.prepare("UPDATE shouts SET status = 'hidden' WHERE ip_hash = ? AND status = 'visible'").bind(hash).run();
      } else {
        await env.DB.prepare("DELETE FROM shout_bans WHERE ip_hash = ?").bind(hash).run();
      }
    }
    return adminSend(200, { ok: true, action });
  } catch {
    return adminSend(503, { ok: false, error: "offline" });
  }
}

export async function shouts(req, env, H) {
  const path = new URL(req.url).pathname;
  if (path === "/api/shouts/admin") return admin(req, env);
  if (req.method === "GET" || req.method === "HEAD") {
    if (path !== "/api/shouts") return H.send(req, 404, { ok: false, error: "Not found." });
    if (req.method === "HEAD") return new Response(null, { status: 200, headers: H.headers(req) });
    return list(req, env, H);
  }
  if (req.method === "POST") {
    if (path === "/api/shouts/report") return report(req, env, H);
    if (path === "/api/shouts") return create(req, env, H);
    return H.send(req, 404, { ok: false, error: "Not found." });
  }
  return H.send(req, 405, { ok: false, error: "Method not allowed." }, { Allow: "GET, POST, OPTIONS" });
}
