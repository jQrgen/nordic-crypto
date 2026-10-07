// Bitcoin Cash signed message, the format Electron Cash and CashConnect's
// bch_signMessage use: the "Bitcoin Signed Message:\n" prefix and a
// recoverable compact signature. The challenge binds the chain, the event
// and the address.

import {
  binToHex,
  cashAddressToLockingBytecode,
  decodeCashAddress,
  encodeCashAddress,
  flattenBinArray,
  hexToBin,
  instantiateRipemd160,
  instantiateSecp256k1,
  instantiateSha256,
  publicKeyToP2pkhCashAddress,
} from "@bitauth/libauth";
import { bchKey } from "./sign.js";
import { challenge } from "../nexa/message.js";

function pushVar(bytes) {
  const n = bytes.length;
  if (n < 253) return flattenBinArray([Uint8Array.of(n), bytes]);
  const len = new Uint8Array(3);
  len[0] = 253;
  len[1] = n & 0xff;
  len[2] = (n >> 8) & 0xff;
  return flattenBinArray([len, bytes]);
}

async function magicHash(message) {
  const sha256 = await instantiateSha256();
  const prefix = new TextEncoder().encode("Bitcoin Signed Message:\n");
  const body = new TextEncoder().encode(message);
  const payload = flattenBinArray([pushVar(prefix), pushVar(body)]);
  return sha256.hash(sha256.hash(payload));
}

function encodeSignature({ recoveryId, signature }) {
  const out = new Uint8Array(65);
  out[0] = 31 + recoveryId;
  out.set(signature, 1);
  return out;
}

export async function signBchChallenge(secret, eventId, address) {
  const secp = await instantiateSecp256k1();
  const hash = await magicHash(challenge("bch", eventId, address));
  const signed = secp.signMessageHashRecoverableCompact(bchKey(secret), hash);
  if (typeof signed === "string") return null;
  return Buffer.from(encodeSignature(signed)).toString("base64");
}

export async function verifyBchChallenge({ address, eventId, signature }) {
  if (!address || !eventId || !signature) return false;
  if (!String(address).startsWith("bchtest:")) return false;
  let raw;
  try {
    raw = Buffer.from(signature, "base64");
  } catch {
    return false;
  }
  if (raw.length !== 65) return false;
  const header = raw[0];
  if (header < 31 || header > 34) return false;
  const recoveryId = header - 31;
  const compact = raw.subarray(1);
  const secp = await instantiateSecp256k1();
  const hash = await magicHash(challenge("bch", eventId, address));
  const pub = secp.recoverPublicKeyCompressed(compact, recoveryId, hash);
  if (typeof pub === "string") return false;
  const sha256 = await instantiateSha256();
  const ripemd160 = await instantiateRipemd160();
  const got = publicKeyToP2pkhCashAddress({ publicKey: pub, prefix: "bchtest", tokenSupport: true, sha256, ripemd160 });
  const plain = publicKeyToP2pkhCashAddress({ publicKey: pub, prefix: "bchtest", tokenSupport: false, sha256, ripemd160 });
  const decoded = decodeCashAddress(address);
  if (typeof decoded === "string") return false;
  const matches = (candidate) => {
    if (!candidate || typeof candidate === "string" || !candidate.address) return false;
    const other = decodeCashAddress(candidate.address);
    return typeof other !== "string" && binToHex(other.payload) === binToHex(decoded.payload);
  };
  return matches(got) || matches(plain);
}

export { challenge, hexToBin, encodeCashAddress, cashAddressToLockingBytecode };
