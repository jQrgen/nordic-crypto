import type { ChainId } from "./types";

export function blockHref(chain: ChainId, height: number) {
  return `/${chain}/block/?height=${height}`;
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

const PRETTY = /^\/(bch|nexa)\/(block|tx|address|token)\/([^/]+)\/?$/;

/** Path-style URLs become the static-export query pages. Returns null when the path is already a shell. */
export function prettyRedirect(pathname: string): string | null {
  const match = pathname.match(PRETTY);
  if (!match) return null;
  const chain = match[1] as ChainId;
  const kind = match[2];
  const value = decodeURIComponent(match[3]);
  if (kind === "block") return blockHref(chain, Number(value));
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
  return null;
}
