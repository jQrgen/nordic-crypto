// Private tip intake for Nordic Crypto.
// POST /api/tip          public form (Turnstile) or onion forward (bearer ONION_INGEST_TOKEN)
// GET  /api/tips         list tips (Authorization: Bearer READ_TOKEN)
// POST /api/tips/:id     set status new|read|handled and editor notes (same bearer)
// GET  /api/health
//
// The IP is never stored. A hash of (short-lived salt + IP) is kept only for the rate-limit
// window, then deleted with the salt. No console logging. Observability is off in wrangler.toml.

import { strings } from "./copy.js";

const ORIGINS = new Set([
  "https://cryptonordic.no",
  "https://www.cryptonordic.no",
  "http://cryptonordic.no",
  "http://www.cryptonordic.no",
  "https://jqrgen.github.io",
]);
const MAX_BODY = 32768;
const MAX_TIP = 8000;
const MAX_CONTACT = 500;
const MAX_NOTES = 4000;
const MAX_LINKS = 10;
const MAX_URL = 2000;
const RATE_N = 5;
const ONION_N = 60;
const RATE_GLOBAL = 200;
const RATE_WINDOW = 600;
const PAGE_PATH = /^\/(?:[a-z]{2,8}\/tip\/?|tip\/?|[a-z]{2,8}\/?)$/;

const chars = (s) => [...s].length;
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");

export function safeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(String(a));
  const y = enc.encode(String(b));
  if (x.byteLength !== y.byteLength || x.byteLength === 0) return false;
  if (crypto.subtle && typeof crypto.subtle.timingSafeEqual === "function") return crypto.subtle.timingSafeEqual(x, y);
  if (typeof crypto.timingSafeEqual === "function") return crypto.timingSafeEqual(x, y);
  let d = 0;
  for (let i = 0; i < x.length; i++) d |= x[i] ^ y[i];
  return d === 0;
}

function bearer(req) {
  const h = req.headers.get("Authorization") || "";
  return h.startsWith("Bearer ") ? h.slice(7).trim() : "";
}

function originOk(origin, env) {
  if (!origin) return false;
  if (ORIGINS.has(origin)) return true;
  const extra = (env && env.EXTRA_ORIGINS) || "";
  return extra.split(",").map((s) => s.trim()).filter(Boolean).includes(origin);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function stripCtrl(s) {
  return s.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "");
}

export function goodUrl(s) {
  if (typeof s !== "string" || s.length === 0 || s.length > MAX_URL || /\s/.test(s)) return false;
  let u;
  try { u = new URL(s); } catch { return false; }
  if (u.username || u.password) return false;
  if (u.protocol !== "http:" && u.protocol !== "https:") return false;
  if (!u.hostname || u.hostname === "localhost" || u.hostname === "127.0.0.1") return false;
  return true;
}

export function pageOk(page) {
  if (typeof page !== "string") return false;
  const p = page.trim();
  if (!p || p.length > 500) return false;
  if (PAGE_PATH.test(p)) return true;
  let u;
  try { u = new URL(p); } catch { return false; }
  if (u.username || u.password || u.search || u.hash) return false;
  const host = u.hostname.toLowerCase();
  const path = u.pathname;
  if (host.endsWith(".onion")) {
    return u.protocol === "http:" && /^[a-z2-7]{56}\.onion$/.test(host) && /^\/(?:[a-z]{2,8}\/)?$/.test(path.endsWith("/") ? path : path + "/");
  }
  if (u.protocol !== "https:") return false;
  const site = host === "cryptonordic.no" || host === "www.cryptonordic.no" || host === "jqrgen.github.io";
  if (!site) return false;
  if (host === "jqrgen.github.io") {
    return /^\/nordic-crypto\/(?:[a-z]{2,8}\/)?tip\/?$/.test(path);
  }
  return /^\/(?:[a-z]{2,8}\/)?tip\/?$/.test(path);
}

export function validateTip(f) {
  if (!f || typeof f !== "object" || Array.isArray(f)) return [null, "bad_body"];
  const raw = (k) => (Object.prototype.hasOwnProperty.call(f, k) ? f[k] : "");
  const tipIn = raw("tip");
  const contactIn = raw("contact");
  const langIn = raw("language");
  const pageIn = raw("page");
  const attIn = raw("attachments");
  if (typeof tipIn !== "string" || typeof contactIn !== "string") return [null, "bad_body"];
  if (langIn !== "" && typeof langIn !== "string") return [null, "bad_body"];
  if (typeof pageIn !== "string") return [null, "bad_body"];
  const tip = stripCtrl(tipIn).trim();
  if (!tip) return [null, "empty_tip"];
  if (chars(tip) > MAX_TIP) return [null, "tip_long"];
  const contact = stripCtrl(contactIn).trim();
  if (chars(contact) > MAX_CONTACT) return [null, "bad_contact"];
  let lang = (typeof langIn === "string" ? langIn : "").trim().toLowerCase();
  if (!lang) lang = "en";
  if (!/^[a-z]{2,8}$/.test(lang)) return [null, "bad_language"];
  const page = pageIn.trim();
  if (!pageOk(page)) return [null, "bad_page"];
  let parts;
  if (attIn === "" || attIn == null) parts = [];
  else if (Array.isArray(attIn)) parts = attIn;
  else if (typeof attIn === "string") parts = attIn.split(/[\n,]+/);
  else return [null, "bad_attachment"];
  const attachments = [];
  for (const part of parts) {
    if (typeof part !== "string") return [null, "bad_attachment"];
    const v = part.trim();
    if (!v) continue;
    if (attachments.length >= MAX_LINKS || !goodUrl(v)) return [null, "bad_attachment"];
    attachments.push(v);
  }
  return [{
    tip,
    contact: contact || null,
    language: lang,
    page,
    attachments,
  }, null];
}

async function sha256(s) {
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
}

async function rateOk(db, key, limit) {
  const now = Math.floor(Date.now() / 1000);
  await db.prepare("DELETE FROM rate_hits WHERE ts <= ?").bind(now - RATE_WINDOW).run();
  let row = await db.prepare("SELECT salt, expires_at FROM rate_salt WHERE id = 1").first();
  if (!row || row.expires_at <= now) {
    const salt = hex(crypto.getRandomValues(new Uint8Array(32)));
    await db.prepare("DELETE FROM rate_hits").run();
    await db.prepare(
      "INSERT INTO rate_salt (id, salt, expires_at) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET salt = excluded.salt, expires_at = excluded.expires_at"
    ).bind(salt, now + RATE_WINDOW).run();
    row = { salt, expires_at: now + RATE_WINDOW };
  }
  const h = await sha256(row.salt + "|" + key);
  const mine = await db.prepare("SELECT COUNT(*) AS n FROM rate_hits WHERE h = ? AND ts > ?").bind(h, now - RATE_WINDOW).first();
  const total = await db.prepare("SELECT COUNT(*) AS n FROM rate_hits WHERE ts > ?").bind(now - RATE_WINDOW).first();
  if ((mine && mine.n >= limit) || (total && total.n >= RATE_GLOBAL)) return false;
  await db.prepare("INSERT INTO rate_hits (h, ts) VALUES (?, ?)").bind(h, now).run();
  return true;
}

async function readCapped(req, max) {
  if (!req.body) return new Uint8Array(0);
  const reader = req.body.getReader();
  const parts = [];
  let n = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    n += value.byteLength;
    if (n > max) { try { await reader.cancel(); } catch { /* already over the cap */ } return null; }
    parts.push(value);
  }
  const out = new Uint8Array(n);
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.byteLength; }
  return out;
}

async function readFields(req) {
  const cl = req.headers.get("Content-Length");
  if (cl !== null && !(Number(cl) <= MAX_BODY)) return { error: "too_long" };
  const raw = await readCapped(req, MAX_BODY);
  if (raw === null) return { error: "too_long" };
  let text;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(raw); }
  catch { return { error: "bad_body" }; }
  const ctype = (req.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  try {
    if (ctype === "application/json") {
      const j = JSON.parse(text || "null");
      if (!j || typeof j !== "object" || Array.isArray(j)) return { error: "bad_body" };
      return { fields: j, form: false };
    }
    if (ctype === "application/x-www-form-urlencoded") {
      const f = Object.create(null);
      for (const [k, v] of new URLSearchParams(text)) if (!Object.prototype.hasOwnProperty.call(f, k)) f[k] = v;
      return { fields: f, form: true };
    }
    return { error: "bad_type" };
  } catch { return { error: "bad_body" }; }
}

function baseHeaders(extra) {
  const h = new Headers({
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    ...extra,
  });
  return h;
}

function corsHeaders(req, env, extra) {
  const h = baseHeaders(extra);
  const o = req.headers.get("Origin");
  if (o && originOk(o, env)) {
    h.set("Access-Control-Allow-Origin", o);
    h.set("Vary", "Origin");
  }
  return h;
}

function json(req, env, code, obj, cors) {
  const headers = (cors ? corsHeaders(req, env, {}) : baseHeaders({}));
  headers.set("Content-Type", "application/json; charset=utf-8");
  return new Response(JSON.stringify(obj), { status: code, headers });
}

function backUrl(page) {
  if (typeof page !== "string" || !pageOk(page)) return "";
  if (page.startsWith("/")) {
    const path = page.endsWith("/") ? page : page + "/";
    if (path.includes("/tip")) return "https://cryptonordic.no" + path;
    return "";
  }
  const u = new URL(page);
  return u.origin + u.pathname + (u.pathname.endsWith("/") ? "" : "/");
}

function htmlPage(lang, ok, page) {
  const code = COPY_LANG(lang);
  const s = strings(code);
  const back = backUrl(page);
  const link = back ? `<p><a href="${esc(back)}">${esc(s.back)}</a></p>` : "";
  const heading = ok ? s.title : s.fail;
  const body = ok ? s.thanks : s.fail;
  return `<!doctype html>
<html lang="${esc(code)}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><meta name="robots" content="noindex">
<title>${esc(heading)}</title>
<style>html,body,p,a,h1{text-align:left}body{margin:0;padding:16px 20px;max-width:40rem;font:16px/1.5 sans-serif;background:#fff;color:#111}</style>
</head><body><h1>${esc(heading)}</h1><p>${esc(body)}</p>${link}</body></html>`;
}

function COPY_LANG(lang) {
  const k = String(lang || "").toLowerCase();
  return ["en", "nn", "nb", "sv", "da", "fi", "is"].includes(k) ? k : "en";
}

function html(lang, ok, page, status) {
  return new Response(htmlPage(lang, ok, page), {
    status: status || 200,
    headers: baseHeaders({
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'",
    }),
  });
}

function fail(req, env, parsed, lang, code, status) {
  if (parsed && parsed.form) return html(lang, false, "", status);
  return json(req, env, status, { ok: false, error: code }, true);
}

async function turnstile(env, token) {
  const secret = env.TURNSTILE_SECRET || "";
  if (!secret) return "unconfigured";
  if (!token || typeof token !== "string" || token.length > 2048) return "fail";
  try {
    const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ secret, response: token }),
    });
    if (!r.ok) return "offline";
    const j = await r.json();
    return j && j.success === true ? "ok" : "fail";
  } catch {
    return "offline";
  }
}

function onionAuthed(req, env) {
  const want = env.ONION_INGEST_TOKEN || "";
  const got = bearer(req);
  if (!want || !got) return false;
  if ((env.READ_TOKEN || "") && safeEqual(want, env.READ_TOKEN)) return false;
  return safeEqual(got, want);
}

function rowOut(r) {
  let attachments = [];
  if (r.attachments) {
    try {
      const p = JSON.parse(r.attachments);
      if (Array.isArray(p)) attachments = p;
    } catch { /* stored value was not a list; show none rather than the raw column */ }
  }
  return {
    id: r.id,
    created_at: r.created_at,
    language: r.language,
    page: r.page,
    tip: r.tip,
    contact: r.contact || null,
    attachments,
    status: r.status,
    editor_notes: r.editor_notes || null,
  };
}

async function notify(env, tip) {
  const url = env.TIP_WEBHOOK_URL || "";
  if (!url) return;
  let u;
  try { u = new URL(url); } catch { return; }
  if (u.protocol !== "https:") return;
  const headers = { "Content-Type": "application/json" };
  if (env.TIP_WEBHOOK_BEARER) headers.Authorization = "Bearer " + env.TIP_WEBHOOK_BEARER;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 5000);
  try {
    await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ event: "tip.created", tip }),
      signal: ctrl.signal,
    });
  } catch { /* the tip is already stored */ }
  finally { clearTimeout(timer); }
}

async function postTip(req, env) {
  const origin = req.headers.get("Origin");
  if (origin && !originOk(origin, env)) return json(req, env, 403, { ok: false, error: "origin" }, true);
  const parsed = await readFields(req);
  const langGuess = parsed.fields && typeof parsed.fields.language === "string" ? parsed.fields.language : "en";
  if (parsed.error) return fail(req, env, parsed, langGuess, parsed.error, parsed.error === "too_long" ? 413 : 400);
  const hp = parsed.fields.website;
  const onion = onionAuthed(req, env);
  const ip = (req.headers.get("CF-Connecting-IP") || "").trim().slice(0, 64);
  const key = onion ? "onion" : (ip || "unknown");
  try {
    if (!(await rateOk(env.DB, key, onion ? ONION_N : RATE_N))) {
      return fail(req, env, parsed, langGuess, "rate", 429);
    }
  } catch {
    return fail(req, env, parsed, langGuess, "offline", 503);
  }
  if (hp && (typeof hp !== "string" || hp.trim())) {
    return parsed.form ? html(langGuess, true, "") : json(req, env, 200, { ok: true }, true);
  }
  const [tip, err] = validateTip(parsed.fields);
  if (err) return fail(req, env, parsed, langGuess, err, 400);
  if (!onion) {
    const token = parsed.fields["cf-turnstile-response"] || parsed.fields.turnstile || "";
    const tv = await turnstile(env, typeof token === "string" ? token : "");
    if (tv === "unconfigured" || tv === "offline") return fail(req, env, parsed, tip.language, "offline", 503);
    if (tv !== "ok") return fail(req, env, parsed, tip.language, "turnstile", 400);
  }
  let id;
  try {
    const row = await env.DB.prepare(
      "INSERT INTO tips (created_at, language, page, tip, contact, attachments, status, editor_notes) VALUES (?, ?, ?, ?, ?, ?, 'new', NULL) RETURNING id"
    ).bind(nowIso(), tip.language, tip.page, tip.tip, tip.contact, tip.attachments.length ? JSON.stringify(tip.attachments) : null).first();
    id = row && row.id;
    if (!id) return fail(req, env, parsed, tip.language, "offline", 503);
  } catch {
    return fail(req, env, parsed, tip.language, "offline", 503);
  }
  const stored = await env.DB.prepare(
    "SELECT id, created_at, language, page, tip, contact, attachments, status, editor_notes FROM tips WHERE id = ?"
  ).bind(id).first();
  if (stored) await notify(env, rowOut(stored));
  if (parsed.form) return html(tip.language, true, tip.page, 201);
  return json(req, env, 201, { ok: true, id }, true);
}

function authed(req, env) {
  const want = env.READ_TOKEN || "";
  if (!want) return "unconfigured";
  const got = bearer(req);
  if (!got || !safeEqual(got, want)) return "unauthorized";
  return "ok";
}

async function listTips(req, env) {
  const auth = authed(req, env);
  if (auth !== "ok") return json(req, env, auth === "unconfigured" ? 503 : 401, { ok: false, error: auth }, false);
  const url = new URL(req.url);
  let status = url.searchParams.get("status") || "new";
  if (!["new", "read", "handled", "all"].includes(status)) return json(req, env, 400, { ok: false, error: "bad_status" }, false);
  let limit = Number(url.searchParams.get("limit") || "50");
  if (!Number.isInteger(limit) || limit < 1) limit = 50;
  if (limit > 200) limit = 200;
  const q = status === "all"
    ? "SELECT id, created_at, language, page, tip, contact, attachments, status, editor_notes FROM tips ORDER BY id ASC LIMIT ?"
    : "SELECT id, created_at, language, page, tip, contact, attachments, status, editor_notes FROM tips WHERE status = ? ORDER BY id ASC LIMIT ?";
  const stmt = status === "all" ? env.DB.prepare(q).bind(limit) : env.DB.prepare(q).bind(status, limit);
  const res = await stmt.all();
  const tips = (res.results || []).map(rowOut);
  return json(req, env, 200, { ok: true, tips }, false);
}

async function markTip(req, env, id) {
  const auth = authed(req, env);
  if (auth !== "ok") return json(req, env, auth === "unconfigured" ? 503 : 401, { ok: false, error: auth }, false);
  const parsed = await readFields(req);
  if (parsed.error || parsed.form) return json(req, env, 400, { ok: false, error: parsed.error || "bad_body" }, false);
  const body = parsed.fields;
  const cur = await env.DB.prepare(
    "SELECT id, created_at, language, page, tip, contact, attachments, status, editor_notes FROM tips WHERE id = ?"
  ).bind(id).first();
  if (!cur) return json(req, env, 404, { ok: false, error: "not_found" }, false);
  let status = cur.status;
  let notes = cur.editor_notes;
  if (Object.prototype.hasOwnProperty.call(body, "status")) {
    if (typeof body.status !== "string" || !["new", "read", "handled"].includes(body.status)) {
      return json(req, env, 400, { ok: false, error: "bad_status" }, false);
    }
    status = body.status;
  }
  if (Object.prototype.hasOwnProperty.call(body, "editor_notes")) {
    if (body.editor_notes === null) notes = null;
    else if (typeof body.editor_notes !== "string" || chars(body.editor_notes) > MAX_NOTES) {
      return json(req, env, 400, { ok: false, error: "bad_notes" }, false);
    } else notes = body.editor_notes;
  }
  if (!Object.prototype.hasOwnProperty.call(body, "status") && !Object.prototype.hasOwnProperty.call(body, "editor_notes")) {
    return json(req, env, 400, { ok: false, error: "bad_body" }, false);
  }
  await env.DB.prepare("UPDATE tips SET status = ?, editor_notes = ? WHERE id = ?").bind(status, notes, id).run();
  const row = await env.DB.prepare(
    "SELECT id, created_at, language, page, tip, contact, attachments, status, editor_notes FROM tips WHERE id = ?"
  ).bind(id).first();
  return json(req, env, 200, { ok: true, tip: rowOut(row) }, false);
}

export default {
  async fetch(req, env) {
    const path = new URL(req.url).pathname;
    if (req.method === "OPTIONS" && path === "/api/tip") {
      const o = req.headers.get("Origin");
      if (!o || !originOk(o, env)) return json(req, env, 403, { ok: false, error: "origin" }, true);
      const headers = corsHeaders(req, env, {
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Accept",
        "Access-Control-Max-Age": "86400",
      });
      return new Response(null, { status: 204, headers });
    }
    try {
      if (req.method === "GET" && path === "/api/health") {
        try {
          await env.DB.prepare("SELECT 1").first();
          return json(req, env, 200, { ok: true, service: "nordic-crypto-tip-intake" }, false);
        } catch {
          return json(req, env, 503, { ok: false, error: "offline" }, false);
        }
      }
      if (req.method === "GET" && path === "/api/tips") return await listTips(req, env);
      const one = path.match(/^\/api\/tips\/(\d+)$/);
      if (req.method === "POST" && one) return await markTip(req, env, Number(one[1]));
      if (req.method === "POST" && path === "/api/tip") return await postTip(req, env);
    } catch {
      return json(req, env, 503, { ok: false, error: "offline" }, false);
    }
    if (req.method !== "GET" && req.method !== "POST" && req.method !== "OPTIONS") {
      return json(req, env, 405, { ok: false, error: "method" }, false);
    }
    return json(req, env, 404, { ok: false, error: "not_found" }, false);
  },
};
