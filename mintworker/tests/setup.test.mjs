import assert from "node:assert/strict";
import test from "node:test";
import { decodeTransaction, hexToBin } from "@bitauth/libauth";
import { PrivateKey } from "libnexa-ts";
import { freshBchKey, signBchGenesis, signBchMint } from "../src/bch/sign.js";
import { signNexaGroup } from "../src/nexa/sign.js";
import { assertOperatorNetwork, chainsFromArgs, networkFromArgs } from "../scripts/setup-tokens.mjs";

test("the setup script defaults to testnet and refuses mainnet without the flag", () => {
  assert.equal(networkFromArgs([]), "testnet");
  assert.equal(networkFromArgs(["--chain", "nexa"]), "testnet");
  assert.equal(networkFromArgs(["--mainnet"]), "mainnet");
  assert.throws(() => assertOperatorNetwork([], "no"), (e) => e.code === "not_operator");
  const net = assertOperatorNetwork(["--chain", "bch"], "yes");
  assert.equal(net, "testnet");
  assert.deepEqual(chainsFromArgs(["--chain", "nexa"]), ["nexa"]);
  assert.throws(() => chainsFromArgs(["--chain", "mainnet"]), (e) => e.code === "bad_chain");
});

test("a Nexa group id is a testnet group address and the key is not in the result", () => {
  const hot = PrivateKey.fromRandom("testnet");
  const signed = signNexaGroup({
    secret: hot.toWIF(),
    utxo: { outpoint: "11".repeat(32), satoshis: 500000 },
  });
  assert.equal(signed.group.startsWith("nexatest:"), true);
  assert.equal(signed.hotAddress.startsWith("nexatest:"), true);
  assert.equal(JSON.stringify(signed).includes(hot.toWIF()), false);
  assert.throws(() => signNexaGroup({
    secret: hot.toWIF(),
    utxo: { outpoint: "11".repeat(32), satoshis: 500000 },
    network: "regtest",
  }), (e) => e.code === "bad_network");
});

test("a CashTokens genesis category is the vout-0 parent txid", async () => {
  const secret = freshBchKey();
  const parent = "ab".repeat(32);
  const signed = signBchGenesis({
    secret,
    funding: { txid: parent, vout: 0, satoshis: 50000 },
  });
  assert.equal(signed.category, parent);
  assert.equal(signed.hex.includes(secret), false);
  const tx = decodeTransaction(hexToBin(signed.hex));
  assert.equal(typeof tx, "object");
  assert.equal(tx.outputs[0].token.nft.capability, "minting");
  assert.equal(tx.outputs[0].valueSatoshis, 800n);
  assert.equal(Buffer.from(tx.outputs[0].token.category).toString("hex"), parent);
  assert.throws(() => signBchGenesis({
    secret,
    funding: { txid: parent, vout: 1, satoshis: 50000 },
  }), (e) => e.code === "genesis_needs_vout0");
  await assert.rejects(() => signBchMint({
    secret,
    recipient: "bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx6a",
    categoryHex: "33".repeat(32),
    commitmentHex: "44".repeat(32),
    minting: { txid: "11".repeat(32), vout: 0, satoshis: 800 },
    funding: { txid: "22".repeat(32), vout: 1, satoshis: 80000 },
  }), (e) => e.code === "not_testnet_address");
});
