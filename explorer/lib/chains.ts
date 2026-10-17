import type { ChainId, ChainMeta } from "./types";

/**
 * Servers checked from this environment on 12 Oct 2026.
 * A browser Origin of https://explorer.nordiccrypto.no completed the WebSocket
 * handshake (HTTP 101) on every URL below. electroncash.de:60002 and
 * bch.loping.net:50004 did not accept a connection, so they are not listed.
 * Port 443 is the same nginx TLS vhost as the published Electrum port, with
 * no extra path.
 */
export const chains: Record<ChainId, ChainMeta> = {
  bch: {
    id: "bch",
    name: "Bitcoin Cash",
    ticker: "BCH",
    decimals: 8,
    subunits: 100_000_000,
    feeEstimate: "coin-per-kb",
    target: "10 min",
    servers: [
      { url: "wss://electrum-bch.nordiccrypto.no:50004", label: "electrum-bch.nordiccrypto.no", primary: true },
      { url: "wss://electrum-bch.nordiccrypto.no", label: "electrum-bch.nordiccrypto.no:443", primary: false },
      { url: "wss://bch.imaginary.cash:50004", label: "bch.imaginary.cash", primary: false },
      { url: "wss://cashnode.bch.ninja:50004", label: "cashnode.bch.ninja", primary: false },
    ],
    apiHref: "https://nordiccrypto.no/api/",
    about: "Blocks, transactions and addresses, read in this browser from a Bitcoin Cash Electrum server.",
    backend: "electrum",
    feeUnit: "byte",
    tokens: true,
  },
  nexa: {
    id: "nexa",
    name: "Nexa",
    ticker: "NEX",
    decimals: 2,
    subunits: 100,
    feeEstimate: "sat-per-kb",
    target: "2 min",
    servers: [
      { url: "wss://electrum-nexa.nordiccrypto.no:20004", label: "electrum-nexa.nordiccrypto.no", primary: true },
      { url: "wss://electrum-nexa.nordiccrypto.no", label: "electrum-nexa.nordiccrypto.no:443", primary: false },
      { url: "wss://electrum.nexa.org:20004", label: "electrum.nexa.org", primary: false },
    ],
    apiHref: "https://nordiccrypto.no/api/",
    about: "Blocks, transactions and addresses, read in this browser from a Nexa Rostrum server.",
    backend: "electrum",
    feeUnit: "byte",
    tokens: true,
  },
  btc: {
    id: "btc",
    name: "Bitcoin",
    ticker: "BTC",
    decimals: 8,
    subunits: 100_000_000,
    feeEstimate: "sat-per-kb",
    target: "10 min",
    // Not a WebSocket: the public mempool.space REST API, called from the browser (CORS *).
    servers: [{ url: "https://mempool.space/api", label: "mempool.space", primary: true }],
    apiHref: "https://mempool.space/docs/api/rest",
    apiLabel: "API docs",
    about: "Blocks, transactions and addresses, read in this browser from the public mempool.space API.",
    backend: "mempool-space",
    feeUnit: "vB",
    tokens: false,
  },
};

/** Chain selector, nav, and static paths. Bitcoin Cash is the first choice; Bitcoin comes last. */
export const chainOrder = ["bch", "nexa", "btc"] as const satisfies readonly ChainId[];

export const defaultChain: ChainId = chainOrder[0];

/** Root `/` sends visitors here. */
export const homePath = `/${defaultChain}/`;

export function isChainId(value: string): value is ChainId {
  return (chainOrder as readonly string[]).includes(value);
}

/** A chain id from a query or path segment, or Bitcoin Cash when it is missing or unknown. */
export function resolveChain(value: string | null | undefined): ChainId {
  return value && isChainId(value) ? value : defaultChain;
}

export function getChain(id: string) {
  return isChainId(id) ? chains[id] : undefined;
}

/** Chains with a token directory page (`/{chain}/tokens`, `/{chain}/token`). */
export const tokenChains = chainOrder.filter((id) => chains[id].tokens);
