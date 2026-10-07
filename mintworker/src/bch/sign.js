// Sign a Bitcoin Cash testnet (chipnet / bchtest) CashTokens mint.
// Spends the minting-capability output, sends an immutable NFT plus the sat
// airdrop to the visitor, and returns the minting capability to the hot key.
// Mainnet (bitcoincash:) is refused.

import {
  binToHex,
  cashAddressToLockingBytecode,
  decodePrivateKeyWif,
  encodeTransaction,
  generatePrivateKey,
  generateTransaction,
  hashTransaction,
  hexToBin,
  instantiateRipemd160,
  instantiateSecp256k1,
  instantiateSha256,
  privateKeyToP2pkhCashAddress,
  walletTemplateP2pkhNonHd,
  walletTemplateToCompilerBCH,
} from "@bitauth/libauth";

const TOKEN_DUST = 800n;
const FEE_TARGET = 400n;

let cryptoKit;

async function kit() {
  if (!cryptoKit) {
    const sha256 = await instantiateSha256();
    const secp256k1 = await instantiateSecp256k1();
    const ripemd160 = await instantiateRipemd160();
    cryptoKit = {
      sha256,
      secp256k1,
      ripemd160,
      compiler: walletTemplateToCompilerBCH(walletTemplateP2pkhNonHd, { sha256, secp256k1, ripemd160 }),
    };
  }
  return cryptoKit;
}

export function bchKey(secret) {
  const raw = String(secret).trim();
  if (/^[0-9a-fA-F]{64}$/.test(raw)) return hexToBin(raw);
  const decoded = decodePrivateKeyWif(raw);
  if (typeof decoded === "string") {
    const err = new Error("bad_key");
    err.code = "bad_key";
    throw err;
  }
  return decoded.privateKey;
}

export async function bchAddress(secret) {
  const { sha256, ripemd160 } = await kit();
  const address = privateKeyToP2pkhCashAddress({
    privateKey: bchKey(secret),
    prefix: "bchtest",
    tokenSupport: true,
    sha256,
    ripemd160,
  });
  if (typeof address === "string") {
    const err = new Error("bad_key");
    err.code = "bad_key";
    throw err;
  }
  return address.address;
}

function lock(compiler, privateKey) {
  return { compiler, script: "lock", data: { keys: { privateKeys: { key: privateKey } } } };
}

function unlock(compiler, privateKey, valueSatoshis, token) {
  const directive = {
    compiler,
    script: "unlock",
    valueSatoshis,
    data: { keys: { privateKeys: { key: privateKey } } },
  };
  if (token) directive.token = token;
  return directive;
}

export async function signBchMint({
  secret,
  recipient,
  categoryHex,
  commitmentHex,
  minting,
  funding,
  airdropSats = 10000,
  feeCeilingSats = 1500,
}) {
  if (!String(recipient).startsWith("bchtest:")) {
    const err = new Error("not_testnet_address");
    err.code = "not_testnet_address";
    throw err;
  }
  const { compiler, sha256 } = await kit();
  const privateKey = bchKey(secret);
  const hot = await bchAddress(secret);
  const category = hexToBin(categoryHex);
  const commitment = hexToBin(commitmentHex);
  if (category.length !== 32 || commitment.length < 1 || commitment.length > 40) {
    const err = new Error("bad_token");
    err.code = "bad_token";
    throw err;
  }
  const mintingValue = BigInt(minting.satoshis);
  const fundingValue = BigInt(funding.satoshis);
  const airdrop = BigInt(airdropSats);
  const fee = FEE_TARGET <= BigInt(feeCeilingSats) ? FEE_TARGET : BigInt(feeCeilingSats);
  const change = fundingValue + mintingValue - mintingValue - TOKEN_DUST - airdrop - fee;
  if (change < 546n) {
    const err = new Error("insufficient_funds");
    err.code = "insufficient_funds";
    throw err;
  }
  if (fee > BigInt(feeCeilingSats) || TOKEN_DUST + fee > BigInt(feeCeilingSats)) {
    const err = new Error("fee_ceiling");
    err.code = "fee_ceiling";
    throw err;
  }
  const mintingToken = { amount: 0n, category, nft: { capability: "minting", commitment: new Uint8Array() } };
  const childToken = { amount: 0n, category, nft: { capability: "none", commitment } };
  const attempt = generateTransaction({
    version: 2,
    locktime: 0,
    inputs: [
      {
        outpointIndex: minting.vout ?? 0,
        outpointTransactionHash: hexToBin(minting.txid),
        sequenceNumber: 0xffffffff,
        unlockingBytecode: unlock(compiler, privateKey, mintingValue, mintingToken),
      },
      {
        outpointIndex: funding.vout ?? 0,
        outpointTransactionHash: hexToBin(funding.txid),
        sequenceNumber: 0xffffffff,
        unlockingBytecode: unlock(compiler, privateKey, fundingValue),
      },
    ],
    outputs: [
      { lockingBytecode: lock(compiler, privateKey), valueSatoshis: mintingValue, token: mintingToken },
      { lockingBytecode: cashAddressToLockingBytecode(recipient).bytecode, valueSatoshis: TOKEN_DUST, token: childToken },
      { lockingBytecode: cashAddressToLockingBytecode(recipient).bytecode, valueSatoshis: airdrop },
      { lockingBytecode: lock(compiler, privateKey), valueSatoshis: change },
    ],
  });
  if (!attempt.success) {
    const err = new Error("sign_failed");
    err.code = "sign_failed";
    throw err;
  }
  const raw = encodeTransaction(attempt.transaction);
  const spent = TOKEN_DUST + airdrop + fee;
  return {
    hex: binToHex(raw),
    txid: hashTransaction(raw, sha256),
    feeSats: Number(fee),
    airdropSats: Number(airdrop),
    hotAddress: hot,
    spentSats: Number(spent),
  };
}

export function freshBchKey() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return binToHex(generatePrivateKey(() => bytes));
}
