// The hot-wallet balance the policy reads. Electrum reports satoshis.
// hot_observed stores those satoshis. Nexa is divided by 100 when the policy
// and the public treasury compare it with the NEXA caps. A mint used to be
// the only writer, so the first mint always saw balance_unknown.

import { BCH_ELECTRUM, NEXA_ELECTRUM, electrumRequest } from "./broadcast.js";
import { bchAddress } from "./bch/sign.js";
import { displayAmount } from "./history.js";
import { recordSnapshot } from "./history.js";
import { nexaAddressOf } from "./nexa/message.js";
import { loadHotKey } from "./secrets.js";

export async function readObservedSats(env, chain) {
  if (!env || !env.DB) return null;
  const row = await env.DB.prepare("SELECT amount FROM hot_observed WHERE chain = ?").bind(chain).first();
  if (!row || row.amount == null) return null;
  const n = Number(row.amount);
  return Number.isFinite(n) ? n : null;
}

export async function writeObservedSats(db, chain, sats, at) {
  if (!db) return;
  await db.prepare(
    "INSERT INTO hot_observed (chain, amount, observed_at) VALUES (?, ?, ?) ON CONFLICT(chain) DO UPDATE SET amount = excluded.amount, observed_at = excluded.observed_at"
  ).bind(chain, sats, at).run();
}

export async function hotAddress(env, chain) {
  const named = chain === "nexa" ? env && env.NEXA_HOT_ADDRESS : env && env.BCH_HOT_ADDRESS;
  if (named && !String(named).startsWith("placeholder:")) return String(named).trim();
  const key = loadHotKey(env, chain);
  if (!key) return null;
  return chain === "nexa" ? nexaAddressOf(key) : bchAddress(key);
}

function asSats(value) {
  let n = null;
  if (typeof value === "bigint" || typeof value === "number") n = Number(value);
  else if (typeof value === "string" && /^-?\d+$/.test(value)) n = Number(value);
  return n != null && Number.isSafeInteger(n) ? n : null;
}

export async function fetchBalanceSats(chain, address, request = electrumRequest) {
  const urls = chain === "nexa" ? [NEXA_ELECTRUM] : BCH_ELECTRUM;
  for (const url of urls) {
    try {
      const res = await request(url, "blockchain.address.get_balance", [address]);
      if (!res || !res.ok || !res.result || typeof res.result !== "object") continue;
      const confirmed = asSats(res.result.confirmed);
      const unconfirmed = asSats(res.result.unconfirmed);
      if (confirmed == null || unconfirmed == null) continue;
      return Math.max(0, confirmed + unconfirmed);
    } catch {
      // The next URL, or a later cron, tries again.
    }
  }
  return null;
}

export async function observeChain(env, chain, request = electrumRequest, at = new Date().toISOString()) {
  if (!env || !env.DB) return { ok: false, reason: "no_db" };
  let address;
  try {
    address = await hotAddress(env, chain);
  } catch {
    return { ok: false, reason: "bad_key" };
  }
  if (!address) return { ok: false, reason: "no_address" };
  const sats = await fetchBalanceSats(chain, address, request);
  if (sats == null) return { ok: false, reason: "balance_unavailable" };
  await writeObservedSats(env.DB, chain, sats, at);
  await recordSnapshot(env.DB, chain, sats, at);
  return { ok: true, sats, display: displayAmount(chain, sats) };
}

export async function observeChains(env, request = electrumRequest) {
  const at = new Date().toISOString();
  const out = {};
  for (const chain of ["nexa", "bch"]) {
    out[chain] = await observeChain(env, chain, request, at);
  }
  return out;
}
