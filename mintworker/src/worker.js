// Nordic Crypto event-NFT mint policy. Separate from the tip Worker on purpose.
// GET  /api/health     booleans only. Never the key.
// GET  /api/treasury   caps, refill address, observed balance. Never the key.
// POST /api/mint       runs the caps. Does not sign and does not broadcast.
//
// The hot key is env.NEXA_HOT_KEY / env.BCH_HOT_KEY, injected by Cloudflare on
// every isolate, including after a redeploy. This handler loads it only to see
// that it is present. It is not copied into a response.

import caps from "../caps.json" with { type: "json" };
import { evaluate } from "./policy.js";
import { loadHotKey, publicHealth, refillAddress } from "./secrets.js";

const PLACEHOLDER = {
  nexa: "placeholder:nexa:nordic-crypto-minting-treasury",
  bch: "placeholder:bch:nordic-crypto-minting-treasury",
};

const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

async function identityHash(chain, identity, eventId) {
  const raw = chain + "|" + String(identity || "").trim() + "|" + String(eventId || "").trim();
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(raw)));
}

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

async function counts(env, chain, eventId, day) {
  if (!env || !env.DB) return { claims: new Set(), eventCounts: {}, dayCounts: {} };
  const eventRow = await env.DB.prepare("SELECT COUNT(*) AS n FROM mint_claim WHERE chain = ? AND event_id = ?").bind(chain, eventId).first();
  const dayRow = await env.DB.prepare("SELECT COUNT(*) AS n FROM mint_claim WHERE chain = ? AND day = ?").bind(chain, day).first();
  return {
    claims: new Set(),
    eventCounts: { [chain + "|" + eventId]: Number(eventRow.n) },
    dayCounts: { [chain + "|" + day]: Number(dayRow.n) },
  };
}

async function already(env, hash) {
  if (!env || !env.DB) return false;
  const row = await env.DB.prepare("SELECT 1 AS x FROM mint_claim WHERE h = ?").bind(hash).first();
  return !!row;
}

export default {
  async fetch(req, env) {
    // Load the binding so a missing secret fails closed. The value is not used
    // for signing in this draft and is not placed on `out`.
    const nexaKey = loadHotKey(env, "nexa");
    const bchKey = loadHotKey(env, "bch");
    void nexaKey;
    void bchKey;

    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/api/health") return send(publicHealth(env));
    if (req.method === "GET" && url.pathname === "/api/treasury") {
      const out = { feature: "event_nft", prototype: true, intentionally_small: true, signs: false, caps };
      for (const chain of ["nexa", "bch"]) {
        const addr = refillAddress(env, chain, PLACEHOLDER[chain]);
        const balance = await observed(env, chain);
        out[chain] = { ...addr, balance, refill_address: addr.address, hot_balance_target: caps[chain].hot_balance_target, unit: caps[chain].unit };
      }
      return send(out);
    }
    if (req.method === "POST" && url.pathname === "/api/mint") {
      let body;
      try { body = await req.json(); } catch { return send({ allow: false, reason: "bad_json" }, 400); }
      const chain = body && body.chain;
      const eventId = body && typeof body.event_id === "string" ? body.event_id : "";
      const identity = body && typeof body.identity === "string" ? body.identity : "";
      if (!caps[chain] || !eventId || !identity) return send({ allow: false, reason: "bad_request" }, 400);
      if (chain === "bch" && caps.bch.turnstile && env && env.TURNSTILE_SECRET && !body.turnstile) {
        return send({ allow: false, reason: "turnstile_required", needs_funding: false }, 400);
      }
      const hash = await identityHash(chain, identity, eventId);
      const day = new Date().toISOString().slice(0, 10);
      const balance = await observed(env, chain);
      const state = await counts(env, chain, eventId, day);
      if (await already(env, hash)) state.claims.add(hash);
      const decision = evaluate(caps, state, { chain, eventId, day, balance, identityHash: hash });
      // No signer is wired. A passed policy still does not broadcast and does not record a claim.
      return send({ ...decision, signed: false, broadcast: false });
    }
    return send({ error: "not_found" }, 404);
  },
};
