// The hot key lives in the Worker secret binding (Cloudflare's secret store).
// A redeploy or a new isolate receives the same binding. The key is never written
// to D1, never returned, and never logged. Callers get a boolean and, separately,
// the public refill address.

const KEY = { nexa: "NEXA_HOT_KEY", bch: "BCH_HOT_KEY" };
const ADDR = { nexa: "NEXA_HOT_ADDRESS", bch: "BCH_HOT_ADDRESS" };

export function keyConfigured(env, chain) {
  const value = env && typeof env[KEY[chain]] === "string" ? env[KEY[chain]] : "";
  return value.length >= 32;
}

export function loadHotKey(env, chain) {
  // Returned only to the signer path, which this draft does not call.
  // Do not pass the result to JSON.stringify, console, or a Response.
  if (!keyConfigured(env, chain)) return null;
  return env[KEY[chain]];
}

export function keyFlags(env) {
  return { nexa: keyConfigured(env, "nexa"), bch: keyConfigured(env, "bch") };
}

export function refillAddress(env, chain, placeholder) {
  const value = env && typeof env[ADDR[chain]] === "string" ? env[ADDR[chain]].trim() : "";
  if (!value) return { address: placeholder, address_placeholder: true };
  return { address: value, address_placeholder: value.startsWith("placeholder:") };
}

export function publicHealth(env) {
  return { ok: true, service: "nordic-crypto-mint", keys: keyFlags(env), signs: false };
}
