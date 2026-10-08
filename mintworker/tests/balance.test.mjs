import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { Address, AddressType, GroupToken, Networks, PrivateKey } from "libnexa-ts";
import { fetchBalanceSats, hotAddress, observeChain } from "../src/balance.js";
import { refillFromTx } from "../src/history.js";
import { nexaVerboseToSatoshis } from "../src/utxos.js";
import { displayAmount, policyAmount } from "../src/history.js";
import { performMint } from "../src/mint.js";
import { signNexaChallenge } from "../src/nexa/message.js";

const caps = JSON.parse(readFileSync(new URL("../caps.json", import.meta.url)));

function memDb() {
  const observed = {};
  const snapshots = [];
  const ledger = [];
  const claims = [];
  return {
    observed,
    snapshots,
    ledger,
    prepare(sql) {
      return {
        bind(...args) {
          return {
            async first() {
              if (sql.includes("hot_observed")) {
                const amount = observed[args[0]];
                return amount == null ? null : { amount };
              }
              if (sql.includes("mint_claim WHERE h")) return claims.includes(args[0]) ? { x: 1 } : null;
              if (sql.includes("COUNT(*)")) return { n: 0 };
              return null;
            },
            async run() {
              if (sql.includes("hot_observed")) observed[args[0]] = args[1];
              if (sql.includes("balance_snapshot")) snapshots.push({ chain: args[0], at: args[1], amount: args[2] });
              if (sql.includes("treasury_ledger")) {
                ledger.push({ txid: args[0], chain: args[1], kind: args[2], amount: args[3] });
              }
              if (sql.includes("mint_claim")) claims.push(args[0]);
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

test("electrum satoshis are summed and a non-integer is ignored", async () => {
  const ok = await fetchBalanceSats("nexa", "nexatest:example", async () => ({
    ok: true,
    result: { confirmed: 10000, unconfirmed: -4000 },
  }));
  assert.equal(ok, 6000);
  const floored = await fetchBalanceSats("nexa", "nexatest:example", async () => ({
    ok: true,
    result: { confirmed: 10, unconfirmed: -40 },
  }));
  assert.equal(floored, 0);
  const bad = await fetchBalanceSats("nexa", "nexatest:example", async () => ({
    ok: true,
    result: { confirmed: 1.5, unconfirmed: 0 },
  }));
  assert.equal(bad, null);
});

test("a dead electrum URL is skipped", async () => {
  let calls = 0;
  const sats = await fetchBalanceSats("bch", "bchtest:zexample", async () => {
    calls += 1;
    if (calls === 1) throw new Error("down");
    return { ok: true, result: { confirmed: "23001", unconfirmed: 0 } };
  });
  assert.equal(sats, 23001);
  assert.equal(calls, 2);
});

test("Nexa policy sees whole NEXA and the public balance divides by 100", () => {
  assert.equal(displayAmount("nexa", 204050), 2040.5);
  assert.equal(policyAmount("nexa", 204050), 2040);
  assert.equal(displayAmount("bch", 23001), 23001);
  assert.equal(policyAmount("bch", 23001), 23001);
});

test("observe stores satoshis for the configured address and omits the key", async () => {
  const key = PrivateKey.fromRandom("testnet").toWIF();
  const address = "nexatest:nqtsq5g5xjg5cqg2kx5wgg4wag9hfjach7zaqxxekdrpgx5v";
  const db = memDb();
  let asked = null;
  const seen = await observeChain({
    DB: db,
    NEXA_HOT_ADDRESS: address,
    NEXA_HOT_KEY: key,
  }, "nexa", async (_url, method, params) => {
    asked = { method, params };
    return { ok: true, result: { confirmed: 204100, unconfirmed: 0 } };
  }, "2026-10-07T00:00:00.000Z");
  assert.equal(seen.ok, true);
  assert.equal(seen.sats, 204100);
  assert.equal(seen.display, 2041);
  assert.equal(db.observed.nexa, 204100);
  assert.deepEqual(db.snapshots, [{ chain: "nexa", at: "2026-10-07T00:00:00.000Z", amount: 204100 }]);
  assert.equal(asked.method, "blockchain.address.get_balance");
  assert.deepEqual(asked.params, [address]);
  assert.equal(JSON.stringify(seen).includes(key), false);
  assert.equal(await hotAddress({ NEXA_HOT_ADDRESS: "placeholder:nexa" }, "nexa"), null);
});

test("a missing balance is refused before any utxo lookup", async () => {
  const db = memDb();
  let calls = 0;
  const quiet = await performMint({ DB: db, MINT_NETWORK: "testnet", NC_EVENT_NFT: "1" }, {
    chain: "nexa", event_id: "evt", identity: "nexatest:someone",
  }, caps, {
    observeBalance: async () => { calls += 1; return 5000000; },
    fetchUtxos: async () => { calls += 1; return {}; },
    broadcast: async () => { calls += 1; return { ok: true }; },
  });
  assert.equal(quiet.reason, "balance_unknown");
  assert.equal(calls, 0);
  assert.equal(db.observed.nexa, undefined);

  db.observed.nexa = 5000000;
  const hot = PrivateKey.fromRandom("testnet");
  const visitor = PrivateKey.fromRandom("testnet");
  const address = visitor.toAddress().toString();
  const auth = GroupToken.authFlags.AUTHORITY | GroupToken.authFlags.MINT | GroupToken.authFlags.BATON | GroupToken.authFlags.SUBGROUP;
  const result = await performMint({
    DB: db,
    NC_EVENT_NFT: "1",
    MINT_NETWORK: "testnet",
    NEXA_HOT_KEY: hot.toWIF(),
    NEXA_PARENT_GROUP: new Address(Uint8Array.from({ length: 32 }, (_, i) => i + 1), Networks.testnet, AddressType.GroupIdAddress).toString(),
  }, {
    chain: "nexa",
    event_id: "evt",
    identity: address,
    signature: signNexaChallenge(visitor.toWIF(), "evt", address),
    zip_url: "https://nordiccrypto.no/assets/nft/card.zip",
    zip_hash: "cd".repeat(32),
  }, caps, {
    now: () => new Date("2026-10-07T12:00:00.000Z"),
    fetchUtxos: async () => ({
      authority: { outpoint: "11".repeat(32), satoshis: 2000, groupAmount: auth },
      funds: [{ outpoint: "22".repeat(32), satoshis: 500000 }],
    }),
    broadcast: async () => ({ ok: true }),
  });
  assert.equal(result.broadcast, true, result.reason);
  assert.equal(db.observed.nexa, 5000000 - (100000 + result.fee));
  assert.equal(JSON.stringify(result).includes(hot.toWIF()), false);
});

test("a balance under the reserve does not open a socket", async () => {
  const db = memDb();
  db.observed.nexa = 10000;
  let calls = 0;
  const result = await performMint({
    DB: db,
    NC_EVENT_NFT: "1",
    MINT_NETWORK: "testnet",
    NEXA_HOT_KEY: "nexa-hot-key-material-not-for-logs-0123456789",
    NEXA_PARENT_GROUP: "nexatest:tq",
  }, {
    chain: "nexa", event_id: "evt", identity: "nexatest:someone",
  }, caps, {
    fetchUtxos: async () => { calls += 1; return {}; },
    broadcast: async () => { calls += 1; return { ok: true }; },
  });
  assert.equal(result.reason, "below_reserve");
  assert.equal(calls, 0);
});

test("a Nexa history value in whole NEXA is stored as satoshis", () => {
  const address = "nexatest:nqtsq5g5xjg5cqg2kx5wgg4wag9hfjach7zaqxxekdrpgx5v";
  const tx = nexaVerboseToSatoshis({
    txid: "ab".repeat(32),
    time: 1791417115,
    vin: [{ scriptPubKey: { addresses: ["nexatest:nqtsq5g5rgxqrnnpdufavwh509l0auhdpv79u2x4ca5xvwmu"] } }],
    vout: [
      { value: 100, scriptPubKey: { addresses: [address] } },
      { value: 2209.48, scriptPubKey: { addresses: ["nexatest:nqtsq5g5dnds02e88d8smqepv4djtuqd05mxhtq8y2v9lda5"] } },
    ],
  });
  const row = refillFromTx(tx, address);
  assert.equal(row.amount, 10000);
  assert.equal(nexaVerboseToSatoshis({ vout: [{ value: 1.001 }] }), null);
});

test("an electrum miss does not invent a balance", async () => {
  const db = memDb();
  const seen = await observeChain({
    DB: db,
    BCH_HOT_ADDRESS: "bchtest:zpahmsq06pyhkzfygww3kyrrpc00vl8mrctf3t6yfv",
  }, "bch", async () => ({ ok: false, error: "down" }));
  assert.equal(seen.reason, "balance_unavailable");
  assert.equal(db.observed.bch, undefined);
  assert.equal(db.snapshots.length, 0);
});
