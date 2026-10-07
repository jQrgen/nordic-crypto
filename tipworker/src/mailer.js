// Pluggable sender for the newsletter's confirmation and welcome emails.
// Issue mail is sent by newsletter/send_issue.py (same provider names and env vars). Nothing is sent unless BOTH are set
// on the deployed Worker (jQrgen's decision):
//   MAIL_PROVIDER = "resend" | "mailgun" | "webhook"     (default / unset: "none" – nothing is sent)
//   MAIL_SEND_ENABLED = "1"
// Provider settings (wrangler secrets / vars, never committed; placeholders only):
//   resend:  RESEND_API_KEY, MAIL_FROM_<SITE> e.g. MAIL_FROM_NORDIC_CRYPTO = "Nordic Crypto <FROM-ADDRESS>"
//   mailgun: MAILGUN_API_KEY, MAILGUN_DOMAIN, optional MAILGUN_API_BASE (default https://api.mailgun.net)
//   webhook: MAIL_WEBHOOK_URL (https), MAIL_WEBHOOK_TOKEN – POSTs {to, from, subject, text, html, site, lang, kind} as JSON
// Cloudflare Email Routing receives mail for the domain. It does not send this list. See newsletter/email-list.md.
// Test builds (SUBSCRIBE_TEST = "1", never in production) use the "test" provider, which only records the message in memory.
export const TEST_OUTBOX = [];

const fromFor = (env, site) => env["MAIL_FROM_" + site.toUpperCase().replace(/-/g, "_")] || env.MAIL_FROM || "";

const PROVIDERS = {
  none: async () => ({ sent: false, reason: "no provider configured" }),
  test: async (env, m) => { TEST_OUTBOX.push(m); if (TEST_OUTBOX.length > 50) TEST_OUTBOX.shift(); return { sent: false, reason: "test outbox" }; },
  resend: async (env, m) => {
    if (!env.RESEND_API_KEY || !fromFor(env, m.site)) return { sent: false, reason: "resend not configured" };
    const payload = { from: fromFor(env, m.site), to: [m.to], subject: m.subject, text: m.text };
    if (m.html) payload.html = m.html;
    if (m.unsubscribe) payload.headers = { "List-Unsubscribe": `<${m.unsubscribe}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" };
    const r = await fetch("https://api.resend.com/emails", { method: "POST",
      headers: { Authorization: "Bearer " + env.RESEND_API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify(payload) });
    return { sent: r.ok, reason: r.ok ? "" : "provider error " + r.status };
  },
  mailgun: async (env, m) => {
    const from = fromFor(env, m.site), domain = env.MAILGUN_DOMAIN, key = env.MAILGUN_API_KEY;
    if (!key || !domain || !from) return { sent: false, reason: "mailgun not configured" };
    const base = (env.MAILGUN_API_BASE || "https://api.mailgun.net").replace(/\/$/, "");
    const body = new URLSearchParams({ from, to: m.to, subject: m.subject, text: m.text || "" });
    if (m.html) body.set("html", m.html);
    if (m.unsubscribe) {
      body.set("h:List-Unsubscribe", `<${m.unsubscribe}>`);
      body.set("h:List-Unsubscribe-Post", "List-Unsubscribe=One-Click");
    }
    const r = await fetch(`${base}/v3/${domain}/messages`, { method: "POST",
      headers: { Authorization: "Basic " + btoa("api:" + key) }, body });
    return { sent: r.ok, reason: r.ok ? "" : "provider error " + r.status };
  },
  webhook: async (env, m) => {
    if (!env.MAIL_WEBHOOK_URL || !/^https:\/\//.test(env.MAIL_WEBHOOK_URL)) return { sent: false, reason: "webhook not configured" };
    const r = await fetch(env.MAIL_WEBHOOK_URL, { method: "POST",
      headers: { Authorization: "Bearer " + (env.MAIL_WEBHOOK_TOKEN || ""), "Content-Type": "application/json" },
      body: JSON.stringify({ ...m, from: fromFor(env, m.site) }) });
    return { sent: r.ok, reason: r.ok ? "" : "provider error " + r.status };
  },
};

export function providerName(env) {
  if (env && env.SUBSCRIBE_TEST === "1") return "test";
  const p = ((env && env.MAIL_PROVIDER) || "none").toLowerCase();
  if (!(p in PROVIDERS) || p === "test") return "none";
  return env.MAIL_SEND_ENABLED === "1" ? p : "none";
}

// m = {to, site, lang, kind: "confirm"|"welcome", subject, text, unsubscribe?}. Never throws; never logs.
export async function sendMail(env, m) {
  try { return await PROVIDERS[providerName(env)](env, m); } catch { return { sent: false, reason: "send failed" }; }
}
