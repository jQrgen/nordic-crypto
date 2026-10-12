import { addresses, blocks, chains, getAddress, getToken, getTx, tokens, txs } from "./data";
import { formatNumber, shortId } from "./format";
import type { ChainId, SearchHit } from "./types";

function hit(partial: SearchHit): SearchHit {
  return partial;
}

export function searchAll(raw: string, preferred: ChainId): SearchHit[] {
  const q = raw.trim();
  if (!q) return [];
  const folded = q.toLowerCase().replace(/\s/g, "");
  const hits: SearchHit[] = [];
  const seen = new Set<string>();
  const add = (item: SearchHit) => {
    if (seen.has(item.href)) return;
    seen.add(item.href);
    hits.push(item);
  };

  if (/^\d{1,10}$/.test(folded)) {
    const height = Number(folded);
    const ordered = [preferred, preferred === "nexa" ? "bch" : "nexa"] as ChainId[];
    for (const chain of ordered) {
      const block = blocks.find((b) => b.chain === chain && b.height === height);
      if (block) {
        add(
          hit({
            href: `/${chain}/block/${block.height}`,
            chain,
            kind: "Block",
            title: formatNumber(block.height),
            detail: block.miner,
          }),
        );
      }
    }
  }

  for (const token of tokens) {
    if (token.ticker.toLowerCase() === folded || token.name.toLowerCase() === folded || token.id === folded) {
      add(
        hit({
          href: `/${token.chain}/token/${token.id}`,
          chain: token.chain,
          kind: "Token",
          title: token.ticker,
          detail: token.name,
        }),
      );
    }
  }

  for (const tx of txs) {
    if (tx.id.toLowerCase() === folded || tx.hash === folded || (folded.length >= 8 && tx.hash.startsWith(folded))) {
      add(
        hit({
          href: `/${tx.chain}/tx/${tx.id}`,
          chain: tx.chain,
          kind: tx.coinbase ? "Coinbase" : "Transaction",
          title: shortId(tx.hash, 12, 6),
          detail: tx.blockHeight ? `Block ${formatNumber(tx.blockHeight)}` : "In the mempool",
        }),
      );
    }
  }

  for (const address of addresses) {
    const label = address.label?.toLowerCase() ?? "";
    const full = address.address.toLowerCase();
    if (
      address.id.toLowerCase() === folded ||
      label === q.trim().toLowerCase() ||
      full === folded ||
      (folded.length >= 12 && full.includes(folded))
    ) {
      add(
        hit({
          href: `/${address.chain}/address/${address.id}`,
          chain: address.chain,
          kind: "Address",
          title: address.label ?? shortId(address.address),
          detail: shortId(address.address, 22, 6),
        }),
      );
    }
  }

  for (const block of blocks) {
    if (folded.length >= 8 && block.hash.startsWith(folded)) {
      add(
        hit({
          href: `/${block.chain}/block/${block.height}`,
          chain: block.chain,
          kind: "Block",
          title: formatNumber(block.height),
          detail: "Block hash",
        }),
      );
    }
  }

  hits.sort((a, b) => {
    if (a.chain === preferred && b.chain !== preferred) return -1;
    if (b.chain === preferred && a.chain !== preferred) return 1;
    return a.kind.localeCompare(b.kind);
  });
  return hits;
}

export function chainName(id: ChainId) {
  return chains[id].name;
}

export function addressById(id: string) {
  return getAddress(id);
}

export function tokenById(id: string) {
  return getToken(id);
}

export function txById(id: string) {
  return getTx(id);
}
