// One mint. The policy runs first. Signing and broadcast run only when the
// feature flag is on and the network is testnet. The claim row is inserted
// only after the node accepts the transaction.

import { evaluate } from "./policy.js";
import { loadHotKey, signingEnabled } from "./secrets.js";
import { signNexaMint } from "./nexa/sign.js";
import { verifyNexaChallenge } from "./nexa/message.js";
import { signBchMint } from "./bch/sign.js";
import { verifyBchChallenge } from "./bch/message.js";
import { recordLedger } from "./history.js";

const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

export async function identityHash(chain, identity, eventId) {
  const raw = chain + "|" + String(identity || "").trim() + "|" + String(eventId || "").trim();
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(raw)));
}

function fail(reason, extra = {}) {
  return { allow: false, reason, signed: false, broadcast: false, ...extra };
}

async function already(env, hash) {
  if (!env || !env.DB) return false;
  const row = await env.DB.prepare("SELECT 1 AS x FROM mint_claim WHERE h = ?").bind(hash).first();
  return !!row;
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

async function observed(env, chain) {
  if (!env || !env.DB) return null;
  const row = await env.DB.prepare("SELECT amount FROM hot_observed WHERE chain = ?").bind(chain).first();
  return row ? Number(row.amount) : null;
}

function zipAllowed(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && u.hostname === "nordiccrypto.no" && u.pathname.startsWith("/assets/nft/");
  } catch {
    return false;
  }
}

export async function performMint(env, body, caps, deps = {}) {
  const chain = body && body.chain;
  const eventId = body && typeof body.event_id === "string" ? body.event_id : "";
  const identity = body && typeof body.identity === "string" ? body.identity.trim() : "";
  if (!caps[chain] || !eventId || !identity) return fail("bad_request");
  if (chain === "bch" && caps.bch.turnstile && env && env.TURNSTILE_SECRET && !body.turnstile) {
    return fail("turnstile_required", { needs_funding: false });
  }
  const hash = await identityHash(chain, identity, eventId);
  const day = (deps.now ? deps.now() : new Date()).toISOString().slice(0, 10);
  const balance = await observed(env, chain);
  const state = await counts(env, chain, eventId, day);
  if (await already(env, hash)) state.claims.add(hash);
  const decision = evaluate(caps, state, { chain, eventId, day, balance, identityHash: hash });
  if (!decision.allow) return { ...decision, signed: false, broadcast: false };
  if (!signingEnabled(env)) return { ...decision, signed: false, broadcast: false };

  const key = loadHotKey(env, chain);
  if (!key) return fail("key_missing", { status: decision.status, needs_funding: decision.needs_funding });
  const signatureOk = chain === "nexa"
    ? verifyNexaChallenge({ address: identity, eventId, signature: body.signature })
    : await verifyBchChallenge({ address: identity, eventId, signature: body.signature });
  if (!signatureOk) return fail("signature_invalid", { status: decision.status, needs_funding: false });

  const fetchUtxos = deps.fetchUtxos;
  if (!fetchUtxos) return fail("utxo_unavailable", { status: decision.status, needs_funding: false });
  const utxos = await fetchUtxos(chain, key);
  if (!utxos) return fail("utxo_unavailable", { status: decision.status, needs_funding: false });

  let signed;
  try {
    if (chain === "nexa") {
      if (!zipAllowed(body.zip_url) || !env.NEXA_PARENT_GROUP) return fail("config_missing");
      signed = signNexaMint({
        secret: key,
        recipient: identity,
        parentGroup: env.NEXA_PARENT_GROUP,
        zipUrl: body.zip_url,
        zipHash: body.zip_hash,
        authority: utxos.authority,
        funds: utxos.funds,
        airdropNexa: caps.nexa.airdrop,
        feeCeilingSats: caps.nexa.network * 100,
      });
    } else {
      if (!env.BCH_CATEGORY) return fail("config_missing");
      const commitment = hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(eventId + "|bch")));
      signed = await signBchMint({
        secret: key,
        recipient: identity,
        categoryHex: env.BCH_CATEGORY,
        commitmentHex: commitment,
        minting: utxos.minting,
        funding: utxos.funding,
        airdropSats: caps.bch.airdrop,
        feeCeilingSats: caps.bch.network,
      });
    }
  } catch (e) {
    return fail(e.code || "sign_failed", { status: decision.status, needs_funding: e.code === "insufficient_funds" });
  }

  const broadcast = deps.broadcast;
  if (!broadcast) return fail("broadcast_unavailable", { status: decision.status });
  const sent = await broadcast(chain, signed.hex);
  if (!sent || !sent.ok) return fail("broadcast_rejected", { status: decision.status, node: sent && sent.error ? sent.error : undefined });

  const at = (deps.now ? deps.now() : new Date()).toISOString();
  if (env && env.DB) {
    await env.DB.prepare(
      "INSERT INTO mint_claim (h, chain, event_id, day, created_at) VALUES (?, ?, ?, ?, ?)"
    ).bind(hash, chain, eventId, day, at).run();
    const spent = chain === "nexa" ? signed.airdropSats + signed.feeSats : signed.spentSats;
    await recordLedger(env.DB, { txid: signed.txid, chain, kind: "mint", amount: spent, at, event_id: eventId });
    if (balance != null) {
      await env.DB.prepare(
        "INSERT INTO hot_observed (chain, amount, observed_at) VALUES (?, ?, ?) ON CONFLICT(chain) DO UPDATE SET amount = excluded.amount, observed_at = excluded.observed_at"
      ).bind(chain, balance - spent, at).run();
    }
  }
  return {
    ...decision,
    signed: true,
    broadcast: true,
    txid: signed.txid,
    fee: signed.feeSats,
  };
}
