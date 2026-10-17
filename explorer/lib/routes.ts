import type { ChainId } from "./types";

export function blockHref(chain: ChainId, height: number) {
  return `/${chain}/block/?height=${height}`;
}

export function blockHashHref(chain: ChainId, hash: string) {
  return `/${chain}/block/?hash=${encodeURIComponent(hash)}`;
}

export function txHref(chain: ChainId, txid: string) {
  return `/${chain}/tx/?txid=${encodeURIComponent(txid)}`;
}

export function addressHref(chain: ChainId, address: string) {
  return `/${chain}/address/?address=${encodeURIComponent(address)}`;
}

export function tokenHref(chain: ChainId, id: string) {
  return `/${chain}/token/?id=${encodeURIComponent(id)}`;
}

const PRETTY = /^\/(bch|nexa|btc)\/(block|tx|address|token)\/([^/]+)\/?$/;

/** Path-style URLs become the static-export query pages. Returns null when the path is already a shell. */
export function prettyRedirect(pathname: string): string | null {
  const match = pathname.match(PRETTY);
  if (!match) return null;
  const chain = match[1] as ChainId;
  const kind = match[2];
  const value = decodeURIComponent(match[3]);
  if (kind === "block") return /^[0-9a-f]{64}$/i.test(value) ? blockHashHref(chain, value) : blockHref(chain, Number(value));
  if (kind === "tx") return txHref(chain, value);
  if (kind === "address") return addressHref(chain, value);
  return tokenHref(chain, value);
}

export function chainForAddress(raw: string): ChainId | null {
  const q = raw.trim();
  const lower = q.toLowerCase();
  if (lower.startsWith("bitcoincash:") || lower.startsWith("bchtest:") || lower.startsWith("bchreg:")) return "bch";
  if (lower.startsWith("nexa:") || lower.startsWith("nexatest:") || lower.startsWith("nexareg:")) return "nexa";
  if (/^n[qp][0-9a-z]{20,}$/i.test(q)) return "nexa";
  if (/^[qp][0-9a-z]{40,}$/i.test(q)) return "bch";
  if (/^bc1[02-9ac-hj-np-z]{11,87}$/i.test(q)) return "btc";
  return null;
}

/** Base58 legacy addresses (1…, 3…) are valid on both Bitcoin and Bitcoin Cash. */
export function isLegacyAddress(raw: string) {
  return /^[13][1-9A-HJ-NP-Za-km-z]{25,34}$/.test(raw.trim());
}
