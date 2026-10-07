import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { Address, AddressType, GroupToken, Networks, PrivateKey, Transaction } from "libnexa-ts";
import { signNexaMint } from "../src/nexa/sign.js";
import { signNexaChallenge, verifyNexaChallenge } from "../src/nexa/message.js";
import { freshBchKey, signBchMint } from "../src/bch/sign.js";
import { signBchChallenge, verifyBchChallenge } from "../src/bch/message.js";
import { bchAddress } from "../src/bch/sign.js";
import { decodeTransaction } from "@bitauth/libauth";
import { hexToBin } from "@bitauth/libauth";
import { performMint } from "../src/mint.js";
import { refillFromTx, seriesFrom, toPublic } from "../src/history.js";
import { publicHealth } from "../src/secrets.js";
import { lookupUtxos } from "../src/utxos.js";

const caps = JSON.parse(readFileSync(new URL("../caps.json", import.meta.url)));

function nexaKey() {
  return PrivateKey.fromRandom("testnet");
}

function parentGroup() {
  return new Address(Uint8Array.from({ length: 32 }, (_, i) => i + 1), Networks.testnet, AddressType.GroupIdAddress).toString();
}

test("a Nexa testnet mint pays the NFT and 1000 NEXA to the visitor", () => {
  const hot = nexaKey();
  const visitor = nexaKey();
  const auth = GroupToken.authFlags.AUTHORITY | GroupToken.authFlags.MINT | GroupToken.authFlags.BATON | GroupToken.authFlags.SUBGROUP;
  const signed = signNexaMint({
    secret: hot.toWIF(),
    recipient: visitor.toAddress().toString(),
    parentGroup: parentGroup(),
    zipUrl: "https://nordiccrypto.no/assets/nft/card.zip",
    zipHash: "ab".repeat(32),
    authority: { outpoint: "11".repeat(32), satoshis: 2000, groupAmount: auth },
    funds: [{ outpoint: "22".repeat(32), satoshis: 500000 }],
    airdropNexa: 1000,
    feeCeilingSats: 2000,
  });
  assert.equal(signed.airdropSats, 100000);
  assert.ok(signed.feeSats > 0 && signed.feeSats <= 2000);
  assert.equal(signed.hotAddress.startsWith("nexatest:"), true);
  const tx = new Transaction(signed.hex);
  const values = tx.outputs.map((o) => Number(o.value));
  assert.ok(values.includes(100000));
  const nft = tx.outputs.find((o) => o.groupData && o.groupData.groupAmount === "1");
  assert.ok(nft, "visitor NFT quantity is 1");
  assert.equal(JSON.stringify(signed).includes(hot.toWIF()), false);
});

test("a Nexa mainnet address is refused", () => {
  const hot = nexaKey();
  assert.throws(() => signNexaMint({
    secret: hot.toWIF(),
    recipient: "nexa:nqtsq5g5jsdmqqywaqd82lhnnk3a8wqunjz6gtxdtavnnekc",
    parentGroup: parentGroup(),
    zipUrl: "https://nordiccrypto.no/assets/nft/card.zip",
    zipHash: "ab".repeat(32),
    authority: { outpoint: "11".repeat(32), satoshis: 2000, groupAmount: 1n },
    funds: [{ outpoint: "22".repeat(32), satoshis: 500000 }],
  }), (e) => e.code === "not_testnet_address");
});

test("a NexaID signature is bound to the address and the event", () => {
  const visitor = nexaKey();
  const address = visitor.toAddress().toString();
  const signature = signNexaChallenge(visitor.toWIF(), "evt-1", address);
  assert.equal(verifyNexaChallenge({ address, eventId: "evt-1", signature }), true);
  assert.equal(verifyNexaChallenge({ address, eventId: "evt-2", signature }), false);
  const other = nexaKey().toAddress().toString();
  assert.equal(verifyNexaChallenge({ address: other, eventId: "evt-1", signature }), false);
});

test("a CashTokens mint returns the authority and pays 10000 sats", async () => {
  const hot = freshBchKey();
  const who = freshBchKey();
  const recipient = await bchAddress(who);
  const signed = await signBchMint({
    secret: hot,
    recipient,
    categoryHex: "33".repeat(32),
    commitmentHex: "44".repeat(32),
    minting: { txid: "11".repeat(32), vout: 0, satoshis: 800 },
    funding: { txid: "22".repeat(32), vout: 1, satoshis: 80000 },
    airdropSats: 10000,
    feeCeilingSats: 1500,
  });
  assert.equal(signed.airdropSats, 10000);
  assert.ok(signed.feeSats <= 1500);
  const tx = decodeTransaction(hexToBin(signed.hex));
  assert.equal(typeof tx, "object");
  const capsOut = tx.outputs.map((o) => o.token && o.token.nft && o.token.nft.capability);
  assert.deepEqual(capsOut.slice(0, 2), ["minting", "none"]);
  assert.equal(tx.outputs[2].valueSatoshis, 10000n);
  assert.equal(JSON.stringify(signed).includes(hot), false);
});

test("a CashConnect signature does not pass for a different event", async () => {
  const who = freshBchKey();
  const address = await bchAddress(who);
  const signature = await signBchChallenge(who, "evt-1", address);
  assert.equal(await verifyBchChallenge({ address, eventId: "evt-1", signature }), true);
  assert.equal(await verifyBchChallenge({ address, eventId: "evt-2", signature }), false);
});

function memDb(balance = { nexa: 5000000, bch: 200000 }) {
  const ledger = [];
  const claims = [];
  return {
    ledger,
    prepare(sql) {
      return {
        bind(...args) {
          return {
            async first() {
              if (sql.includes("hot_observed")) return { amount: balance[args[0]] };
              if (sql.includes("mint_claim WHERE h")) return claims.includes(args[0]) ? { x: 1 } : null;
              if (sql.includes("COUNT(*)")) return { n: 0 };
              return null;
            },
            async run() {
              if (sql.includes("mint_claim")) claims.push(args[0]);
              if (sql.includes("treasury_ledger")) {
                ledger.push({ txid: args[0], chain: args[1], kind: args[2], amount: args[3], at: args[4], event_id: args[5] });
              }
              if (sql.includes("hot_observed")) balance[args[0]] = args[1];
            },
            async all() {
              if (sql.includes("treasury_ledger")) return { results: ledger };
              return { results: [] };
            },
          };
        },
      };
    },
  };
}

test("the flag off does not sign", async () => {
  const db = memDb();
  const result = await performMint({ DB: db, MINT_NETWORK: "testnet" }, {
    chain: "nexa", event_id: "evt", identity: "nexatest:someone",
  }, caps, {});
  assert.equal(result.allow, true);
  assert.equal(result.signed, false);
  assert.equal(result.broadcast, false);
});

test("a bad signature is not broadcast", async () => {
  const visitor = nexaKey();
  const db = memDb();
  let broadcasts = 0;
  const result = await performMint({
    DB: db,
    NC_EVENT_NFT: "1",
    MINT_NETWORK: "testnet",
    NEXA_HOT_KEY: nexaKey().toWIF(),
    NEXA_PARENT_GROUP: parentGroup(),
  }, {
    chain: "nexa",
    event_id: "evt",
    identity: visitor.toAddress().toString(),
    signature: "not-a-signature",
    zip_url: "https://nordiccrypto.no/assets/nft/card.zip",
    zip_hash: "ab".repeat(32),
  }, caps, {
    fetchUtxos: async () => ({}),
    broadcast: async () => { broadcasts += 1; return { ok: true }; },
  });
  assert.equal(result.reason, "signature_invalid");
  assert.equal(broadcasts, 0);
  assert.equal(result.signed, false);
});

test("an accepted testnet mint is recorded without the key", async () => {
  const hot = nexaKey();
  const visitor = nexaKey();
  const address = visitor.toAddress().toString();
  const db = memDb();
  const auth = GroupToken.authFlags.AUTHORITY | GroupToken.authFlags.MINT | GroupToken.authFlags.BATON | GroupToken.authFlags.SUBGROUP;
  const result = await performMint({
    DB: db,
    NC_EVENT_NFT: "1",
    MINT_NETWORK: "testnet",
    NEXA_HOT_KEY: hot.toWIF(),
    NEXA_PARENT_GROUP: parentGroup(),
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
  assert.equal(result.signed, true);
  assert.equal(db.ledger.length, 1);
  assert.equal(db.ledger[0].kind, "mint");
  assert.equal(db.ledger[0].event_id, "evt");
  const pub = toPublic({ ...db.ledger[0], name: "jQrgen", from: "secret-funder" });
  assert.equal(pub.name, undefined);
  assert.equal(pub.from, undefined);
  assert.equal(JSON.stringify(result).includes(hot.toWIF()), false);
});

test("the balance series adds refills and subtracts mints", () => {
  const ledger = [
    { chain: "nexa", kind: "refill", amount: 2000000, at: "2026-10-01T00:00:00Z", txid: "aa".repeat(32) },
    { chain: "nexa", kind: "mint", amount: 102000, at: "2026-10-02T00:00:00Z", txid: "bb".repeat(32), event_id: "evt" },
  ];
  const series = seriesFrom("nexa", [], ledger);
  assert.deepEqual(series.map((p) => p.amount), [20000, 18980]);
  const pub = toPublic(ledger[0]);
  assert.equal(pub.explorer_url.startsWith("https://testnet-explorer.nexa.org/tx/"), true);
  assert.equal(Object.keys(pub).includes("name"), false);
});

test("health stays silent about the secret until testnet signing is on", () => {
  const secret = "nexa-hot-key-material-not-for-logs-0123456789";
  const off = publicHealth({ NEXA_HOT_KEY: secret });
  assert.equal(off.signs, false);
  assert.equal(JSON.stringify(off).includes(secret), false);
  const on = publicHealth({ NEXA_HOT_KEY: secret, NC_EVENT_NFT: "1", MINT_NETWORK: "testnet" });
  assert.equal(on.signs, true);
  assert.equal(on.network, "testnet");
  assert.equal(JSON.stringify(on).includes(secret), false);
});

test("utxo lookup reads the testnet node and drops everything but the coins", async () => {
  const hot = nexaKey();
  const parent = parentGroup();
  const auth = GroupToken.authFlags.AUTHORITY | GroupToken.authFlags.MINT | GroupToken.authFlags.BATON | GroupToken.authFlags.SUBGROUP;
  const request = async (_url, method) => {
    if (method === "token.address.listunspent") {
      return { ok: true, result: { unspent: [{
        outpoint_hash: "11".repeat(32), value: 2000, group: parent, token_amount: auth.toString(), name: "hidden",
      }] } };
    }
    return { ok: true, result: [{ outpoint_hash: "22".repeat(32), value: 500000, from: "hidden" }] };
  };
  const got = await lookupUtxos({ NEXA_PARENT_GROUP: parent }, "nexa", hot.toWIF(), request);
  assert.equal(got.authority.groupAmount, auth.toString());
  assert.equal(got.funds[0].satoshis, 500000);
  assert.equal(JSON.stringify(got).includes("hidden"), false);
  assert.equal(JSON.stringify(got).includes(hot.toWIF()), false);
  const rounded = await lookupUtxos({ NEXA_PARENT_GROUP: parent }, "nexa", hot.toWIF(), async (_url, method) => {
    if (method === "token.address.listunspent") {
      return { ok: true, result: { unspent: [{
        outpoint_hash: "11".repeat(32), value: 2000, group: parent, token_amount: Number(auth),
      }] } };
    }
    return { ok: true, result: [{ outpoint_hash: "22".repeat(32), value: 500000 }] };
  });
  assert.equal(rounded, null);
});

test("a Bitcoin Cash lookup keeps the minting output and one funding coin", async () => {
  const secret = freshBchKey();
  const category = "33".repeat(32);
  const got = await lookupUtxos({ BCH_CATEGORY: category }, "bch", secret, async () => ({
    ok: true,
    result: [
      { tx_hash: "11".repeat(32), tx_pos: 0, value: 800, token_data: { category, amount: "0", nft: { capability: "minting", commitment: "" } } },
      { tx_hash: "22".repeat(32), tx_pos: 1, value: 80000 },
    ],
  }));
  assert.equal(got.minting.vout, 0);
  assert.equal(got.funding.satoshis, 80000);
  assert.equal(JSON.stringify(got).includes(secret), false);
});

test("a refill row is the incoming satoshis and the txid", () => {
  const address = "bchtest:qqexample";
  const row = refillFromTx({
    txid: "ab".repeat(32),
    time: 1760000000,
    name: "jQrgen",
    vin: [{ address: "bchtest:someone-else" }],
    vout: [
      { value: 50000, scriptPubKey: { addresses: [address] } },
      { value: 0.002, scriptPubKey: { addresses: ["bchtest:someone-else"] } },
    ],
  }, address);
  assert.equal(row.amount, 50000);
  assert.equal(row.txid, "ab".repeat(32));
  assert.equal(row.name, undefined);
  assert.equal(refillFromTx({
    txid: "cd".repeat(32),
    time: 1760000000,
    vin: [{ address }],
    vout: [{ value: 1000, scriptPubKey: { address } }],
  }, address), null);
  assert.equal(refillFromTx({
    txid: "ef".repeat(32),
    time: 1760000000,
    vin: [{ address: "bchtest:someone-else" }],
    vout: [{ value: 0.002, scriptPubKey: { address } }],
  }, address), null);
});
