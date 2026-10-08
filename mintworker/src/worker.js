// Nordic Crypto event-NFT mint Worker. Separate from the tip Worker.
// GET  /api/health            booleans only. Never the key.
// GET  /api/treasury          caps, refill address, observed balance, history.
// POST /api/treasury/observe  read each hot-wallet balance from electrum and store it.
// GET  /api/treasury/history  refills, mints, and the balance series.
// POST /api/mint              caps, then (testnet flag only) sign and broadcast.
//
// The hourly cron stores each chain's balance before any mint, including when
// signing is off. A mint with no stored balance asks electrum once.
//
// The hot key is env.NEXA_HOT_KEY / env.BCH_HOT_KEY. Signing runs only when
// NC_EVENT_NFT=1 and MINT_NETWORK=testnet. Mainnet is not broadcast.

import caps from "../caps.json" with { type: "json" };
import { performMint } from "./mint.js";
import { loadHotKey, publicHealth, refillAddress, signingEnabled } from "./secrets.js";
import { broadcastBch, broadcastNexa } from "./broadcast.js";
import { displayAmount, ingestRefills, publicHistory, recordSnapshot } from "./history.js";
import { hotAddress, observeChain, observeChains, readObservedSats } from "./balance.js";
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

async function observedDisplay(env, chain) {
  return displayAmount(chain, await readObservedSats(env, chain));
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
    const balance = await observedDisplay(env, chain);
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
    if (req.method === "POST" && url.pathname === "/api/treasury/observe") {
      const refreshed = await observeChains(env);
      const body = await treasuryBody(env);
      body.refreshed = {
        nexa: !!(refreshed.nexa && refreshed.nexa.ok),
        bch: !!(refreshed.bch && refreshed.bch.ok),
      };
      return send(body);
    }
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
        observeBalance: async (chain) => {
          const seen = await observeChain(env, chain);
          return seen.ok ? seen.sats : null;
        },
      });
      const status = result.reason === "bad_request" || result.reason === "bad_json" ? 400 : 200;
      return send(result, status);
    }
    return send({ error: "not_found" }, 404);
  },

  async scheduled(_event, env) {
    if (!env.DB) return;
    const at = new Date().toISOString();
    for (const chain of ["nexa", "bch"]) {
      try {
        const seen = await observeChain(env, chain);
        if (!seen.ok) {
          const sats = await readObservedSats(env, chain);
          if (sats != null) await recordSnapshot(env.DB, chain, sats, at);
        }
        const address = await hotAddress(env, chain);
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
