import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { GroupToken, PrivateKey } from "libnexa-ts";
import { adminAuthorized, tokensEqual } from "../src/admin.js";
import { allowClient, resetRates, PER_CLIENT } from "../src/limit.js";
import { performMint } from "../src/mint.js";
import { signNexaChallenge } from "../src/nexa/message.js";
import { freshBchKey } from "../src/bch/sign.js";
import { BCH_GENESIS_MIN, BCH_PREP_MIN, setupChain } from "../src/setup.js";
import { handleFetch } from "../src/worker.js";

const caps = JSON.parse(readFileSync(new URL("../caps.json", import.meta.url)));
const TOKEN = "admin-token-value-0123456789";

function memDb() {
  const setup = {};
  const observed = {};
  const claims = [];
  const ledger = [];
  return {
    setup,
    observed,
    prepare(sql) {
      return {
        bind(...args) {
          return {
            async first() {
              if (sql.includes("token_setup")) return setup[args[0]] || null;
              if (sql.includes("hot_observed")) {
                const amount = observed[args[0]];
                return amount == null ? null : { amount };
              }
              if (sql.includes("mint_claim WHERE h")) return claims.includes(args[0]) ? { x: 1 } : null;
              if (sql.includes("COUNT(*)")) return { n: 0 };
              return null;
            },
            async run() {
              if (sql.includes("token_setup")) {
                setup[args[0]] = { public_id: args[1], txid: args[2], created_at: args[3] };
              }
              if (sql.includes("hot_observed")) observed[args[0]] = args[1];
              if (sql.includes("mint_claim")) claims.push(args[0]);
              if (sql.includes("treasury_ledger")) ledger.push(args);
            },
            async all() {
              return { results: [] };
            },
          };
        },
      };
    },
  };
}

function signingEnv(over = {}) {
  return {
    NC_EVENT_NFT: "1",
    MINT_NETWORK: "testnet",
    ADMIN_TOKEN: TOKEN,
    DB: memDb(),
    ...over,
  };
}

function post(path, token, body) {
  const headers = {};
  if (token) headers.Authorization = "Bearer " + token;
  if (body) headers["content-type"] = "application/json";
  return new Request("https://mint.example" + path, {
    method: "POST",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
}

test("the admin compare does not treat a different length as a match", async () => {
  assert.equal(await tokensEqual(TOKEN, TOKEN), true);
  assert.equal(await tokensEqual(TOKEN, TOKEN + "x"), false);
  assert.equal(await tokensEqual(TOKEN, "short"), false);
  assert.equal(await tokensEqual(TOKEN, ""), false);
  const req = new Request("https://mint.example/api/admin/setup-tokens", {
    headers: { Authorization: "Bearer " + TOKEN },
  });
  assert.equal(await adminAuthorized({ ADMIN_TOKEN: TOKEN }, req), true);
  assert.equal(await adminAuthorized({ ADMIN_TOKEN: "" }, req), false);
  assert.equal(await adminAuthorized({ ADMIN_TOKEN: TOKEN }, new Request("https://mint.example/")), false);
});

test("setup and observe refuse a missing admin token before any network call", async () => {
  let calls = 0;
  const env = signingEnv();
  const boom = async () => { calls += 1; return []; };
  const setup = await handleFetch(post("/api/admin/setup-tokens?chain=nexa", ""), env, {
    setup: { listUnspent: boom, broadcast: boom },
  });
  assert.equal(setup.status, 401);
  const observe = await handleFetch(post("/api/treasury/observe", "wrong-token-value-0123456789"), env, {
    observeChains: boom,
  });
  assert.equal(observe.status, 401);
  assert.equal(calls, 0);
  const body = await setup.json();
  assert.equal(body.reason, "unauthorized");
  assert.equal(JSON.stringify(body).includes(TOKEN), false);
});

test("setup refuses mainnet without asking electrum", async () => {
  let calls = 0;
  const listUnspent = async () => { calls += 1; return []; };
  const blocked = await setupChain(signingEnv({ MINT_NETWORK: "mainnet", NC_EVENT_NFT: "1" }), "nexa", { listUnspent });
  assert.equal(blocked.reason, "mainnet_blocked");
  const address = await setupChain(signingEnv({
    BCH_HOT_ADDRESS: "bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx6a",
    BCH_HOT_KEY: freshBchKey(),
  }), "bch", { listUnspent });
  assert.equal(address.reason, "mainnet_address");
  const mainnetWif = "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn";
  const key = await setupChain(signingEnv({ BCH_HOT_KEY: mainnetWif }), "bch", { listUnspent });
  assert.equal(key.reason, "mainnet_blocked");
  assert.equal(calls, 0);
  assert.equal(JSON.stringify(key).includes(mainnetWif), false);
});

test("setup refuses to create a second group once one is recorded", async () => {
  const db = memDb();
  db.setup.nexa = { public_id: "nexatest:already", txid: "ab".repeat(32) };
  let calls = 0;
  const result = await setupChain(signingEnv({ DB: db, NEXA_HOT_KEY: PrivateKey.fromRandom("testnet").toWIF() }), "nexa", {
    listUnspent: async () => { calls += 1; return []; },
    broadcast: async () => { calls += 1; return { ok: true }; },
  });
  assert.equal(result.reason, "already_setup");
  assert.equal(result.public_id, "nexatest:already");
  assert.equal(result.txid, "ab".repeat(32));
  assert.equal(calls, 0);
});

test("an empty chipnet wallet is unfunded, and a later coin is spent from vout 0", async () => {
  const secret = freshBchKey();
  const env = signingEnv({ BCH_HOT_KEY: secret });
  let broadcasts = 0;
  const empty = await setupChain(env, "bch", {
    listUnspent: async () => [],
    broadcast: async () => { broadcasts += 1; return { ok: true }; },
  });
  assert.equal(empty.reason, "unfunded");
  assert.equal(empty.have_sats, 0);
  assert.equal(empty.need_sats, BCH_GENESIS_MIN);
  assert.equal(empty.detail, "no_coins");
  assert.equal(broadcasts, 0);
  assert.equal(JSON.stringify(empty).includes(secret), false);

  const small = await setupChain(env, "bch", {
    listUnspent: async () => [{ txid: "11".repeat(32), vout: 1, satoshis: 1000 }],
    broadcast: async () => { broadcasts += 1; return { ok: true }; },
  });
  assert.equal(small.reason, "unfunded");
  assert.equal(small.detail, "no_vout0");
  assert.equal(small.need_sats, BCH_PREP_MIN);
  assert.equal(broadcasts, 0);

  const created = await setupChain(env, "bch", {
    listUnspent: async () => [{ txid: "22".repeat(32), vout: 1, satoshis: 50000 }],
    broadcast: async () => { broadcasts += 1; return { ok: true }; },
  });
  assert.equal(created.ok, true, created.reason);
  assert.equal(created.prep_txid, created.public_id);
  assert.equal(broadcasts, 2);
  assert.equal(env.DB.setup.bch.public_id, created.public_id);
  assert.equal(JSON.stringify(created).includes(secret), false);

  const again = await setupChain(env, "bch", {
    listUnspent: async () => { broadcasts += 10; return []; },
    broadcast: async () => { broadcasts += 10; return { ok: true }; },
  });
  assert.equal(again.reason, "already_setup");
  assert.equal(again.public_id, created.public_id);
  assert.equal(broadcasts, 2);
});

test("a Nexa group id is recorded and a mint can read it without the var", async () => {
  const hot = PrivateKey.fromRandom("testnet");
  const env = signingEnv({ NEXA_HOT_KEY: hot.toWIF() });
  const created = await setupChain(env, "nexa", {
    listUnspent: async () => [{ outpoint: "11".repeat(32), satoshis: 500000 }],
    broadcast: async () => ({ ok: true }),
  });
  assert.equal(created.ok, true, created.reason);
  assert.equal(created.public_id.startsWith("nexatest:"), true);
  assert.equal(JSON.stringify(created).includes(hot.toWIF()), false);
  assert.equal(env.DB.setup.nexa.public_id, created.public_id);

  const visitor = PrivateKey.fromRandom("testnet");
  const address = visitor.toAddress().toString();
  const auth = GroupToken.authFlags.AUTHORITY | GroupToken.authFlags.MINT | GroupToken.authFlags.BATON | GroupToken.authFlags.SUBGROUP;
  env.DB.observed.nexa = 5000000;
  const minted = await performMint(env, {
    chain: "nexa",
    event_id: "evt",
    identity: address,
    signature: signNexaChallenge(visitor.toWIF(), "evt", address),
    zip_url: "https://nordiccrypto.no/assets/nft/card.zip",
    zip_hash: "cd".repeat(32),
  }, caps, {
    now: () => new Date("2026-10-08T00:00:00.000Z"),
    fetchUtxos: async () => ({
      authority: { outpoint: "33".repeat(32), satoshis: 2000, groupAmount: auth },
      funds: [{ outpoint: "44".repeat(32), satoshis: 500000 }],
    }),
    broadcast: async () => ({ ok: true }),
  });
  assert.equal(minted.broadcast, true, minted.reason);
  assert.equal(JSON.stringify(minted).includes(hot.toWIF()), false);
});

test("the mint rate limit is enforced before a utxo lookup", async () => {
  resetRates();
  const ip = "203.0.113.44";
  for (let i = 0; i < PER_CLIENT; i++) assert.equal(await allowClient(ip, 1_000), true);
  assert.equal(await allowClient(ip, 1_000), false);
  assert.equal(await allowClient("203.0.113.45", 1_000), true);

  let calls = 0;
  const res = await handleFetch(post("/api/mint", "", {
    chain: "nexa", event_id: "evt", identity: "nexatest:someone",
  }), signingEnv(), {
    rateAllow: async () => false,
    fetchUtxos: async () => { calls += 1; return null; },
    broadcast: async () => { calls += 1; return { ok: true }; },
  });
  assert.equal(res.status, 429);
  assert.equal((await res.json()).reason, "rate_limited");
  assert.equal(calls, 0);
});

test("the admin route returns only the public id", async () => {
  const secret = freshBchKey();
  const env = signingEnv({ BCH_HOT_KEY: secret });
  const res = await handleFetch(post("/api/admin/setup-tokens?chain=bch", TOKEN), env, {
    setup: {
      listUnspent: async () => [],
      broadcast: async () => ({ ok: true }),
    },
  });
  assert.equal(res.status, 422);
  const body = await res.json();
  assert.equal(body.reason, "unfunded");
  assert.equal(JSON.stringify(body).includes(secret), false);
  assert.equal(JSON.stringify(body).includes(TOKEN), false);
});
