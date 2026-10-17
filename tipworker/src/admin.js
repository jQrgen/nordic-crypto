// Private admin API for /admin/ on the site. Used by worker.js.
//   POST /api/admin/login       {email}  -> always 202 {"ok":true} (same answer for every address, no enumeration). Only
//                               an address whose domain is exactly ADMIN_EMAIL_DOMAIN (default nordiccrypto.no) gets a
//                               one-time link, valid 15 minutes, single use. Rate-limited per IP (scope "admin") and per address.
//   POST /api/admin/verify      {token}  -> 200 {"ok":true, token, email, expires} – a bearer session token (7 days).
//                               POST, not GET: the link points at the site (…/admin/#t=…) and the page posts the token, so
//                               mail scanners that prefetch links never burn it, and the token is never in a server log.
//   POST /api/admin/logout      (bearer) -> deletes the session.
//   GET  /api/admin/me          (bearer) -> {"ok":true, email}
//   GET  /api/admin/subscribers (bearer) -> every subscriber with the issues each has received.
//   POST /api/admin/deliveries  (bearer ADMIN_DELIVERY_TOKEN, a secret) {deliveries:[{subscriber_id, issue}]} – used by
//                               newsletter/send_issue.py when it is not writing to D1 directly.
// Why bearer and not a cookie: the page is on nordiccrypto.no and the Worker on workers.dev, a different site; browsers
// (Safari, Firefox strict, Chrome's third-party-cookie limits) drop cross-site cookies. CORS here allows only ADMIN_ORIGIN.
import { sendMail } from "./mailer.js";

export const LOGIN_TTL = 15 * 60, SESSION_TTL = 7 * 86400, PER_EMAIL_N = 3, ADMIN_RATE_N = 5;
export const ADMIN_ORIGIN = "https://nordiccrypto.no";
const enc = new TextEncoder();
const hex = (b) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
export const sha256 = async (s) => hex(await crypto.subtle.digest("SHA-256", enc.encode(s)));
const b64url = (u8) => btoa(String.fromCharCode(...u8)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
export const newToken = () => b64url(crypto.getRandomValues(new Uint8Array(32)));
const now = () => Math.floor(Date.now() / 1000);
const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");
const LOCAL_RE = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}$/;

export const adminDomain = (env) => String((env && env.ADMIN_EMAIL_DOMAIN) || "nordiccrypto.no").trim().toLowerCase();

// Returns the lower-cased address when it is allowed, else null. Exactly one "@", a plain local part, and a domain that
// equals the admin domain exactly: no subdomains (x@a.nordiccrypto.no), no lookalikes (x@evil-nordiccrypto.no,
// x@nordiccrypto.no.evil.com), no trailing dot, no display names or whitespace.
export function allowedAdmin(email, env) {
  if (typeof email !== "string") return null;
  const e = email.trim().toLowerCase();
  if (e.length > 254 || /\s/.test(e)) return null;
  const parts = e.split("@");
  if (parts.length !== 2) return null;
  const [local, domain] = parts;
  if (!LOCAL_RE.test(local) || local.startsWith(".") || local.endsWith(".") || local.includes("..")) return null;
  const want = adminDomain(env);
  if (!want || domain !== want) return null;
  return e;
}

function cors(req, extra = {}) {
  const h = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", ...extra });
  if (req.headers.get("Origin") === ADMIN_ORIGIN) { h.set("Access-Control-Allow-Origin", ADMIN_ORIGIN); h.set("Vary", "Origin"); }
  return h;
}
const json = (req, code, obj) => new Response(JSON.stringify(obj), { status: code, headers: cors(req, { "Content-Type": "application/json; charset=utf-8" }) });

export function adminPreflight(req) {
  if (req.headers.get("Origin") !== ADMIN_ORIGIN) return json(req, 403, { ok: false });
  return new Response(null, { status: 204, headers: cors(req, { "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization", "Access-Control-Max-Age": "600" }) });
}

async function body(req, h) {
  const raw = await h.readCapped(req, 1024);
  if (raw === null) return null;
  try { const f = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw)); return f && typeof f === "object" && !Array.isArray(f) ? f : null; }
  catch { return null; }
}
const bearer = (req) => { const m = (req.headers.get("Authorization") || "").match(/^Bearer ([A-Za-z0-9_-]{20,200})$/); return m ? m[1] : null; };
const sameStr = (a, b) => { if (a.length !== b.length) return false; let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i); return d === 0; };

export async function session(req, env) {
  const t = bearer(req); if (!t) return null;
  const row = await env.DB.prepare("SELECT email, expires_at FROM admin_sessions WHERE token_hash = ?").bind(await sha256(t)).first();
  if (!row || row.expires_at <= now()) return null;
  return allowedAdmin(row.email, env) ? row : null;   // domain changed since login -> session no longer valid
}

export function loginEmail(link) {
  return { subject: "Nordic Crypto admin sign-in link",
    text: `Sign in to the Nordic Crypto admin page:\n\n${link}\n\nThe link works once and expires in 15 minutes. If you did not ask for it, ignore this email.\n` };
}

async function login(req, env, h) {
  const origin = req.headers.get("Origin");
  if (origin !== null && origin !== ADMIN_ORIGIN) return json(req, 403, { ok: false });
  const generic = () => json(req, 202, { ok: true, message: "If that address may sign in, a link is on its way." });
  const f = await body(req, h);
  if (!f) return json(req, 400, { ok: false, error: "invalid" });
  const ip = (req.headers.get("CF-Connecting-IP") || "unknown").trim().slice(0, 64);
  try { if (!(await h.rateOk(env.DB, ip, "admin", ADMIN_RATE_N))) return json(req, 429, { ok: false, error: "rate" }); }
  catch { return json(req, 503, { ok: false }); }
  const email = allowedAdmin(f.email, env);
  if (!email) return generic();
  const t = now();
  await env.DB.prepare("DELETE FROM admin_login_tokens WHERE expires_at < ?").bind(t - 86400).run();
  const c = await env.DB.prepare("SELECT COUNT(*) AS n FROM admin_login_tokens WHERE email = ? AND created_at > ?").bind(email, t - LOGIN_TTL).first();
  if (c.n >= PER_EMAIL_N) return generic();   // per-address cap, silent (no enumeration)
  const token = newToken();
  await env.DB.prepare("INSERT INTO admin_login_tokens (token_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)")
    .bind(await sha256(token), email, t, t + LOGIN_TTL).run();
  const link = `${ADMIN_ORIGIN}/admin/#t=${token}`;
  await sendMail(env, { to: email, site: "nordic-crypto", lang: "en", kind: "admin-login", ...loginEmail(link) });
  return generic();
}

async function verify(req, env, h) {
  if (req.headers.get("Origin") !== null && req.headers.get("Origin") !== ADMIN_ORIGIN) return json(req, 403, { ok: false });
  const f = await body(req, h);
  const tok = f && typeof f.token === "string" && /^[A-Za-z0-9_-]{20,200}$/.test(f.token) ? f.token : null;
  const bad = () => json(req, 401, { ok: false, error: "The link is invalid, used or expired. Ask for a new one." });
  if (!tok) return bad();
  const t = now(), th = await sha256(tok);
  // Single use: the UPDATE only succeeds once, even for two concurrent requests.
  const u = await env.DB.prepare("UPDATE admin_login_tokens SET used_at = ? WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?").bind(t, th, t).run();
  if (!u.meta || u.meta.changes !== 1) return bad();
  const row = await env.DB.prepare("SELECT email FROM admin_login_tokens WHERE token_hash = ?").bind(th).first();
  const email = row && allowedAdmin(row.email, env);
  if (!email) return bad();
  const st = newToken();
  await env.DB.batch([
    env.DB.prepare("DELETE FROM admin_sessions WHERE expires_at <= ?").bind(t),
    env.DB.prepare("INSERT INTO admin_sessions (token_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)").bind(await sha256(st), email, t, t + SESSION_TTL),
    env.DB.prepare("INSERT INTO admin_logins (email, at) VALUES (?, ?)").bind(email, nowIso()),
  ]);
  return json(req, 200, { ok: true, token: st, email, expires: t + SESSION_TTL });
}

async function logout(req, env) {
  const t = bearer(req);
  if (t) await env.DB.prepare("DELETE FROM admin_sessions WHERE token_hash = ?").bind(await sha256(t)).run();
  return json(req, 200, { ok: true });
}

export async function listSubscribers(env) {
  const subs = (await env.DB.prepare("SELECT id, email, site, lang, status, created_at, confirmed_at, unsubscribed_at FROM subscribers ORDER BY id").all()).results || [];
  const dels = (await env.DB.prepare("SELECT subscriber_id, issue, sent_at FROM newsletter_deliveries ORDER BY issue").all()).results || [];
  const by = new Map();
  for (const d of dels) { if (!by.has(d.subscriber_id)) by.set(d.subscriber_id, []); by.get(d.subscriber_id).push(d.issue); }
  const rows = subs.map((s) => { const issues = by.get(s.id) || []; return { ...s, issues, last_issue: issues.length ? Math.max(...issues) : null }; });
  const totals = { all: rows.length, pending: 0, confirmed: 0, unsubscribed: 0, deliveries: dels.length };
  for (const r of rows) if (r.status in totals) totals[r.status]++;
  const last = dels.length ? Math.max(...dels.map((d) => d.issue)) : null;
  return { rows, totals, last_issue: last };
}

async function recordDeliveries(req, env, h) {
  const t = bearer(req), secret = env.ADMIN_DELIVERY_TOKEN || "";
  if (!t || secret.length < 32 || !sameStr(t, secret)) return json(req, 401, { ok: false });
  const raw = await h.readCapped(req, 65536);
  let f; try { f = JSON.parse(new TextDecoder().decode(raw)); } catch { return json(req, 400, { ok: false }); }
  const list = f && Array.isArray(f.deliveries) ? f.deliveries : null;
  if (!list || list.length > 500 || !list.every((d) => Number.isInteger(d.subscriber_id) && Number.isInteger(d.issue) && d.issue > 0 && d.issue < 100000))
    return json(req, 400, { ok: false });
  const at = nowIso();
  if (list.length) await env.DB.batch(list.map((d) => env.DB.prepare("INSERT OR IGNORE INTO newsletter_deliveries (subscriber_id, issue, sent_at) VALUES (?, ?, ?)").bind(d.subscriber_id, d.issue, at)));
  return json(req, 200, { ok: true, recorded: list.length });
}

export async function admin(req, env, h, path) {
  try {
    if (req.method === "OPTIONS") return adminPreflight(req);
    if (req.method === "POST" && path === "/api/admin/login") return await login(req, env, h);
    if (req.method === "POST" && path === "/api/admin/verify") return await verify(req, env, h);
    if (req.method === "POST" && path === "/api/admin/logout") return await logout(req, env);
    if (req.method === "POST" && path === "/api/admin/deliveries") return await recordDeliveries(req, env, h);
    if (req.method === "GET" && (path === "/api/admin/me" || path === "/api/admin/subscribers")) {
      const s = await session(req, env);
      if (!s) return json(req, 401, { ok: false, error: "auth" });
      if (path === "/api/admin/me") return json(req, 200, { ok: true, email: s.email });
      return json(req, 200, { ok: true, email: s.email, ...(await listSubscribers(env)) });
    }
    return json(req, 404, { ok: false });
  } catch { return json(req, 503, { ok: false }); }
}
