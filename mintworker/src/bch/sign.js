// Sign a Bitcoin Cash testnet (chipnet / bchtest) CashTokens mint.
// Spends the minting-capability output, sends an immutable NFT plus the sat
// airdrop to the visitor, and returns the minting capability to the hot key.
// Mainnet (bitcoincash:) is refused by signBchMint. The setup script is the
// only caller that may pass prefix "bitcoincash", and only after --mainnet.

import {
  bytesToHex,
  compactUint,
  compressedPublicKey,
  concat,
  decodeCashAddr,
  decodeWif,
  encodeCashAddr,
  hash160,
  hexToBytes,
  lockingBytecode,
  p2pkhLock,
  pushScript,
  randomPrivateKey,
  reversed,
  schnorrSign,
  sha256d,
  u32le,
  u64le,
} from "./crypto.js";

const TOKEN_DUST = 800n;
const FEE_TARGET = 400n;
const SIGHASH_ALL_FORKID = 0x41;

function fail(code) {
  const err = new Error(code);
  err.code = code;
  return err;
}

export function bchKey(secret) {
  const raw = String(secret).trim();
  if (/^[0-9a-fA-F]{64}$/.test(raw)) {
    const key = hexToBytes(raw);
    if (!secpValid(key)) throw fail("bad_key");
    return key;
  }
  const decoded = decodeWif(raw);
  if (!decoded || !secpValid(decoded)) throw fail("bad_key");
  return decoded;
}

function secpValid(key) {
  try {
    compressedPublicKey(key);
    return true;
  } catch {
    return false;
  }
}

export function bchAddress(secret, { prefix = "bchtest", tokenSupport = true } = {}) {
  const pub = compressedPublicKey(bchKey(secret));
  const typeBits = tokenSupport ? 2 : 0;
  return encodeCashAddr(prefix, typeBits, hash160(pub));
}

function encodeTokenPrefix(token) {
  if (!token || (token.nft == null && token.amount < 1n)) return new Uint8Array();
  const hasNft = token.nft ? 0x20 : 0;
  const capability = token.nft ? { none: 0, mutable: 1, minting: 2 }[token.nft.capability] : 0;
  if (token.nft && capability === undefined) throw fail("bad_token");
  const commitment = token.nft ? token.nft.commitment : new Uint8Array();
  const hasCommitment = token.nft && commitment.length > 0 ? 0x40 : 0;
  const hasAmount = token.amount > 0n ? 0x10 : 0;
  const parts = [Uint8Array.of(0xef), reversed(token.category), Uint8Array.of(hasNft | hasCommitment | hasAmount | capability)];
  if (hasCommitment) parts.push(compactUint(BigInt(commitment.length)), commitment);
  if (hasAmount) parts.push(compactUint(token.amount));
  return concat(parts);
}

function encodeOutput(output) {
  const script = concat([encodeTokenPrefix(output.token), output.lockingBytecode]);
  return concat([u64le(output.valueSatoshis), compactUint(BigInt(script.length)), script]);
}

function encodeInput(input) {
  return concat([
    reversed(input.txid),
    u32le(input.vout),
    compactUint(BigInt(input.unlock.length)),
    input.unlock,
    u32le(input.sequence),
  ]);
}

export function encodeBchTx(tx) {
  return concat([
    u32le(tx.version),
    compactUint(BigInt(tx.inputs.length)),
    ...tx.inputs.map(encodeInput),
    compactUint(BigInt(tx.outputs.length)),
    ...tx.outputs.map(encodeOutput),
    u32le(tx.locktime),
  ]);
}

function txidOf(raw) {
  return bytesToHex(reversed(sha256d(raw)));
}

// BCH sighash (SIGHASH_ALL | SIGHASH_FORKID, without SIGHASH_UTXOS).
// The CashTokens prefix sits in front of the covered locking script and is
// empty when the spent output has no token. hashUtxos is omitted unless the
// UTXOS flag is set, so it is not part of this serialization.
function sighash(tx, index, source, covered, tokenPrefix) {
  const prevouts = concat(tx.inputs.map((input) => concat([reversed(input.txid), u32le(input.vout)])));
  const sequences = concat(tx.inputs.map((input) => u32le(input.sequence)));
  const outputs = concat(tx.outputs.map(encodeOutput));
  const input = tx.inputs[index];
  return sha256d(concat([
    u32le(tx.version),
    sha256d(prevouts),
    sha256d(sequences),
    reversed(input.txid),
    u32le(input.vout),
    tokenPrefix,
    compactUint(BigInt(covered.length)),
    covered,
    u64le(source.valueSatoshis),
    u32le(input.sequence),
    sha256d(outputs),
    u32le(tx.locktime),
    Uint8Array.of(SIGHASH_ALL_FORKID, 0, 0, 0),
  ]));
}

function signInput(privateKey, tx, index, source, covered) {
  const prefix = encodeTokenPrefix(source.token);
  const digest = sighash(tx, index, source, covered, prefix);
  const sig = concat([schnorrSign(digest, privateKey), Uint8Array.of(SIGHASH_ALL_FORKID)]);
  const pub = compressedPublicKey(privateKey);
  return pushScript([sig, pub]);
}

function lockOf(privateKey) {
  return p2pkhLock(hash160(compressedPublicKey(privateKey)));
}

function recipientLock(address, prefix) {
  const decoded = decodeCashAddr(address);
  if (!decoded || decoded.prefix !== prefix) throw fail(prefix === "bchtest" ? "not_testnet_address" : "bad_address");
  return lockingBytecode(decoded.typeBits, decoded.hash);
}

function txidBytes(hex) {
  const bytes = hexToBytes(hex);
  if (bytes.length !== 32) throw fail("bad_token");
  return bytes;
}

function buildSigned({ privateKey, inputs, outputs }) {
  const tx = {
    version: 2,
    locktime: 0,
    inputs: inputs.map((input) => ({
      txid: input.txid,
      vout: input.vout,
      sequence: 0xffffffff,
      unlock: new Uint8Array(),
    })),
    outputs,
  };
  tx.inputs.forEach((input, index) => {
    input.unlock = signInput(privateKey, tx, index, inputs[index].source, inputs[index].covered);
  });
  const raw = encodeBchTx(tx);
  return { raw, txid: txidOf(raw) };
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
  if (!String(recipient).startsWith("bchtest:")) throw fail("not_testnet_address");
  const privateKey = bchKey(secret);
  const hot = bchAddress(secret);
  const category = hexToBytes(categoryHex);
  const commitment = hexToBytes(commitmentHex);
  if (category.length !== 32 || commitment.length < 1 || commitment.length > 40) throw fail("bad_token");
  const mintingValue = BigInt(minting.satoshis);
  const fundingValue = BigInt(funding.satoshis);
  const airdrop = BigInt(airdropSats);
  const fee = FEE_TARGET <= BigInt(feeCeilingSats) ? FEE_TARGET : BigInt(feeCeilingSats);
  const change = fundingValue + mintingValue - mintingValue - TOKEN_DUST - airdrop - fee;
  if (change < 546n) throw fail("insufficient_funds");
  if (fee > BigInt(feeCeilingSats) || TOKEN_DUST + fee > BigInt(feeCeilingSats)) throw fail("fee_ceiling");
  const hotLock = lockOf(privateKey);
  const visitorLock = recipientLock(recipient, "bchtest");
  const mintingToken = { amount: 0n, category, nft: { capability: "minting", commitment: new Uint8Array() } };
  const childToken = { amount: 0n, category, nft: { capability: "none", commitment } };
  const signed = buildSigned({
    privateKey,
    inputs: [
      { txid: txidBytes(minting.txid), vout: minting.vout ?? 0, source: { valueSatoshis: mintingValue, token: mintingToken }, covered: hotLock },
      { txid: txidBytes(funding.txid), vout: funding.vout ?? 0, source: { valueSatoshis: fundingValue }, covered: hotLock },
    ],
    outputs: [
      { lockingBytecode: hotLock, valueSatoshis: mintingValue, token: mintingToken },
      { lockingBytecode: visitorLock, valueSatoshis: TOKEN_DUST, token: childToken },
      { lockingBytecode: visitorLock, valueSatoshis: airdrop },
      { lockingBytecode: hotLock, valueSatoshis: change },
    ],
  });
  return {
    hex: bytesToHex(signed.raw),
    txid: signed.txid,
    feeSats: Number(fee),
    airdropSats: Number(airdrop),
    hotAddress: hot,
    spentSats: Number(TOKEN_DUST + airdrop + fee),
  };
}

// Create the category. The category id is the transaction id of the output 0
// being spent (CHIP-2022-02). The new output is a minting NFT on the hot key.
export function signBchGenesis({ secret, funding, prefix = "bchtest", feeSats = 400 }) {
  if (prefix !== "bchtest" && prefix !== "bitcoincash") throw fail("bad_network");
  if (Number(funding.vout) !== 0) throw fail("genesis_needs_vout0");
  const privateKey = bchKey(secret);
  const hotLock = lockOf(privateKey);
  const value = BigInt(funding.satoshis);
  const fee = BigInt(feeSats);
  const change = value - TOKEN_DUST - fee;
  if (change < 546n) throw fail("insufficient_funds");
  const category = txidBytes(funding.txid);
  const mintingToken = { amount: 0n, category, nft: { capability: "minting", commitment: new Uint8Array() } };
  const signed = buildSigned({
    privateKey,
    inputs: [
      { txid: category, vout: 0, source: { valueSatoshis: value }, covered: hotLock },
    ],
    outputs: [
      { lockingBytecode: hotLock, valueSatoshis: TOKEN_DUST, token: mintingToken },
      { lockingBytecode: hotLock, valueSatoshis: change },
    ],
  });
  return {
    hex: bytesToHex(signed.raw),
    txid: signed.txid,
    category: bytesToHex(category),
    hotAddress: bchAddress(secret, { prefix, tokenSupport: true }),
  };
}

// Pay the hot address at output 0 so a later genesis has a vout-0 coin.
export function signBchToSelf({ secret, funding, prefix = "bchtest", feeSats = 400 }) {
  if (prefix !== "bchtest" && prefix !== "bitcoincash") throw fail("bad_network");
  const privateKey = bchKey(secret);
  const hotLock = lockOf(privateKey);
  const value = BigInt(funding.satoshis);
  const fee = BigInt(feeSats);
  const pay = value - fee;
  if (pay < 546n) throw fail("insufficient_funds");
  const signed = buildSigned({
    privateKey,
    inputs: [
      { txid: txidBytes(funding.txid), vout: funding.vout ?? 0, source: { valueSatoshis: value }, covered: hotLock },
    ],
    outputs: [{ lockingBytecode: hotLock, valueSatoshis: pay }],
  });
  return {
    hex: bytesToHex(signed.raw),
    txid: signed.txid,
    vout: 0,
    satoshis: Number(pay),
    hotAddress: bchAddress(secret, { prefix, tokenSupport: true }),
  };
}

export function freshBchKey() {
  return bytesToHex(randomPrivateKey());
}

export function readTokenOutput(script) {
  if (!script.length || script[0] !== 0xef || script.length < 34) return null;
  const category = reversed(script.subarray(1, 33));
  const bitfield = script[33];
  if (bitfield & 0x80) return null;
  const capability = ["none", "mutable", "minting"][bitfield & 15] || null;
  const hasNft = (bitfield & 0x20) !== 0;
  return {
    category: bytesToHex(category),
    capability: hasNft ? capability : null,
    fungible: (bitfield & 0x10) !== 0,
  };
}
