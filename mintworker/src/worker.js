// Nordic Crypto event-NFT mint Worker. Separate from the tip Worker.
// GET  /api/health                 booleans only. Never the key.
// GET  /api/treasury               caps, refill address, observed balance, history.
// POST /api/treasury/observe       admin token. Read each hot-wallet balance.
// GET  /api/treasury/history       refills, mints, and the balance series.
// POST /api/mint                   rate limit, then caps, then (testnet) sign.
// POST /api/admin/setup-tokens     admin token. One testnet group or category.
//
// The hourly cron stores each chain's balance before any mint, including when
// signing is off. A mint with no stored balance is refused. It does not ask
// electrum until the rate limit and the caps have allowed the request.
//
// The hot key is env.NEXA_HOT_KEY / env.BCH_HOT_KEY. Signing runs only when
// NC_EVENT_NFT=1 and MINT_NETWORK=testnet. Mainnet is not broadcast.
// ADMIN_TOKEN gates setup and the manual balance read. The cron does not use it.

import caps from "../caps.json" with { type: "json" };
import { adminAuthorized } from "./admin.js";
import { performMint } from "./mint.js";
import { loadHotKey, publicHealth, refillAddress, signingEnabled } from "./secrets.js";
import { broadcastBch, broadcastNexa } from "./broadcast.js";
import { displayAmount, ingestRefills, publicHistory, recordSnapshot } from "./history.js";
import { hotAddress, observeChain, observeChains, readObservedSats } from "./balance.js";
import { allowClient } from "./limit.js";
import { setupChain } from "./setup.js";
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

function setupStatus(result) {
  if (result.ok) return 200;
  if (result.reason === "bad_chain") return 400;
  if (result.reason === "mainnet_blocked" || result.reason === "mainnet_address" || result.reason === "signing_off") return 403;
  if (result.reason === "already_setup") return 409;
  if (result.reason === "unfunded") return 422;
  if (result.reason === "schema_missing") return 503;
  return 200;
}

export async function handleFetch(req, env, deps = {}) {
  const nexaKey = loadHotKey(env, "nexa");
  const bchKey = loadHotKey(env, "bch");
  void nexaKey;
  void bchKey;

  const url = new URL(req.url);
  if (req.method === "GET" && url.pathname === "/api/health") return send(publicHealth(env));
  if (req.method === "POST" && url.pathname === "/api/treasury/observe") {
    if (!(await adminAuthorized(env, req))) return send({ ok: false, reason: "unauthorized" }, 401);
    const refreshed = await (deps.observeChains || observeChains)(env);
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
  if (req.method === "POST" && url.pathname === "/api/admin/setup-tokens") {
    if (!(await adminAuthorized(env, req))) return send({ ok: false, reason: "unauthorized" }, 401);
    const result = await setupChain(env, url.searchParams.get("chain"), deps.setup || {});
    return send(result, setupStatus(result));
  }
  if (req.method === "POST" && url.pathname === "/api/mint") {
    const ip = (req.headers.get("CF-Connecting-IP") || "").trim().slice(0, 64);
    const allowed = deps.rateAllow ? await deps.rateAllow(ip) : await allowClient(ip);
    if (!allowed) return send({ allow: false, reason: "rate_limited", signed: false, broadcast: false }, 429);
    let body;
    try { body = await req.json(); } catch { return send({ allow: false, reason: "bad_json" }, 400); }
    const result = await performMint(env, body, caps, {
      fetchUtxos: deps.fetchUtxos || ((chain, secret) => lookupUtxos(env, chain, secret)),
      broadcast: deps.broadcast || (async (chain, hex) => chain === "nexa" ? broadcastNexa(hex) : broadcastBch(hex)),
      now: deps.now,
    });
    const status = result.reason === "bad_request" || result.reason === "bad_json" ? 400 : 200;
    return send(result, status);
  }
  return send({ error: "not_found" }, 404);
}

export default {
  fetch(req, env) {
    return handleFetch(req, env);
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
