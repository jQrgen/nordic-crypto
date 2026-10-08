// Testnet UTXOs for the hot address. The client does not supply these.
// A missing authority output, a missing fund, or a node error returns null
// and the mint stops. Mainnet URLs are not used.

import { GroupToken } from "libnexa-ts";
import caps from "../caps.json" with { type: "json" };
import { BCH_ELECTRUM, NEXA_ELECTRUM, electrumRequest } from "./broadcast.js";
import { bchAddress } from "./bch/sign.js";
import { recordLedger, refillFromTx } from "./history.js";
import { nexaAddressOf } from "./nexa/message.js";

const AUTHORITY = GroupToken.authFlags.AUTHORITY;

function rowsOf(result) {
  if (Array.isArray(result)) return result;
  if (result && Array.isArray(result.unspent)) return result.unspent;
  return [];
}

function tokenOf(row) {
  if (row.token_data) {
    const nft = row.token_data.nft || {};
    return {
      id: String(row.token_data.category || "").replace(/^0x/i, "").toLowerCase(),
      group: null,
      amount: row.token_data.amount,
      capability: nft.capability || null,
    };
  }
  const id = String(row.token_id_hex || row.token_id || "").replace(/^0x/i, "").toLowerCase();
  const group = row.group ? String(row.group) : "";
  if (!id && !group && row.token_amount == null && row.group_quantity == null) return null;
  let capability = null;
  if (row.token_bitfield != null) {
    const cap = Number(row.token_bitfield) & 3;
    capability = cap === 2 ? "minting" : cap === 1 ? "mutable" : "none";
  }
  return { id, group, amount: row.token_amount ?? row.group_quantity, capability };
}

function exactAmount(raw) {
  if (typeof raw === "bigint") return raw;
  if (typeof raw === "string" && /^-?\d+$/.test(raw)) return BigInt(raw);
  if (typeof raw === "number" && Number.isSafeInteger(raw)) return BigInt(raw);
  return null;
}

function hasAuthority(amount) {
  return amount !== null && (amount & AUTHORITY) === AUTHORITY;
}

async function firstOk(urls, method, params, request) {
  let last = null;
  for (const url of urls) {
    const res = await request(url, method, params);
    if (res && res.ok) return res;
    last = res;
  }
  return last;
}

async function nexaUtxos(env, secret, request) {
  const parent = String(env.NEXA_PARENT_GROUP || "");
  if (!parent) return null;
  const address = nexaAddressOf(secret);
  const tokens = await request(NEXA_ELECTRUM, "token.address.listunspent", [address, null]);
  const coins = await request(NEXA_ELECTRUM, "blockchain.address.listunspent", [address, "exclude_tokens"]);
  if (!tokens || !tokens.ok || !coins || !coins.ok) return null;
  const parentKey = parent.toLowerCase();
  let authority = null;
  for (const row of rowsOf(tokens.result)) {
    const token = tokenOf(row);
    if (!token || !row.outpoint_hash) continue;
    const id = token.id.toLowerCase();
    const group = String(token.group || "").toLowerCase();
    if (id !== parentKey && group !== parentKey) continue;
    const amount = exactAmount(token.amount);
    if (!hasAuthority(amount)) continue;
    authority = { outpoint: row.outpoint_hash, satoshis: Number(row.value), groupAmount: amount.toString() };
    break;
  }
  if (!authority) return null;
  const need = caps.nexa.airdrop * 100 + caps.nexa.network * 100 + 546 * 3;
  const funds = [];
  let sum = 0;
  const plain = rowsOf(coins.result).filter((row) => row.outpoint_hash && row.value != null);
  plain.sort((a, b) => Number(b.value) - Number(a.value));
  for (const row of plain) {
    funds.push({ outpoint: row.outpoint_hash, satoshis: Number(row.value) });
    sum += Number(row.value);
    if (sum >= need || funds.length >= 8) break;
  }
  if (sum < need) return null;
  return { authority, funds };
}

async function bchUtxos(env, secret, request) {
  const category = String(env.BCH_CATEGORY || "").replace(/^0x/i, "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(category)) return null;
  const address = await bchAddress(secret);
  const listed = await firstOk(BCH_ELECTRUM, "blockchain.address.listunspent", [address, "include_tokens"], request);
  if (!listed || !listed.ok) return null;
  const rows = rowsOf(listed.result);
  let minting = null;
  for (const row of rows) {
    const token = tokenOf(row);
    if (!token || token.capability !== "minting") continue;
    if (token.id !== category) continue;
    if (!row.tx_hash || row.tx_pos == null) continue;
    minting = { txid: row.tx_hash, vout: row.tx_pos, satoshis: Number(row.value) };
    break;
  }
  if (!minting) return null;
  const need = 800 + caps.bch.airdrop + Math.min(400, caps.bch.network) + 546;
  const plain = rows.filter((row) => !tokenOf(row) && row.tx_hash && row.tx_pos != null);
  plain.sort((a, b) => Number(b.value) - Number(a.value));
  const funding = plain.find((row) => Number(row.value) >= need);
  if (!funding) return null;
  return {
    minting,
    funding: { txid: funding.tx_hash, vout: funding.tx_pos, satoshis: Number(funding.value) },
  };
}

// Rostrum's verbose transaction reports `value` in NEXA, with up to two
// decimal places. get_balance on the same server reports satoshis. A whole
// number of NEXA (100) would otherwise be stored as 100 sats.
const NEXA_SATS = 100;

function nexaOutputSats(value) {
  if (typeof value === "string" && /^-?\d+(\.\d{1,2})?$/.test(value)) {
    const neg = value.startsWith("-");
    const body = neg ? value.slice(1) : value;
    const [whole, frac = ""] = body.split(".");
    const sats = Number(whole) * NEXA_SATS + Number((frac + "00").slice(0, 2));
    if (!Number.isSafeInteger(sats)) return null;
    return neg ? -sats : sats;
  }
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const sats = Math.round(value * NEXA_SATS);
  if (!Number.isSafeInteger(sats) || Math.abs(value * NEXA_SATS - sats) > 1e-6) return null;
  return sats;
}

export function nexaVerboseToSatoshis(tx) {
  if (!tx || typeof tx !== "object") return null;
  const outputs = tx.vout || tx.outputs;
  if (!Array.isArray(outputs)) return null;
  const vout = [];
  for (const output of outputs) {
    const sats = nexaOutputSats(output && output.value);
    if (sats == null) return null;
    vout.push({ ...output, value: sats });
  }
  return { ...tx, vout };
}

export async function syncChainRefills(db, chain, address, request = electrumRequest) {
  if (!db || !address) return;
  const urls = chain === "nexa" ? [NEXA_ELECTRUM] : BCH_ELECTRUM;
  for (const url of urls) {
    const hist = await request(url, "blockchain.address.get_history", [address]);
    if (!hist || !hist.ok || !Array.isArray(hist.result)) continue;
    for (const item of hist.result.slice(-40)) {
      const txid = item && (item.tx_hash || item.txid);
      if (!txid) continue;
      const got = await request(url, "blockchain.transaction.get", [txid, true]);
      if (!got || !got.ok) continue;
      const tx = chain === "nexa" ? nexaVerboseToSatoshis(got.result) : got.result;
      const row = refillFromTx(tx, address);
      if (!row) continue;
      await recordLedger(db, { txid: row.txid, chain, kind: "refill", amount: row.amount, at: row.at, event_id: null });
    }
    return;
  }
}

export async function lookupUtxos(env, chain, secret, request = electrumRequest) {
  try {
    if (chain === "nexa") return await nexaUtxos(env, secret, request);
    if (chain === "bch") return await bchUtxos(env, secret, request);
  } catch {
    return null;
  }
  return null;
}
