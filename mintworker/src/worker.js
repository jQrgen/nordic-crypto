// Nordic Crypto event-NFT mint Worker. Separate from the tip Worker.
// GET  /api/health            booleans only. Never the key.
// GET  /api/treasury          caps, refill address, observed balance, history.
// GET  /api/treasury/history  refills, mints, and the balance series.
// POST /api/mint              caps, then (testnet flag only) sign and broadcast.
//
// The hot key is env.NEXA_HOT_KEY / env.BCH_HOT_KEY. Signing runs only when
// NC_EVENT_NFT=1 and MINT_NETWORK=testnet. Mainnet is not broadcast.

import caps from "../caps.json" with { type: "json" };
import { performMint } from "./mint.js";
import { loadHotKey, publicHealth, refillAddress, signingEnabled } from "./secrets.js";
import { broadcastBch, broadcastNexa } from "./broadcast.js";
import { ingestRefills, publicHistory, recordSnapshot } from "./history.js";
import { bchAddress } from "./bch/sign.js";
import { nexaAddressOf } from "./nexa/message.js";
import { lookupUtxos, syncChainRefills } from "./utxos.js";

const PLACEHOLDER = {
  nexa: "placeholder:nexa:nordic-crypto-minting-treasury",
  bch: "placeholder:bch:nordic-crypto-minting-treasury",
};

function send(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

async function observed(env, chain) {
  if (!env || !env.DB) return null;
  const row = await env.DB.prepare("SELECT amount FROM hot_observed WHERE chain = ?").bind(chain).first();
  return row ? Number(row.amount) : null;
}

async function treasuryBody(env) {
  const history = await publicHistory(env && env.DB);
  const out = {
    feature: "event_nft",
    prototype: !signingEnabled(env),
    intentionally_small: true,
    signs: signingEnabled(env),
    network: signingEnabled(env) ? "testnet" : "off",
    caps,
    history: history.history,
    balance_series: history.balance_series,
  };
  for (const chain of ["nexa", "bch"]) {
    const addr = refillAddress(env, chain, PLACEHOLDER[chain]);
    const balance = await observed(env, chain);
    out[chain] = {
      ...addr,
      balance,
      refill_address: addr.address,
      hot_balance_target: caps[chain].hot_balance_target,
      unit: caps[chain].unit,
    };
  }
  return out;
}

export default {
  async fetch(req, env) {
    const nexaKey = loadHotKey(env, "nexa");
    const bchKey = loadHotKey(env, "bch");
    void nexaKey;
    void bchKey;

    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/api/health") return send(publicHealth(env));
    if (req.method === "GET" && (url.pathname === "/api/treasury" || url.pathname === "/api/treasury/")) {
      return send(await treasuryBody(env));
    }
    if (req.method === "GET" && url.pathname === "/api/treasury/history") {
      return send(await publicHistory(env && env.DB));
    }
    if (req.method === "POST" && url.pathname === "/api/mint") {
      let body;
      try { body = await req.json(); } catch { return send({ allow: false, reason: "bad_json" }, 400); }
      const result = await performMint(env, body, caps, {
        fetchUtxos: (chain, secret) => lookupUtxos(env, chain, secret),
        broadcast: async (chain, hex) => chain === "nexa" ? broadcastNexa(hex) : broadcastBch(hex),
      });
      const status = result.reason === "bad_request" || result.reason === "bad_json" ? 400 : 200;
      return send(result, status);
    }
    return send({ error: "not_found" }, 404);
  },

  async scheduled(_event, env) {
    if (!signingEnabled(env) || !env.DB) return;
    const at = new Date().toISOString();
    for (const chain of ["nexa", "bch"]) {
      const row = await env.DB.prepare("SELECT amount FROM hot_observed WHERE chain = ?").bind(chain).first();
      if (row) await recordSnapshot(env.DB, chain, Number(row.amount), at);
    }
    for (const chain of ["nexa", "bch"]) {
      try {
        const named = chain === "nexa" ? env.NEXA_HOT_ADDRESS : env.BCH_HOT_ADDRESS;
        const key = loadHotKey(env, chain);
        let address = named && !String(named).startsWith("placeholder:") ? named : null;
        if (!address && key) address = chain === "nexa" ? nexaAddressOf(key) : await bchAddress(key);
        if (address) await syncChainRefills(env.DB, chain, address);
      } catch {
        // A node that is down leaves the ledger as it was.
      }
    }
    if (!env.REFILL_FEED) return;
    const res = await fetch(env.REFILL_FEED);
    if (!res.ok) return;
    const doc = await res.json();
    for (const chain of ["nexa", "bch"]) {
      const rows = (doc && doc[chain]) || [];
      await ingestRefills(env.DB, chain, rows);
    }
  },
};

export { ingestRefills };
