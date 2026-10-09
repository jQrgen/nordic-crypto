// Nexa signed message, the same check Wally uses for a NexaID login.
// The challenge binds the chain, the event and the address. A signature from
// another address or another event does not pass.

import { Message, PrivateKey } from "libnexa-ts";
import { nexaKey } from "./sign.js";

export function challenge(chain, eventId, address) {
  return `nordic-crypto-mint|${chain}|${String(eventId)}|${String(address).trim()}`;
}

export function signNexaChallenge(secret, eventId, address) {
  const key = nexaKey(secret, "testnet");
  return new Message(challenge("nexa", eventId, address)).sign(key);
}

export function verifyNexaChallenge({ address, eventId, signature }) {
  if (!address || !eventId || !signature) return false;
  if (!String(address).startsWith("nexatest:")) return false;
  try {
    return new Message(challenge("nexa", eventId, address)).verify(address, signature);
  } catch {
    return false;
  }
}

export function nexaAddressOf(secret) {
  return PrivateKey.fromWIF(String(secret).trim(), "testnet").toAddress().toString();
}
