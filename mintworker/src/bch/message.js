// Bitcoin Cash signed message, the format Electron Cash and CashConnect's
// bch_signMessage use: the "Bitcoin Signed Message:\n" prefix and a
// recoverable compact signature. The challenge binds the chain, the event
// and the address.

import { challenge } from "../nexa/message.js";
import { bchKey } from "./sign.js";
import {
  base64ToBytes,
  bytesToBase64,
  compactUint,
  concat,
  decodeCashAddr,
  ecdsaRecoverable,
  hash160,
  recoverCompressed,
  sha256d,
} from "./crypto.js";

function magicHash(message) {
  const prefix = new TextEncoder().encode("Bitcoin Signed Message:\n");
  const body = new TextEncoder().encode(message);
  return sha256d(concat([compactUint(BigInt(prefix.length)), prefix, compactUint(BigInt(body.length)), body]));
}

export async function signBchChallenge(secret, eventId, address) {
  const hash = magicHash(challenge("bch", eventId, address));
  const signed = ecdsaRecoverable(hash, bchKey(secret));
  const out = new Uint8Array(65);
  out[0] = 31 + signed.recovery;
  out.set(signed.compact, 1);
  return bytesToBase64(out);
}

function samePayload(address, publicKey) {
  const decoded = decodeCashAddr(address);
  if (!decoded || decoded.prefix !== "bchtest" || decoded.hash.length !== 20) return false;
  const hash = hash160(publicKey);
  if (hash.length !== decoded.hash.length) return false;
  for (let i = 0; i < hash.length; i++) if (hash[i] !== decoded.hash[i]) return false;
  return decoded.typeBits === 0 || decoded.typeBits === 2;
}

export async function verifyBchChallenge({ address, eventId, signature }) {
  if (!address || !eventId || !signature) return false;
  if (!String(address).startsWith("bchtest:")) return false;
  let raw;
  try {
    raw = base64ToBytes(signature);
  } catch {
    return false;
  }
  if (raw.length !== 65) return false;
  const header = raw[0];
  if (header < 31 || header > 34) return false;
  try {
    const hash = magicHash(challenge("bch", eventId, address));
    const pub = recoverCompressed(raw.subarray(1), header - 31, hash);
    return samePayload(address, pub);
  } catch {
    return false;
  }
}

export { challenge };
