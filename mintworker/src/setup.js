// Create the Nexa group or the CashTokens category on the hot key.
// Testnet and chipnet only. The caller records the public id in D1.
// The key is read from the Worker secret and is not returned.

import { BCH_ELECTRUM, NEXA_ELECTRUM, broadcastBch, broadcastNexa, electrumRequest } from "./broadcast.js";
import { bchAddress, signBchGenesis, signBchToSelf } from "./bch/sign.js";
import { wifVersion } from "./bch/crypto.js";
import { nexaAddressOf } from "./nexa/message.js";
import { signNexaGroup } from "./nexa/sign.js";
import { loadHotKey, signingEnabled } from "./secrets.js";

export const BCH_GENESIS_MIN = 800 + 546 + 400;
export const BCH_PREP_MIN = BCH_GENESIS_MIN + 400;
export const NEXA_MIN = 5000;

const PUBLIC_FIELDS = ["ok", "reason", "chain", "public_id", "txid", "prep_txid", "have_sats", "need_sats", "detail"];

export function networkFromArgs(argv) {
  return argv.includes("--mainnet") ? "mainnet" : "testnet";
}

export function chainsFromArgs(argv) {
  const i = argv.indexOf("--chain");
  if (i < 0) return ["nexa", "bch"];
  const value = argv[i + 1];
  if (value === "nexa" || value === "bch") return [value];
  if (value === "both") return ["nexa", "bch"];
  const err = new Error("bad_chain");
  err.code = "bad_chain";
  throw err;
}

export function assertOperatorNetwork(argv, operator) {
  if (operator !== "yes") {
    const err = new Error("not_operator");
    err.code = "not_operator";
    throw err;
  }
  if (argv.includes("--mainnet")) {
    const err = new Error("mainnet_blocked");
    err.code = "mainnet_blocked";
    throw err;
  }
  return "testnet";
}

export function isMainnetAddress(chain, address) {
  const value = String(address || "").trim();
  if (!value) return false;
  if (chain === "nexa") return value.startsWith("nexa:");
  if (chain === "bch") return value.startsWith("bitcoincash:");
  return false;
}

function configuredVar(env, chain) {
  const raw = chain === "nexa" ? env && env.NEXA_PARENT_GROUP : env && env.BCH_CATEGORY;
  if (typeof raw !== "string") return "";
  const value = raw.trim();
  if (!value || value.startsWith("placeholder:")) return "";
  return value;
}

async function readRecorded(env, chain) {
  if (!env || !env.DB) return null;
  try {
    const row = await env.DB.prepare(
      "SELECT public_id, txid FROM token_setup WHERE chain = ?"
    ).bind(chain).first();
    if (!row || !row.public_id) return null;
    return { public_id: String(row.public_id), txid: row.txid ? String(row.txid) : null };
  } catch {
    return null;
  }
}

export async function schemaReady(env) {
  if (!env || !env.DB) return false;
  try {
    await env.DB.prepare("SELECT public_id FROM token_setup WHERE chain = ?").bind("nexa").first();
    return true;
  } catch {
    return false;
  }
}

export async function tokenConfig(env, chain) {
  const fromVar = configuredVar(env, chain);
  if (fromVar) return { public_id: fromVar, txid: null, source: "var" };
  const row = await readRecorded(env, chain);
  if (!row) return null;
  return { public_id: row.public_id, txid: row.txid, source: "d1" };
}

function rowsOf(result) {
  if (Array.isArray(result)) return result;
  if (result && Array.isArray(result.unspent)) return result.unspent;
  return [];
}

function nexaCoins(result) {
  return rowsOf(result)
    .filter((row) => row && row.outpoint_hash && row.value != null)
    .map((row) => ({ outpoint: String(row.outpoint_hash), satoshis: Number(row.value) }))
    .filter((row) => row.satoshis > 0);
}

function bchCoins(result) {
  return rowsOf(result)
    .filter((row) => row && row.tx_hash && row.tx_pos != null && row.value != null && !row.token_data && row.token_amount == null)
    .map((row) => ({ txid: String(row.tx_hash), vout: Number(row.tx_pos), satoshis: Number(row.value) }))
    .filter((row) => row.satoshis > 0);
}

async function defaultList(chain, address) {
  if (chain === "nexa") {
    const res = await electrumRequest(NEXA_ELECTRUM, "blockchain.address.listunspent", [address, "exclude_tokens"]);
    return res && res.ok ? nexaCoins(res.result) : null;
  }
  let last = null;
  for (const url of BCH_ELECTRUM) {
    const res = await electrumRequest(url, "blockchain.address.listunspent", [address]);
    if (res && res.ok) return bchCoins(res.result);
    last = res;
  }
  return last && last.ok ? bchCoins(last.result) : null;
}

async function defaultBroadcast(chain, hex) {
  return chain === "nexa" ? broadcastNexa(hex) : broadcastBch(hex);
}

function hotFromKey(chain, secret) {
  if (chain === "bch" && !/^[0-9a-fA-F]{64}$/.test(String(secret).trim())) {
    if (wifVersion(secret) === 0x80) {
      const err = new Error("mainnet_blocked");
      err.code = "mainnet_blocked";
      throw err;
    }
  }
  if (chain === "nexa") {
    const address = nexaAddressOf(secret);
    if (!address.startsWith("nexatest:")) {
      const err = new Error("mainnet_blocked");
      err.code = "mainnet_blocked";
      throw err;
    }
    return address;
  }
  const address = bchAddress(secret, { prefix: "bchtest", tokenSupport: true });
  if (!String(address).startsWith("bchtest:")) {
    const err = new Error("mainnet_blocked");
    err.code = "mainnet_blocked";
    throw err;
  }
  return address;
}

function namedAddress(env, chain) {
  const raw = chain === "nexa" ? env && env.NEXA_HOT_ADDRESS : env && env.BCH_HOT_ADDRESS;
  if (typeof raw !== "string") return "";
  const value = raw.trim();
  if (!value || value.startsWith("placeholder:")) return "";
  return value;
}

function publicResult(result) {
  const out = {};
  for (const key of PUBLIC_FIELDS) {
    if (result[key] != null && result[key] !== "") out[key] = result[key];
  }
  if (!("ok" in out)) out.ok = false;
  return out;
}

function scrub(result, secret) {
  const out = publicResult(result);
  const text = JSON.stringify(out);
  if (secret && text.includes(String(secret).trim())) return { ok: false, reason: "failed", chain: result.chain };
  return out;
}

async function remember(env, chain, publicId, txid) {
  await env.DB.prepare(
    "INSERT INTO token_setup (chain, public_id, txid, created_at) VALUES (?, ?, ?, ?)"
  ).bind(chain, publicId, txid, new Date().toISOString()).run();
}

function unfunded(chain, have, need, detail) {
  return { ok: false, reason: "unfunded", chain, have_sats: have, need_sats: need, detail };
}

async function createNexa({ secret, hot, list, broadcast }) {
  const coins = await list("nexa", hot);
  if (!coins) return { ok: false, reason: "utxo_unavailable", chain: "nexa" };
  const have = coins.reduce((sum, coin) => sum + coin.satoshis, 0);
  const coin = coins.sort((a, b) => b.satoshis - a.satoshis)[0];
  if (!coin || coin.satoshis < NEXA_MIN) return unfunded("nexa", have, NEXA_MIN, have ? "too_small" : "no_coins");
  let signed;
  try {
    signed = signNexaGroup({ secret, utxo: coin, network: "testnet" });
  } catch (e) {
    return { ok: false, reason: e && e.code ? e.code : "sign_failed", chain: "nexa" };
  }
  if (!String(signed.group).startsWith("nexatest:")) return { ok: false, reason: "mainnet_blocked", chain: "nexa" };
  const sent = await broadcast("nexa", signed.hex);
  if (!sent || !sent.ok) return { ok: false, reason: "broadcast_rejected", chain: "nexa" };
  return { ok: true, chain: "nexa", public_id: signed.group, txid: signed.txid };
}

async function createBch({ secret, hot, list, broadcast }) {
  const coins = await list("bch", hot);
  if (!coins) return { ok: false, reason: "utxo_unavailable", chain: "bch" };
  const have = coins.reduce((sum, coin) => sum + coin.satoshis, 0);
  let funding = coins.find((row) => row.vout === 0 && row.satoshis >= BCH_GENESIS_MIN);
  let prepTxid = null;
  if (!funding) {
    const source = coins.filter((row) => row.satoshis >= BCH_PREP_MIN).sort((a, b) => b.satoshis - a.satoshis)[0];
    if (!source) {
      const need = coins.length ? BCH_PREP_MIN : BCH_GENESIS_MIN;
      return unfunded("bch", have, need, coins.length ? "no_vout0" : "no_coins");
    }
    let prep;
    try {
      prep = signBchToSelf({ secret, funding: source, prefix: "bchtest" });
    } catch (e) {
      return { ok: false, reason: e && e.code ? e.code : "sign_failed", chain: "bch" };
    }
    if (!String(prep.hotAddress).startsWith("bchtest:")) return { ok: false, reason: "mainnet_blocked", chain: "bch" };
    const sent = await broadcast("bch", prep.hex);
    if (!sent || !sent.ok) return { ok: false, reason: "broadcast_rejected", chain: "bch" };
    prepTxid = prep.txid;
    funding = { txid: prep.txid, vout: 0, satoshis: prep.satoshis };
  }
  let signed;
  try {
    signed = signBchGenesis({ secret, funding, prefix: "bchtest" });
  } catch (e) {
    return { ok: false, reason: e && e.code ? e.code : "sign_failed", chain: "bch", prep_txid: prepTxid };
  }
  if (!String(signed.hotAddress).startsWith("bchtest:")) return { ok: false, reason: "mainnet_blocked", chain: "bch" };
  const sent = await broadcast("bch", signed.hex);
  if (!sent || !sent.ok) return { ok: false, reason: "broadcast_rejected", chain: "bch", prep_txid: prepTxid };
  return { ok: true, chain: "bch", public_id: signed.category, txid: signed.txid, prep_txid: prepTxid };
}

export async function setupChain(env, chain, deps = {}) {
  if (chain !== "nexa" && chain !== "bch") return { ok: false, reason: "bad_chain" };
  if (!env || env.MINT_NETWORK !== "testnet") return { ok: false, reason: "mainnet_blocked", chain };
  if (!signingEnabled(env)) return { ok: false, reason: "signing_off", chain };
  const named = namedAddress(env, chain);
  if (isMainnetAddress(chain, named)) return { ok: false, reason: "mainnet_address", chain };

  const record = deps.record !== false;
  if (record && !(await schemaReady(env))) return { ok: false, reason: "schema_missing", chain };
  if (record) {
    const existing = await tokenConfig(env, chain);
    if (existing) {
      return {
        ok: false,
        reason: "already_setup",
        chain,
        public_id: existing.public_id,
        txid: existing.txid,
      };
    }
  }

  const secret = loadHotKey(env, chain);
  if (!secret) return { ok: false, reason: "key_missing", chain };
  let hot;
  try {
    hot = hotFromKey(chain, secret);
  } catch (e) {
    return scrub({ ok: false, reason: e && e.code ? e.code : "bad_key", chain }, secret);
  }
  if (isMainnetAddress(chain, hot)) return { ok: false, reason: "mainnet_address", chain };
  if (named && named !== hot) return { ok: false, reason: "address_mismatch", chain };

  const list = deps.listUnspent || defaultList;
  const broadcast = deps.broadcast || defaultBroadcast;
  const created = chain === "nexa"
    ? await createNexa({ secret, hot, list, broadcast })
    : await createBch({ secret, hot, list, broadcast });
  if (!created.ok) return scrub(created, secret);
  if (record) {
    try {
      await remember(env, chain, created.public_id, created.txid);
    } catch {
      return scrub({ ...created, ok: false, reason: "record_failed" }, secret);
    }
  }
  return scrub(created, secret);
}
