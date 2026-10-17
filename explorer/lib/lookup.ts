import { chains } from "./chains";
import { formatNumber, shortId } from "./format";
import { isBlockHash } from "./mempool-space";
import { chainForAddress, addressHref, blockHashHref, blockHref, isLegacyAddress, txHref } from "./routes";
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
    // A Bitcoin block hash starts with many zero digits; a txid essentially never does.
    if (preferred === "btc" && isBlockHash(txid)) {
      return [
        {
          href: blockHashHref(preferred, txid),
          chain: preferred,
          kind: "Block",
          title: shortId(txid, 12, 6),
          detail: chains[preferred].name,
        },
      ];
    }
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
  if (isLegacyAddress(q)) {
    // 1… and 3… are valid on Bitcoin and Bitcoin Cash. Offer both, the chain you are on first.
    const both: ChainId[] = preferred === "bch" ? ["bch", "btc"] : ["btc", "bch"];
    return both.map((chain) => ({
      href: addressHref(chain, q),
      chain,
      kind: "Address",
      title: shortId(q, 22, 6),
      detail: chains[chain].name,
    }));
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
