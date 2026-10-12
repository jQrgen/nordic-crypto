import { chains } from "./chains";
import { formatNumber, shortId } from "./format";
import { chainForAddress, addressHref, blockHref, txHref } from "./routes";
import type { ChainId, SearchHit } from "./types";

/** Classify a search box query into a page. The page asks the chain whether it exists. */
export function interpretQuery(raw: string, preferred: ChainId): SearchHit[] {
  const q = raw.trim();
  if (!q) return [];
  const compact = q.replace(/\s/g, "");
  if (/^\d{1,10}$/.test(compact)) {
    const height = Number(compact);
    return [
      {
        href: blockHref(preferred, height),
        chain: preferred,
        kind: "Block",
        title: formatNumber(height),
        detail: chains[preferred].name,
      },
    ];
  }
  if (/^[0-9a-fA-F]{64}$/.test(compact)) {
    const txid = compact.toLowerCase();
    return [
      {
        href: txHref(preferred, txid),
        chain: preferred,
        kind: "Transaction",
        title: shortId(txid, 12, 6),
        detail: chains[preferred].name,
      },
    ];
  }
  const chain = chainForAddress(q);
  if (!chain) return [];
  return [
    {
      href: addressHref(chain, q),
      chain,
      kind: "Address",
      title: shortId(q, 22, 6),
      detail: chains[chain].name,
    },
  ];
}

export function chainName(id: ChainId) {
  return chains[id].name;
}
