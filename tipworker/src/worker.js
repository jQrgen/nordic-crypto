// Nordic Crypto tip intake – Cloudflare Worker + D1. Port of tipserver/server.py (same fields, validation, honeypot,
// limits and responses).
//   POST /api/tip     JSON or form fields: url (required, http/https), country (NO/SE/DK/FI/IS/unsure), note (<=1000 chars),
//                     name (optional, <=100 chars), website (honeypot: must be empty). Stored in D1 as status 'pending'.
//   GET  /api/health  {"ok": true, "service": "nordic-crypto-tips"}
//   GET  /api/geo     {"country": "NO"} – only the two-letter country code Cloudflare already attaches to the request
//                     (request.cf.country), or null. Used once by the site's language picker. Nothing is stored or logged,
//                     Cache-Control: no-store, CORS only for the public site origin and https://jqrgen.github.io. For local tests only, the header
//                     X-Test-Country is honoured when the variable GEO_TEST is "1" (never set in wrangler.toml / production).
// Privacy: never logs anything (no console.* calls, observability off in wrangler.toml); the IP is never stored – only a
// SHA-256 of (daily random salt + IP) is kept for the 10-minute rate-limit window (see migrations/0001_tips.sql).
// No user agent or other metadata is stored. Body capped at 4 KB.
// CORS: the public site origin (site_url.json), www, the country domains (apex and www) and
// https://jqrgen.github.io. A browser POST from any other Origin is refused (403).
// Newsletter signup (Nordic Crypto + Kryptonytt, double opt-in): POST /api/subscribe, GET /api/confirm, GET/POST
// /api/unsubscribe – see src/newsletter.js (D1 table subscribers, migrations/0003_subscribers.sql) and src/mailer.js.
// Shoutbox (one shared room, every language): GET/POST /api/shouts, POST /api/shouts/report,
// GET/POST /api/shouts/admin – see src/shouts.js (migrations/0004_shouts.sql).
import { subscribe, confirm, unsubscribe } from "./newsletter.js";
import { shouts } from "./shouts.js";
import siteUrl from "../../site_url.json" with { type: "json" };

const SITE_BASE = siteUrl.base.endsWith("/") ? siteUrl.base : siteUrl.base + "/";
const SITE_ORIGIN = new URL(SITE_BASE).origin;
// github.io stays allowed so Kryptonytt, which still lives there, can post.
const COUNTRY_ORIGINS = ["se", "fi", "dk", "is"].flatMap((cc) => [`https://nordiccrypto.${cc}`, `https://www.nordiccrypto.${cc}`]);
const ORIGINS = new Set([SITE_ORIGIN, "https://www.nordiccrypto.no", ...COUNTRY_ORIGINS, "https://jqrgen.github.io"]);
const THANKS = SITE_BASE + "tip/";
const MAX_BODY = 4096, MAX_NOTE = 1000, MAX_NAME = 100, MAX_URL = 2000;
const COUNTRIES = new Set(["NO", "SE", "DK", "FI", "IS", "UNSURE"]);
const RATE_N = 5, RATE_WINDOW = 600;   // max 5 tips per IP per 10 minutes
const RATE_GLOBAL_N = 200;             // and max 200 tips per 10 minutes in total (spam flood guard)

const clen = (s) => [...s].length;     // code points, like Python len()
const ctrl = (s) => s.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "");
const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");

export function validate(f) {
  const g = (k) => {
    const v = Object.prototype.hasOwnProperty.call(f, k) ? f[k] : "";
    if (typeof v !== "string") return null;
    return (v || "").trim();
  };
  let url = g("url"), country = g("country") || "unsure", note = g("note"), name = g("name");
  if ([url, country, note, name].includes(null)) return [null, "Invalid field type."];
  if (!url) return [null, "Please enter the article URL."];
  let host = "";
  if (/^https?:\/\//i.test(url) && !/\s/.test(url) && url.length <= MAX_URL) {
    try { host = new URL(url).hostname; } catch { host = ""; }
  }
  if (!host || !host.includes(".")) return [null, "The URL must be a full http:// or https:// link."];
  const m = country.toUpperCase().match(/\b(NO|SE|DK|FI|IS)\b/);
  country = m ? m[1] : country.toUpperCase().replace("NOT SURE", "UNSURE");
  if (!COUNTRIES.has(country)) return [null, "Country must be NO, SE, DK, FI, IS or unsure."];
  if (clen(note) > MAX_NOTE) return [null, `The note can be at most ${MAX_NOTE} characters.`];
  if (clen(name) > MAX_NAME) return [null, `The name can be at most ${MAX_NAME} characters.`];
  return [{ url: ctrl(url), country: country === "UNSURE" ? "unsure" : country, note: ctrl(note), name: ctrl(name) || null }, null];
}

const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

async function rateOk(db, ip) {
  const now = Math.floor(Date.now() / 1000), day = new Date().toISOString().slice(0, 10);
  const fresh = hex(crypto.getRandomValues(new Uint8Array(32)));
  await db.batch([
    db.prepare("DELETE FROM rate_hits WHERE ts <= ?").bind(now - RATE_WINDOW),
    db.prepare("DELETE FROM rate_salt WHERE day <> ?").bind(day),
    db.prepare("INSERT OR IGNORE INTO rate_salt (day, salt) VALUES (?, ?)").bind(day, fresh),
  ]);
  const row = await db.prepare("SELECT salt FROM rate_salt WHERE day = ?").bind(day).first();
  const h = hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(row.salt + "|" + ip)));
  const c = await db.prepare("SELECT (SELECT COUNT(*) FROM rate_hits WHERE h = ?1 AND ts > ?2) AS mine, (SELECT COUNT(*) FROM rate_hits WHERE ts > ?2) AS total")
    .bind(h, now - RATE_WINDOW).first();
  if (c.mine >= RATE_N || c.total >= RATE_GLOBAL_N) return false;
  await db.prepare("INSERT INTO rate_hits (h, ts) VALUES (?, ?)").bind(h, now).run();
  return true;
}

function headers(req, extra = {}) {
  const h = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", ...extra });
  const o = req.headers.get("Origin");
  if (o && ORIGINS.has(o)) { h.set("Access-Control-Allow-Origin", o); h.set("Vary", "Origin"); }
  return h;
}
const send = (req, code, obj, extra) =>
  new Response(JSON.stringify(obj ?? {}), { status: code, headers: headers(req, { "Content-Type": "application/json; charset=utf-8", ...(extra || {}) }) });
const redirect = (req, q) =>
  new Response(null, { status: 303, headers: headers(req, { Location: THANKS + "?" + new URLSearchParams(q).toString() }) });

async function readCapped(req, max = MAX_BODY) {  // returns Uint8Array or null if larger than max
  if (!req.body) return new Uint8Array(0);
  const reader = req.body.getReader(); const parts = []; let n = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    n += value.byteLength;
    if (n > max) { try { await reader.cancel(); } catch {} return null; }
    parts.push(value);
  }
  const out = new Uint8Array(n); let o = 0; for (const p of parts) { out.set(p, o); o += p.byteLength; }
  return out;
}

async function tip(req, env) {
  const origin = req.headers.get("Origin");
  if (origin !== null && !ORIGINS.has(origin)) return send(req, 403, { ok: false, error: "Origin not allowed." });
  const ctype = (req.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  const isForm = ctype === "application/x-www-form-urlencoded";
  const wantsJson = (req.headers.get("Accept") || "").includes("application/json") || !isForm;
  const fail = (code, msg) => (wantsJson ? send(req, code, { ok: false, error: msg }) : redirect(req, { error: msg }));
  const cl = req.headers.get("Content-Length");
  if (cl !== null && !(Number(cl) <= MAX_BODY)) return fail(413, "The tip is too long (max 4 KB).");
  const raw = await readCapped(req);
  if (raw === null) return fail(413, "The tip is too long (max 4 KB).");
  const ip = (req.headers.get("CF-Connecting-IP") || "unknown").trim().slice(0, 64);
  try { if (!(await rateOk(env.DB, ip))) return fail(429, "Too many tips from you in a short time. Please try again later."); }
  catch { return fail(503, "The tip service is temporarily offline, try again later."); }
  let f;
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(raw);
    if (ctype === "application/json") {
      f = JSON.parse(text);
      if (f === null || typeof f !== "object" || Array.isArray(f)) throw new Error("not an object");
    } else if (isForm) {
      f = Object.create(null); for (const [k, v] of new URLSearchParams(text)) if (!Object.prototype.hasOwnProperty.call(f, k)) f[k] = v;
    } else return fail(415, "Send JSON or form data.");
  } catch { return fail(400, "Could not read the tip."); }
  const hp = f.website;  // honeypot filled in: pretend success, store nothing
  if (hp && (typeof hp !== "string" || hp.trim())) return wantsJson ? send(req, 200, { ok: true }) : redirect(req, { sent: "1" });
  const [t, err] = validate(f);
  if (err) return fail(400, err);
  try {
    await env.DB.prepare("INSERT INTO tips (created_at, url, country, note, name) VALUES (?, ?, ?, ?, ?)")
      .bind(nowIso(), t.url, t.country, t.note, t.name).run();
  } catch { return fail(503, "The tip service is temporarily offline, try again later."); }
  return wantsJson ? send(req, 201, { ok: true }) : redirect(req, { sent: "1" });
}

export function geo(req, env) {
  let c = req.cf && typeof req.cf.country === "string" ? req.cf.country : null;
  if (env && env.GEO_TEST === "1" && req.headers.get("X-Test-Country") !== null) c = req.headers.get("X-Test-Country");
  c = (c || "").toUpperCase();
  return /^[A-Z]{2}$/.test(c) && c !== "XX" && c !== "T1" ? c : null;   // XX = unknown, T1 = Tor (Cloudflare codes)
}

const H = { ORIGINS, send, headers, readCapped, rateOk };

export default {
  async fetch(req, env) {
    const path = new URL(req.url).pathname;
    if (req.method === "OPTIONS") {
      const o = req.headers.get("Origin");
      const preflight = ["/api/tip", "/api/subscribe", "/api/shouts", "/api/shouts/report"];
      if (!preflight.includes(path) || (o !== null && !ORIGINS.has(o))) return send(req, 403, { ok: false });
      const methods = path === "/api/shouts" ? "GET, POST, OPTIONS" : "POST, OPTIONS";
      return new Response(null, { status: 204, headers: headers(req, {
        "Access-Control-Allow-Methods": methods, "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400" }) });
    }
    if (req.method === "GET" || req.method === "HEAD") {
      if (path === "/api/shouts" || path === "/api/shouts/admin") return shouts(req, env, H);
      if (path === "/api/geo") return send(req, 200, { country: geo(req, env) });
      if ((path === "/api/confirm" || path === "/api/unsubscribe") && req.method === "HEAD") return new Response(null, { status: 200, headers: headers(req) });  // HEAD never acts
      if (path === "/api/confirm") return confirm(req, env, H);
      if (path === "/api/unsubscribe") return unsubscribe(req, env, H);
      if (path === "/api/health") {
        try { await env.DB.prepare("SELECT 1").first(); return send(req, 200, { ok: true, service: "nordic-crypto-tips" }); }
        catch { return send(req, 503, { ok: false }); }
      }
      return send(req, 404, { ok: false, error: "Not found." });
    }
    if (req.method === "POST") {
      if (path === "/api/shouts" || path === "/api/shouts/report" || path === "/api/shouts/admin") return shouts(req, env, H);
      if (path === "/api/subscribe") return subscribe(req, env, H);
      if (path === "/api/unsubscribe") return unsubscribe(req, env, H);
      if (path !== "/api/tip") return send(req, 404, { ok: false, error: "Not found." });
      return tip(req, env);
    }
    return send(req, 405, { ok: false, error: "Method not allowed." }, { Allow: "GET, POST, OPTIONS" });
  },
};
