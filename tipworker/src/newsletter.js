// Newsletter signup (double opt-in) for Nordic Crypto and Kryptonytt. Used by worker.js.
//   POST /api/subscribe       JSON or form: email, site (nordic-crypto | kryptonytt), lang, website (honeypot).
//                             Always the same answer for a valid request (202 {"ok":true,"pending":true}, or 303 to the
//                             site's newsletter page ?sent=1), whether the address is new, pending or already confirmed,
//                             so the endpoint can't be used to find out who subscribes.
//   GET  /api/confirm?token=…&s=<site>&l=<lang>   confirms a pending signup (token valid 7 days) -> 303 ?confirmed=1
//   GET  /api/unsubscribe?id=…&sig=…&s=&l=        small page with a button (so mail scanners can't unsubscribe people)
//   POST /api/unsubscribe?id=…&sig=…              unsubscribes (also RFC 8058 one-click) -> 303 ?unsubscribed=1 / 200
// Stored per signup: email, site, lang, status, SHA-256 of the confirmation token, timestamps. No IP, no user agent.
// Unsubscribe links: sig = HMAC-SHA-256(UNSUB_SECRET, "id|email|site"), nothing stored. Mail goes through mailer.js
// (provider not chosen; default sends nothing).
import { SITES, pageUrl, confirmEmail, welcomeEmail, text } from "./messages.js";
import { sendMail, providerName } from "./mailer.js";

const MAX_BODY = 2048, TOKEN_TTL = 7 * 86400, RESEND_AFTER = 600;
const EMAIL_RE = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@(?=.{4,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$/;
const enc = new TextEncoder();
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const sha256 = async (s) => hex(await crypto.subtle.digest("SHA-256", enc.encode(s)));
const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");
const now = () => Math.floor(Date.now() / 1000);

export function validateSignup(f) {
  const g = (k) => { const v = Object.prototype.hasOwnProperty.call(f, k) ? f[k] : ""; return typeof v === "string" ? v.trim() : null; };
  const email = g("email"), site = g("site"), lang0 = g("lang");
  if ([email, site, lang0].includes(null)) return [null, "invalid"];
  if (!Object.prototype.hasOwnProperty.call(SITES, site)) return [null, "site"];
  const lang = lang0 || SITES[site].def;
  if (!Object.prototype.hasOwnProperty.call(SITES[site].langs, lang)) return [null, "lang"];
  if (!email) return [null, "email"];
  if (email.length > 254 || !EMAIL_RE.test(email) || email.includes("..")) return [null, "email"];
  return [{ email: email.toLowerCase(), site, lang }, null];
}

async function hmac(secret, msg) {
  const k = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, enc.encode(msg))).slice(0, 40);
}
const sameStr = (a, b) => { if (a.length !== b.length) return false; let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i); return d === 0; };
export async function unsubscribeUrl(env, origin, row) {
  if (!env.UNSUB_SECRET) return null;
  const sig = await hmac(env.UNSUB_SECRET, `${row.id}|${row.email}|${row.site}`);
  return `${origin}/api/unsubscribe?` + new URLSearchParams({ id: String(row.id), sig, s: row.site, l: row.lang });
}

const siteLang = (q) => {   // site + lang from the query, for redirects; falls back to Nordic Crypto English
  const s = Object.prototype.hasOwnProperty.call(SITES, q.get("s") || "") ? q.get("s") : "nordic-crypto";
  const l = Object.prototype.hasOwnProperty.call(SITES[s].langs, q.get("l") || "") ? q.get("l") : SITES[s].def;
  return [s, l];
};

export async function subscribe(req, env, h) {
  const origin = req.headers.get("Origin");
  if (origin !== null && !h.ORIGINS.has(origin)) return h.send(req, 403, { ok: false, error: "origin" });
  const ctype = (req.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  const isForm = ctype === "application/x-www-form-urlencoded";
  const wantsJson = (req.headers.get("Accept") || "").includes("application/json") || !isForm;
  let back = pageUrl("nordic-crypto", "en");
  const out = (code, q) => (wantsJson ? h.send(req, code, { ok: code < 300, ...(q.error ? { error: q.error } : {}), ...(q.extra || {}) })
    : new Response(null, { status: 303, headers: h.headers(req, { Location: back + "?" + new URLSearchParams(q.error ? { error: q.error } : { sent: "1" }) }) }));
  const cl = req.headers.get("Content-Length");
  if (cl !== null && !(Number(cl) <= MAX_BODY)) return out(413, { error: "too_long" });
  const raw = await h.readCapped(req, MAX_BODY);
  if (raw === null) return out(413, { error: "too_long" });
  let f;
  try {
    const t = new TextDecoder("utf-8", { fatal: true }).decode(raw);
    if (ctype === "application/json") { f = JSON.parse(t); if (f === null || typeof f !== "object" || Array.isArray(f)) throw 0; }
    else if (isForm) { f = Object.create(null); for (const [k, v] of new URLSearchParams(t)) if (!(k in f)) f[k] = v; }
    else return out(415, { error: "content_type" });
  } catch { return out(400, { error: "invalid" }); }
  if (typeof f.site === "string" && SITES[f.site]) {
    const l = typeof f.lang === "string" && Object.prototype.hasOwnProperty.call(SITES[f.site].langs, f.lang) ? f.lang : SITES[f.site].def;
    back = pageUrl(f.site, l);
  }
  const hp = f.website;
  if (hp && (typeof hp !== "string" || hp.trim())) return out(202, { extra: { pending: true } });   // honeypot: pretend, store nothing
  const [s, err] = validateSignup(f);
  if (err) return out(400, { error: err });
  const ip = (req.headers.get("CF-Connecting-IP") || "unknown").trim().slice(0, 64);
  try { if (!(await h.rateOk(env.DB, "subscribe|" + ip))) return out(429, { error: "rate" }); }
  catch { return out(503, { error: "offline" }); }
  const t = now(), extra = { pending: true };
  try {
    const db = env.DB;
    await db.prepare("DELETE FROM subscribers WHERE status = 'pending' AND token_expires < ?").bind(t).run();
    const row = await db.prepare("SELECT id, status, last_sent_at FROM subscribers WHERE email = ? AND site = ?").bind(s.email, s.site).first();
    const fresh = !row || row.status === "unsubscribed" || (row.status === "pending" && !(row.last_sent_at > t - RESEND_AFTER));
    if (fresh) {
      const token = hex(crypto.getRandomValues(new Uint8Array(32))), th = await sha256(token);
      if (row) await db.prepare("UPDATE subscribers SET status = 'pending', lang = ?, token_hash = ?, token_expires = ?, last_sent_at = ?, unsubscribed_at = NULL WHERE id = ?")
        .bind(s.lang, th, t + TOKEN_TTL, t, row.id).run();
      else await db.prepare("INSERT INTO subscribers (email, site, lang, status, token_hash, token_expires, last_sent_at, created_at) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)")
        .bind(s.email, s.site, s.lang, th, t + TOKEN_TTL, t, nowIso()).run();
      const link = `${new URL(req.url).origin}/api/confirm?` + new URLSearchParams({ token, s: s.site, l: s.lang });
      const m = confirmEmail(s.site, s.lang, link);
      await sendMail(env, { to: s.email, site: s.site, lang: s.lang, kind: "confirm", ...m });
      if (providerName(env) === "test") extra.test_token = token;
    }
  } catch { return out(503, { error: "offline" }); }
  return out(202, { extra });
}

export async function confirm(req, env, h) {
  const q = new URL(req.url).searchParams, [site, lang] = siteLang(q), token = q.get("token") || "";
  const go = (k) => new Response(null, { status: 303, headers: h.headers(req, { Location: pageUrl(site, lang) + "?" + k }) });
  if (!/^[0-9a-f]{64}$/.test(token)) return go("error=invalid_link");
  let row;
  try {
    row = await env.DB.prepare("UPDATE subscribers SET status = 'confirmed', confirmed_at = ?, token_hash = NULL, token_expires = NULL " +
      "WHERE token_hash = ? AND status = 'pending' AND token_expires >= ? RETURNING id, email, site, lang").bind(nowIso(), await sha256(token), now()).first();
  } catch { return go("error=offline"); }
  if (!row) return go("error=invalid_link");
  const unsub = await unsubscribeUrl(env, new URL(req.url).origin, row);
  if (unsub) await sendMail(env, { to: row.email, site: row.site, lang: row.lang, kind: "welcome", unsubscribe: unsub, ...welcomeEmail(row.site, row.lang, unsub) });
  return new Response(null, { status: 303, headers: h.headers(req, { Location: pageUrl(row.site, row.lang) + "?confirmed=1" }) });
}

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
async function checkSig(env, q) {
  const id = Number(q.get("id")), sig = q.get("sig") || "";
  if (!env.UNSUB_SECRET || !Number.isInteger(id) || id <= 0 || !/^[0-9a-f]{40}$/.test(sig)) return null;
  const row = await env.DB.prepare("SELECT id, email, site, lang, status FROM subscribers WHERE id = ?").bind(id).first();
  if (!row) return null;
  return sameStr(await hmac(env.UNSUB_SECRET, `${row.id}|${row.email}|${row.site}`), sig) ? row : null;
}

export async function unsubscribe(req, env, h) {
  const u = new URL(req.url), q = u.searchParams, [site, lang] = siteLang(q);
  if (req.method === "POST") {
    const origin = req.headers.get("Origin");
    if (origin !== null && origin !== "null" && !h.ORIGINS.has(origin) && origin !== u.origin) return h.send(req, 403, { ok: false });
    const raw = await h.readCapped(req, MAX_BODY); const body = raw ? new TextDecoder().decode(raw) : "";
    const oneClick = /List-Unsubscribe=One-Click/i.test(body);
    let row;
    try { row = await checkSig(env, q); } catch { return h.send(req, 503, { ok: false }); }
    if (!row) return oneClick ? h.send(req, 400, { ok: false }) : new Response(null, { status: 303, headers: h.headers(req, { Location: pageUrl(site, lang) + "?error=invalid_link" }) });
    await env.DB.prepare("UPDATE subscribers SET status = 'unsubscribed', unsubscribed_at = ?, token_hash = NULL, token_expires = NULL WHERE id = ?")
      .bind(nowIso(), row.id).run();
    return oneClick ? h.send(req, 200, { ok: true }) : new Response(null, { status: 303, headers: h.headers(req, { Location: pageUrl(row.site, row.lang) + "?unsubscribed=1" }) });
  }
  let row = null; try { row = await checkSig(env, q); } catch {}
  const v = { name: SITES[site].name };
  const body = row
    ? `<p>${esc(text(lang, "uq", v))}</p><form method="post" action="${esc(u.pathname + u.search)}"><button type="submit">${esc(text(lang, "ub", v))}</button></form>`
    : `<p>${esc(text(lang, "ux", v))}</p>`;
  return new Response(`<!doctype html><html lang="${esc(lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>${esc(text(lang, "ut", v))} – ${esc(v.name)}</title>` +
    `<style>body{font:16px/1.5 system-ui,sans-serif;max-width:560px;margin:40px auto;padding:0 16px}button{font-size:16px;padding:8px 14px}</style></head><body><h1>${esc(v.name)}</h1>${body}` +
    `<p><a href="${esc(SITES[site].base + (SITES[site].langs[lang] ?? ""))}">${esc(SITES[site].base)}</a></p></body></html>`,
    { status: row ? 200 : 400, headers: h.headers(req, { "Content-Type": "text/html; charset=utf-8", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'" }) });
}
