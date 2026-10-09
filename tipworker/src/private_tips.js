// Private tip inbox for Nordic Crypto (the /tip/ form). Free text, never a public GitHub issue.
//   POST /api/private-tip        tip (required, <=8000 chars), attachments (http/https links, newline/comma list or
//                                array, <=10), contact (optional, <=500), language, page, website (honeypot),
//                                cf-turnstile-response. JSON or form body, JSON answer with short error codes.
//   GET  /api/private-tips       list (Authorization: Bearer PRIVATE_TIPS_READ_TOKEN; no CORS) ?status=new|read|handled|all&limit=
//   POST /api/private-tips/:id   {status, editor_notes} (same bearer)
// Turnstile: TURNSTILE_SECRET (shared with the shoutbox). Without it the route answers 503 and stores nothing.
// Optional webhook after a stored tip: TIP_WEBHOOK_URL (https only) with TIP_WEBHOOK_BEARER.
// Privacy: never logs. The IP is only used for the shared salted, daily-rotating rate-limit hash (worker.js rateOk).
// Tests: TIP_TEST=1 accepts the Turnstile token "test-pass" and nothing else (never set in wrangler.toml).

export const PLIMITS = { maxBody: 32768, maxTip: 8000, maxContact: 500, maxNotes: 4000, maxLinks: 10, maxUrl: 2000 };
const STATUSES = ["new", "read", "handled"];
const PAGE_PATH = /^\/(?:[a-z]{2,8}\/)?tip\/?$/;
const enc = new TextEncoder();
const chars = (s) => [...s].length;
const ctrl = (s) => s.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "");
const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");
const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const COLS = "id, created_at, language, page, tip, contact, attachments, status, editor_notes";

export function goodUrl(s) {
  if (typeof s !== "string" || !s || s.length > PLIMITS.maxUrl || /\s/.test(s)) return false;
  let u;
  try { u = new URL(s); } catch { return false; }
  if (u.username || u.password) return false;
  if (u.protocol !== "http:" && u.protocol !== "https:") return false;
  if (!u.hostname || !u.hostname.includes(".") || u.hostname === "127.0.0.1") return false;
  return true;
}

// The page a tip came from: a /tip/ path, or the https URL of a tip page on one of the site origins.
export function pageOk(page, origins) {
  if (typeof page !== "string") return false;
  const p = page.trim();
  if (!p || p.length > 500) return false;
  if (PAGE_PATH.test(p)) return true;
  let u;
  try { u = new URL(p); } catch { return false; }
  if (u.protocol !== "https:" || u.username || u.password || u.search || u.hash) return false;
  if (!origins.has(u.origin)) return false;
  const path = u.hostname === "jqrgen.github.io" ? u.pathname.replace(/^\/nordic-crypto/, "") : u.pathname;
  return PAGE_PATH.test(path);
}

export function validatePrivateTip(f, origins) {
  if (!f || typeof f !== "object" || Array.isArray(f)) return [null, "bad_body"];
  const raw = (k) => (own(f, k) ? f[k] : "");
  const tipIn = raw("tip"), contactIn = raw("contact"), langIn = raw("language"), pageIn = raw("page"), attIn = raw("attachments");
  if (typeof tipIn !== "string" || typeof contactIn !== "string" || typeof langIn !== "string" || typeof pageIn !== "string") return [null, "bad_body"];
  const tip = ctrl(tipIn).trim();
  if (!tip) return [null, "empty_tip"];
  if (chars(tip) > PLIMITS.maxTip) return [null, "tip_long"];
  const contact = ctrl(contactIn).trim();
  if (chars(contact) > PLIMITS.maxContact) return [null, "bad_contact"];
  const language = langIn.trim().toLowerCase() || "en";
  if (!/^[a-z]{2,8}$/.test(language)) return [null, "bad_language"];
  const page = pageIn.trim();
  if (!pageOk(page, origins)) return [null, "bad_page"];
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
    if (attachments.length >= PLIMITS.maxLinks || !goodUrl(v)) return [null, "bad_attachment"];
    attachments.push(v);
  }
  return [{ tip, contact: contact || null, language, page, attachments }, null];
}

function safeEqual(a, b) {
  const aa = enc.encode(String(a)), bb = enc.encode(String(b));
  if (!aa.length || aa.length !== bb.length) return false;
  let d = 0;
  for (let i = 0; i < aa.length; i++) d |= aa[i] ^ bb[i];
  return d === 0;
}

async function turnstile(env, token) {
  if (env.TIP_TEST === "1") return token === "test-pass" ? "ok" : "bad";
  const secret = env.TURNSTILE_SECRET || "";
  if (!secret) return "unconfigured";
  if (!token || typeof token !== "string" || token.length > 2048) return "bad";
  try {
    const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ secret, response: token }),
    });
    if (!r.ok) return "offline";
    const j = await r.json();
    return j && j.success === true ? "ok" : "bad";
  } catch {
    return "offline";
  }
}

function rowOut(r) {
  let attachments = [];
  if (r.attachments) {
    try { const p = JSON.parse(r.attachments); if (Array.isArray(p)) attachments = p; } catch { /* show none */ }
  }
  return { id: r.id, created_at: r.created_at, language: r.language, page: r.page, tip: r.tip, contact: r.contact || null,
    attachments, status: r.status, editor_notes: r.editor_notes || null };
}

async function notify(env, tip) {
  const url = env.TIP_WEBHOOK_URL || "";
  let u;
  try { u = new URL(url); } catch { return; }
  if (u.protocol !== "https:") return;
  const headers = { "Content-Type": "application/json" };
  if (env.TIP_WEBHOOK_BEARER) headers.Authorization = "Bearer " + env.TIP_WEBHOOK_BEARER;
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 5000);
  try {
    await fetch(url, { method: "POST", headers, body: JSON.stringify({ event: "tip.created", tip }), signal: ac.signal });
  } catch { /* the tip is already stored */ } finally { clearTimeout(timer); }
}

async function readFields(req, H) {
  const ctype = (req.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  const cl = req.headers.get("Content-Length");
  if (cl !== null && !(Number(cl) <= PLIMITS.maxBody)) return { error: "too_long" };
  const raw = await H.readCapped(req, PLIMITS.maxBody);
  if (raw === null) return { error: "too_long" };
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(raw);
    if (ctype === "application/json") {
      const f = JSON.parse(text);
      if (f === null || typeof f !== "object" || Array.isArray(f)) return { error: "bad_body" };
      return { fields: f };
    }
    if (ctype === "application/x-www-form-urlencoded") {
      const f = Object.create(null);
      for (const [k, v] of new URLSearchParams(text)) if (!own(f, k)) f[k] = v;
      return { fields: f };
    }
    return { error: "bad_type" };
  } catch {
    return { error: "bad_body" };
  }
}

export async function postPrivateTip(req, env, H) {
  const origin = req.headers.get("Origin");
  if (origin !== null && !H.ORIGINS.has(origin)) return H.send(req, 403, { ok: false, error: "origin" });
  const parsed = await readFields(req, H);
  if (parsed.error) return H.send(req, parsed.error === "too_long" ? 413 : parsed.error === "bad_type" ? 415 : 400, { ok: false, error: parsed.error });
  const f = parsed.fields;
  const ip = (req.headers.get("CF-Connecting-IP") || "unknown").trim().slice(0, 64);
  try { if (!(await H.rateOk(env.DB, ip))) return H.send(req, 429, { ok: false, error: "rate" }); }
  catch { return H.send(req, 503, { ok: false, error: "offline" }); }
  const hp = f.website;  // honeypot filled in: pretend success, store nothing
  if (hp && (typeof hp !== "string" || hp.trim())) return H.send(req, 200, { ok: true });
  const [tip, err] = validatePrivateTip(f, H.ORIGINS);
  if (err) return H.send(req, 400, { ok: false, error: err });
  const token = typeof f["cf-turnstile-response"] === "string" ? f["cf-turnstile-response"] : (typeof f.turnstile === "string" ? f.turnstile : "");
  const gate = await turnstile(env, token);
  if (gate === "unconfigured" || gate === "offline") return H.send(req, 503, { ok: false, error: "offline" });
  if (gate !== "ok") return H.send(req, 400, { ok: false, error: "turnstile" });
  let row;
  try {
    row = await env.DB.prepare(
      `INSERT INTO private_tips (created_at, language, page, tip, contact, attachments, status) VALUES (?, ?, ?, ?, ?, ?, 'new') RETURNING ${COLS}`
    ).bind(nowIso(), tip.language, tip.page, tip.tip, tip.contact, tip.attachments.length ? JSON.stringify(tip.attachments) : null).first();
  } catch {
    return H.send(req, 503, { ok: false, error: "offline" });
  }
  if (!row) return H.send(req, 503, { ok: false, error: "offline" });
  await notify(env, rowOut(row));
  return H.send(req, 201, { ok: true, id: row.id });
}

// Bearer-only newsroom routes. No Access-Control-Allow-Origin: a browser on another site cannot read them.
function plain(code, obj) {
  return new Response(JSON.stringify(obj), { status: code, headers: {
    "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" } });
}
function authed(req, env) {
  const want = env.PRIVATE_TIPS_READ_TOKEN || "";
  if (!want) return "unconfigured";
  const m = (req.headers.get("Authorization") || "").match(/^Bearer\s+(\S+)\s*$/i);
  return m && safeEqual(m[1], want) ? "ok" : "unauthorized";
}

export async function listPrivateTips(req, env) {
  const auth = authed(req, env);
  if (auth !== "ok") return plain(auth === "unconfigured" ? 503 : 401, { ok: false, error: auth });
  const url = new URL(req.url);
  const status = url.searchParams.get("status") || "new";
  if (![...STATUSES, "all"].includes(status)) return plain(400, { ok: false, error: "bad_status" });
  let limit = Number(url.searchParams.get("limit") || "50");
  if (!Number.isInteger(limit) || limit < 1) limit = 50;
  limit = Math.min(limit, 200);
  const res = status === "all"
    ? await env.DB.prepare(`SELECT ${COLS} FROM private_tips ORDER BY id ASC LIMIT ?`).bind(limit).all()
    : await env.DB.prepare(`SELECT ${COLS} FROM private_tips WHERE status = ? ORDER BY id ASC LIMIT ?`).bind(status, limit).all();
  return plain(200, { ok: true, tips: (res.results || []).map(rowOut) });
}

export async function markPrivateTip(req, env, H, id) {
  const auth = authed(req, env);
  if (auth !== "ok") return plain(auth === "unconfigured" ? 503 : 401, { ok: false, error: auth });
  const parsed = await readFields(req, H);
  if (parsed.error) return plain(400, { ok: false, error: parsed.error });
  const body = parsed.fields;
  if (!own(body, "status") && !own(body, "editor_notes")) return plain(400, { ok: false, error: "bad_body" });
  const cur = await env.DB.prepare(`SELECT ${COLS} FROM private_tips WHERE id = ?`).bind(id).first();
  if (!cur) return plain(404, { ok: false, error: "not_found" });
  let status = cur.status, notes = cur.editor_notes;
  if (own(body, "status")) {
    if (!STATUSES.includes(body.status)) return plain(400, { ok: false, error: "bad_status" });
    status = body.status;
  }
  if (own(body, "editor_notes")) {
    if (body.editor_notes === null) notes = null;
    else if (typeof body.editor_notes !== "string" || chars(body.editor_notes) > PLIMITS.maxNotes) return plain(400, { ok: false, error: "bad_notes" });
    else notes = body.editor_notes;
  }
  await env.DB.prepare("UPDATE private_tips SET status = ?, editor_notes = ? WHERE id = ?").bind(status, notes, id).run();
  const row = await env.DB.prepare(`SELECT ${COLS} FROM private_tips WHERE id = ?`).bind(id).first();
  return plain(200, { ok: true, tip: rowOut(row) });
}
