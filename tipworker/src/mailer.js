// Pluggable sender for the newsletter's confirmation and welcome emails. The provider is not chosen yet.
// Nothing is sent unless BOTH are set on the deployed Worker (jQrgen's decision):
//   MAIL_PROVIDER = "resend" | "webhook"     (default / unset: "none" – nothing is sent)
//   MAIL_SEND_ENABLED = "1"
// Provider settings (wrangler secrets / vars, never committed):
//   resend:  RESEND_API_KEY, MAIL_FROM_<SITE> e.g. MAIL_FROM_NORDIC_CRYPTO = "Nordic Crypto <FROM-ADDRESS>" (jQrgen chooses the address)
//   webhook: MAIL_WEBHOOK_URL (https), MAIL_WEBHOOK_TOKEN – POSTs {to, from, subject, text, site, lang, kind} as JSON, for
//            any other service (e.g. a small relay in front of Buttondown or Postmark).
// Buttondown / Substack: they run their own double opt-in, so with them this Worker would only collect confirmed
// addresses and tools export them (tipworker/export_subscribers.py → CSV import); no mail is sent from here.
// Test builds (SUBSCRIBE_TEST = "1", never in production) use the "test" provider, which only records the message in memory.
export const TEST_OUTBOX = [];

const fromFor = (env, site) => env["MAIL_FROM_" + site.toUpperCase().replace(/-/g, "_")] || env.MAIL_FROM || "";

const PROVIDERS = {
  none: async () => ({ sent: false, reason: "no provider configured" }),
  test: async (env, m) => { TEST_OUTBOX.push(m); if (TEST_OUTBOX.length > 50) TEST_OUTBOX.shift(); return { sent: false, reason: "test outbox" }; },
  resend: async (env, m) => {
    if (!env.RESEND_API_KEY || !fromFor(env, m.site)) return { sent: false, reason: "resend not configured" };
    const r = await fetch("https://api.resend.com/emails", { method: "POST",
      headers: { Authorization: "Bearer " + env.RESEND_API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ from: fromFor(env, m.site), to: [m.to], subject: m.subject, text: m.text,
        headers: m.unsubscribe ? { "List-Unsubscribe": `<${m.unsubscribe}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" } : undefined }) });
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
