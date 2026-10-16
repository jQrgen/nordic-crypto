// Private columnist applications (the /columnist/ form). Never a public GitHub issue.
//   POST /api/columnist  name (optional, <=80), email (required, reply address), languages (<=120), pitch (<=1500),
//                        sample (optional http/https link), why (<=800), language, website (honeypot), cf-turnstile-response.
//                        JSON or form body; JSON answer with short error codes.
// Turnstile (TURNSTILE_SECRET, shared with tips and the shoutbox) and the rate limit (scope 'columnist') as for private tips.
// Stored in D1 columnist_applications (migrations/0006_columnist.sql), then forwarded by email to COLUMNIST_TO
// (var or secret) from MAIL_FROM_NORDIC_CRYPTO with Reply-To = the applicant, through mailer.js. Mail obeys the same
// switches as the newsletter (MAIL_PROVIDER + MAIL_SEND_ENABLED); without them or without COLUMNIST_TO it is only stored.
// Privacy: never logs; the IP is only used for the salted daily rate-limit hash.
import { turnstile, readFields, goodUrl } from "./private_tips.js";
import { sendMail } from "./mailer.js";

export const CLIMITS = { name: 80, email: 254, languages: 120, pitch: 1500, sample: 300, why: 800 };
const chars = (s) => [...s].length;
const ctrl = (s) => s.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "");
const one = (s) => s.replace(/[\r\n]+/g, " ");
const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");
const EMAIL = /^[^\s@<>()",;:]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

export function validateColumnist(f) {
  if (!f || typeof f !== "object" || Array.isArray(f)) return [null, "bad_body"];
  const v = {};
  for (const k of ["name", "email", "languages", "pitch", "sample", "why", "language"]) {
    const x = Object.prototype.hasOwnProperty.call(f, k) ? f[k] : "";
    if (x != null && typeof x !== "string") return [null, "bad_body"];
    v[k] = ctrl(x || "").trim();
  }
  for (const k of ["name", "email", "languages", "sample"]) v[k] = one(v[k]);
  if (!EMAIL.test(v.email) || v.email.length > CLIMITS.email) return [null, "bad_email"];
  for (const k of ["languages", "pitch", "why"]) if (!v[k]) return [null, "empty"];
  for (const k of ["name", "languages", "pitch", "sample", "why"]) if (chars(v[k]) > CLIMITS[k]) return [null, "too_long"];
  if (v.sample && !goodUrl(v.sample)) return [null, "bad_link"];
  v.language = v.language.toLowerCase() || "en";
  if (!/^[a-z]{2,8}$/.test(v.language)) return [null, "bad_language"];
  return [{ ...v, name: v.name || null, sample: v.sample || null }, null];
}

export function columnistMail(a, id) {
  const subject = `Columnist application #${id}: ${a.name || a.email}`.slice(0, 180);
  const text = [`New columnist application #${id} (page language: ${a.language})`, "",
    `Name: ${a.name || "(not given)"}`, `Email: ${a.email}`, `Languages: ${a.languages}`, `Sample: ${a.sample || "(none)"}`, "",
    "Pitch / topic:", a.pitch, "", "Why Nordic Crypto:", a.why, "",
    "Reply to this email to answer the applicant directly. Stored privately in D1 (columnist_applications)."].join("\n");
  return { subject, text };
}

export async function postColumnist(req, env, H) {
  const origin = req.headers.get("Origin");
  if (origin !== null && !H.ORIGINS.has(origin)) return H.send(req, 403, { ok: false, error: "origin" });
  const parsed = await readFields(req, H);
  if (parsed.error) return H.send(req, parsed.error === "too_long" ? 413 : parsed.error === "bad_type" ? 415 : 400, { ok: false, error: parsed.error });
  const f = parsed.fields;
  const hp = f.website;  // honeypot filled in: pretend success, store nothing
  if (hp && (typeof hp !== "string" || hp.trim())) return H.send(req, 200, { ok: true });
  const [a, err] = validateColumnist(f);
  if (err) return H.send(req, 400, { ok: false, error: err });
  const token = typeof f["cf-turnstile-response"] === "string" ? f["cf-turnstile-response"] : "";
  const gate = await turnstile(env, token);
  if (gate === "unconfigured" || gate === "offline") return H.send(req, 503, { ok: false, error: "offline" });
  if (gate !== "ok") return H.send(req, 400, { ok: false, error: "turnstile" });
  const ip = (req.headers.get("CF-Connecting-IP") || "unknown").trim().slice(0, 64);
  try { if (!(await H.rateOk(env.DB, ip, "columnist", 3))) return H.send(req, 429, { ok: false, error: "rate" }); }
  catch { return H.send(req, 503, { ok: false, error: "offline" }); }
  let row;
  try {
    row = await env.DB.prepare("INSERT INTO columnist_applications (created_at, language, name, email, languages, pitch, sample, why) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id")
      .bind(nowIso(), a.language, a.name, a.email, a.languages, a.pitch, a.sample, a.why).first();
  } catch { return H.send(req, 503, { ok: false, error: "offline" }); }
  if (!row) return H.send(req, 503, { ok: false, error: "offline" });
  const to = (env.COLUMNIST_TO || "").trim();
  if (to) {
    const r = await sendMail(env, { to, site: "nordic-crypto", lang: "en", kind: "columnist", replyTo: a.email, ...columnistMail(a, row.id) });
    if (r.sent) { try { await env.DB.prepare("UPDATE columnist_applications SET emailed = 1 WHERE id = ?").bind(row.id).run(); } catch { /* stored */ } }
  }
  return H.send(req, 201, { ok: true });
}
