// Sign a Nexa testnet mint: one NFT (subgroup quantity 1) and the NEXA airdrop
// to the visitor. The mint authority and the change stay on the hot key.
// The key is the Worker secret. This module does not log it and does not
// broadcast. Mainnet is refused.

import {
  Address,
  AddressType,
  GroupToken,
  Networks,
  PrivateKey,
  ScriptFactory,
  Transaction,
  TransactionBuilder,
  UnitUtils,
} from "libnexa-ts";

const NETWORKS = { testnet: Networks.testnet, mainnet: Networks.mainnet };

export function nexaKey(secret, network) {
  if (network !== "testnet") {
    const err = new Error("mainnet_blocked");
    err.code = "mainnet_blocked";
    throw err;
  }
  const key = PrivateKey.fromWIF(String(secret).trim(), NETWORKS.testnet);
  if (key.network && key.network.name !== "testnet") {
    const err = new Error("mainnet_blocked");
    err.code = "mainnet_blocked";
    throw err;
  }
  return key;
}

export function signNexaMint({
  secret,
  recipient,
  parentGroup,
  zipUrl,
  zipHash,
  authority,
  funds,
  airdropNexa = 1000,
  feeCeilingSats = 2000,
}) {
  const key = nexaKey(secret, "testnet");
  const hot = key.toAddress().toString();
  if (!String(recipient).startsWith("nexatest:")) {
    const err = new Error("not_testnet_address");
    err.code = "not_testnet_address";
    throw err;
  }
  if (!authority || !authority.outpoint || authority.groupAmount == null) {
    const err = new Error("authority_missing");
    err.code = "authority_missing";
    throw err;
  }
  const opReturn = ScriptFactory.buildNFTDescription(zipUrl, zipHash);
  const subBuf = GroupToken.generateSubgroupId(parentGroup, zipHash);
  const subgroup = new Address(subBuf, Networks.testnet, AddressType.GroupIdAddress).toString();
  const airdropSats = UnitUtils.parseNEXA(String(airdropNexa));
  const builder = new TransactionBuilder();
  builder.from({
    outpoint: authority.outpoint,
    satoshis: Number(authority.satoshis),
    address: hot,
    groupId: parentGroup,
    groupAmount: BigInt(authority.groupAmount),
  });
  let inSats = BigInt(authority.satoshis);
  for (const u of funds || []) {
    builder.from({ outpoint: u.outpoint, satoshis: Number(u.satoshis), address: hot });
    inSats += BigInt(u.satoshis);
  }
  builder.addData(opReturn, true);
  builder.to(recipient, Transaction.DUST_AMOUNT, subgroup, 1n);
  builder.to(recipient, airdropSats);
  builder.to(hot, Transaction.DUST_AMOUNT, parentGroup, BigInt(authority.groupAmount));
  builder.change(hot);
  builder.feePerByte(Transaction.FEE_PER_BYTE);
  let tx;
  try {
    tx = builder.sign(key).build();
  } catch (e) {
    const err = new Error("sign_failed");
    err.code = "sign_failed";
    err.cause = e;
    throw err;
  }
  const outSats = tx.outputs.reduce((s, o) => s + o.value, 0n);
  const feeSats = inSats - outSats;
  if (feeSats <= 0n || feeSats > BigInt(feeCeilingSats)) {
    const err = new Error("fee_ceiling");
    err.code = "fee_ceiling";
    err.feeSats = feeSats;
    throw err;
  }
  return {
    hex: tx.serialize(),
    txid: tx.id,
    feeSats: Number(feeSats),
    airdropSats: Number(airdropSats),
    hotAddress: hot,
    subgroup,
  };
}
