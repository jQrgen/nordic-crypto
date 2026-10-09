// What a public testnet node says about a transaction this Worker would sign.
// The inputs are not funded (the faucet needs a wallet), so a confirming mint
// is not expected. A decode error is a failure of the signer. A missing-input
// error means the node parsed the transaction.

import test from "node:test";
import assert from "node:assert/strict";
import { PrivateKey, Address, AddressType, GroupToken, Networks } from "libnexa-ts";
import { signNexaMint } from "../src/nexa/sign.js";
import { freshBchKey, signBchMint, bchAddress } from "../src/bch/sign.js";
import { broadcastBch, broadcastNexa, nexaTip } from "../src/broadcast.js";

test("Nexa testnet parses a signed mint", async () => {
  const tip = await nexaTip();
  assert.equal(tip.ok, true, JSON.stringify(tip.error || tip));
  const hot = PrivateKey.fromRandom("testnet");
  const visitor = PrivateKey.fromRandom("testnet");
  const parent = new Address(Uint8Array.from({ length: 32 }, (_, i) => i + 3), Networks.testnet, AddressType.GroupIdAddress).toString();
  const auth = GroupToken.authFlags.AUTHORITY | GroupToken.authFlags.MINT | GroupToken.authFlags.BATON | GroupToken.authFlags.SUBGROUP;
  const signed = signNexaMint({
    secret: hot.toWIF(),
    recipient: visitor.toAddress().toString(),
    parentGroup: parent,
    zipUrl: "https://nordiccrypto.no/assets/nft/card.zip",
    zipHash: "ab".repeat(32),
    authority: { outpoint: "11".repeat(32), satoshis: 2000, groupAmount: auth },
    funds: [{ outpoint: "22".repeat(32), satoshis: 500000 }],
  });
  const sent = await broadcastNexa(signed.hex);
  const text = JSON.stringify(sent.error || sent.result || sent);
  console.log("NEXA_NODE", text);
  assert.equal(/decode|deserialization|parse/i.test(text), false, text);
  assert.equal(sent.ok, false);
});

test("Bitcoin Cash chipnet parses a signed mint", async () => {
  const hot = freshBchKey();
  const who = freshBchKey();
  const signed = await signBchMint({
    secret: hot,
    recipient: await bchAddress(who),
    categoryHex: "33".repeat(32),
    commitmentHex: "44".repeat(32),
    minting: { txid: "11".repeat(32), vout: 0, satoshis: 800 },
    funding: { txid: "22".repeat(32), vout: 1, satoshis: 80000 },
  });
  const sent = await broadcastBch(signed.hex);
  const text = JSON.stringify(sent.error || sent.result || sent);
  console.log("BCH_NODE", text.slice(0, 500));
  assert.equal(/decode failed|deserialization/i.test(text), false, text);
  assert.equal(sent.ok, false);
});
