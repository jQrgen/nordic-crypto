import type { Address, Block, ChainId, ChainInfo, TokenInfo, Tx } from "./types";

const NEX_USD = 0.0000010506;
const NOK_PER_USD = 2618.38 / 273.34;
const SEK_PER_USD = 2745.13 / 273.34;
const DKK_PER_USD = 1831.5 / 273.34;
const EUR_PER_USD = 245 / 273.34;

function fakeHash(seed: string) {
  let x = 2166136261;
  for (const c of seed) x = Math.imul(x ^ c.charCodeAt(0), 16777619);
  let h = "";
  const alphabet = "0123456789abcdef";
  for (let i = 0; i < 64; i++) {
    x = Math.imul(x ^ (x >>> 13), 2246822519) >>> 0;
    h += alphabet[x & 15];
  }
  return h;
}

export const chains: Record<ChainId, ChainInfo> = {
  bch: {
    id: "bch",
    name: "Bitcoin Cash",
    ticker: "BCH",
    decimals: 8,
    target: "10 min",
    height: 972618,
    mempoolCount: 93,
    prices: {
      USD: 273.34,
      NOK: 2618.38,
      SEK: 2745.13,
      DKK: 1831.5,
      EUR: 245,
    },
    change24h: -3.8,
    supply: 20_102_169,
    hashrate: "3.57 EH/s",
    difficulty: "491,316,613,434",
    size: "202.5 GB",
    utxo: "public set",
    txCount: "417,496,980",
    serverName: "electrum-bch.nordiccrypto.no",
    serverUrl: "wss://electrum-bch.nordiccrypto.no:50004",
    apiHref: "https://nordiccrypto.no/api/",
    about:
      "Blocks, transactions, addresses and CashTokens, read from Nordic Crypto’s own Rostrum server.",
  },
  nexa: {
    id: "nexa",
    name: "Nexa",
    ticker: "NEX",
    decimals: 2,
    target: "2 min",
    height: 1168213,
    mempoolCount: 1,
    prices: {
      USD: NEX_USD,
      NOK: NEX_USD * NOK_PER_USD,
      SEK: NEX_USD * SEK_PER_USD,
      DKK: NEX_USD * DKK_PER_USD,
      EUR: NEX_USD * EUR_PER_USD,
    },
    change24h: null,
    supply: 11_091_025_000_000,
    hashrate: "2.5 TH/s",
    difficulty: "70,790",
    size: "7.19 GB",
    utxo: "6.13 million",
    txCount: "3,994,581",
    serverName: "electrum-nexa.nordiccrypto.no",
    serverUrl: "wss://electrum-nexa.nordiccrypto.no:20004",
    apiHref: "https://nordiccrypto.no/api/",
    about:
      "Blocks, transactions, addresses and native group tokens, read from Nordic Crypto’s own Rostrum server.",
  },
};

const addresses: Address[] = [
  {
    id: "pool",
    chain: "nexa",
    address: "nexa:nqtsq5g5m2poolk8w2r6t0v4x9c3e7h1j5l8n0q2s4u6",
    label: "m2pool.com",
    balance: 86_420_000_000,
    tokens: [],
    txIds: ["cb-nexa-1168213", "cb-nexa-1168212", "cb-nexa-1168211", "cb-nexa-1168209", "cb-nexa-1168208"],
  },
  {
    id: "sigrid",
    chain: "nexa",
    address: "nexa:nqtsq5g5sigridk3w8m2p6r0t4v9x1c7e5h2j6l0n4",
    label: "Sigrid",
    balance: 14298.2,
    tokens: [
      { tokenId: "agnar", amount: 1_750_000 },
      { tokenId: "kibl", amount: 100_000 },
    ],
    txIds: ["kibl-send", "agnar-250", "mp-sigrid"],
  },
  {
    id: "leif",
    chain: "nexa",
    address: "nexa:nqtsq5g5leif0k8m2p6r4t9v3x7c1e5h8j2l6n0q4s",
    label: "Leif",
    balance: 8496.7,
    tokens: [
      { tokenId: "agnar", amount: 250_000 },
      { tokenId: "taplt", amount: 4_000_000 },
    ],
    txIds: ["mp-sigrid", "taplt-move", "nex-harbour", "agnar-250"],
  },
  {
    id: "harbour",
    chain: "nexa",
    address: "nexa:nqtsq5g5harbourk2w6m0p4r8t1v5x9c3e7h2j6l",
    label: "Harbour café",
    balance: 12998.2,
    tokens: [{ tokenId: "taplt", amount: 1_000_000 }],
    txIds: ["taplt-move", "nex-harbour", "kibl-send"],
  },
  {
    id: "viabtc",
    chain: "bch",
    address: "bitcoincash:qqviabtck8m2p6r0t4v9x3c7e1h5j8l0n2q4s6u8",
    label: "ViaBTC",
    balance: 412.08421,
    tokens: [],
    txIds: ["cb-bch-972618", "cb-bch-972615"],
  },
  {
    id: "sigrid-bch",
    chain: "bch",
    address: "bitcoincash:qzsigridk8m2p6r0t4v9x3c7e1h5j8l0n2q4s6",
    label: "Sigrid",
    balance: 1.249982,
    tokens: [
      { tokenId: "fjord", amount: 25 },
      { tokenId: "aurora", amount: 1 },
    ],
    txIds: ["aurora-12", "fjord-send", "bch-pay"],
  },
  {
    id: "leif-bch",
    chain: "bch",
    address: "bitcoincash:qzleif00k8m2p6r0t4v9x3c7e1h5j8l0n2q4s6u",
    label: "Leif",
    balance: 2.18441,
    tokens: [{ tokenId: "fjord", amount: 75 }],
    txIds: ["bch-wait", "aurora-12", "fjord-send"],
  },
  {
    id: "harbour-bch",
    chain: "bch",
    address: "bitcoincash:qzharbourk2m6p0r4t8v1x5c9e3h7j2l6n0q4",
    label: "Harbour café",
    balance: 0.551842,
    tokens: [],
    txIds: ["bch-pay"],
  },
];

const tokens: TokenInfo[] = [
  {
    id: "agnar",
    chain: "nexa",
    ticker: "AGNAR",
    name: "Agnar",
    supply: 20_000_000,
    decimals: 2,
    kind: "Nexa group token",
    about:
      "A native Nexa group token. The supply is the figure the public Nexa explorer listed on 12 Oct 2026. The transfer below is a sample row for this layout.",
    txIds: ["agnar-250"],
  },
  {
    id: "taplt",
    chain: "nexa",
    ticker: "TAPLT",
    name: "Tap!",
    supply: 1_000_000_000_000,
    decimals: 0,
    kind: "Nexa group token",
    about:
      "A native Nexa group token. Supply as listed on the public explorer on 12 Oct 2026. The transfer is a sample row.",
    txIds: ["taplt-move"],
  },
  {
    id: "kibl",
    chain: "nexa",
    ticker: "KIBL",
    name: "Kibble",
    supply: 997_854_100,
    decimals: 0,
    kind: "Nexa group token",
    about:
      "A native Nexa group token. Supply as listed on the public explorer on 12 Oct 2026. The transfer is a sample row.",
    txIds: ["kibl-send"],
  },
  {
    id: "fjord",
    chain: "bch",
    ticker: "FJOR",
    name: "Fjord",
    supply: 1_000_000,
    decimals: 0,
    kind: "CashToken, fungible",
    about:
      "A sample fungible CashToken, drawn so the Bitcoin Cash token layout has something honest to hold. It is not a live asset.",
    txIds: ["fjord-send"],
  },
  {
    id: "aurora",
    chain: "bch",
    ticker: "AURORA",
    name: "Aurora",
    supply: 100,
    decimals: 0,
    kind: "CashToken, NFT",
    about:
      "A sample NFT collection. Each piece is an immutable CashToken. Aurora #12 below shows how a single piece moves, with the small Bitcoin Cash amount the output has to carry.",
    txIds: ["aurora-12"],
  },
];

function coinbase(chain: ChainId, height: number, time: string, addressId: string, reward: number): Tx {
  return {
    id: `cb-${chain}-${height}`,
    chain,
    hash: fakeHash(`cb-${chain}-${height}`),
    time,
    blockHeight: height,
    fee: 0,
    size: chain === "nexa" ? 256 : 312,
    feeRate: chain === "nexa" ? "0 NEX/byte" : "0 sat/byte",
    coinbase: true,
    inputs: [],
    outputs: [{ addressId, amount: reward, label: chain === "nexa" ? "m2pool.com" : undefined }],
  };
}

const txs: Tx[] = [
  coinbase("nexa", 1168213, "2026-10-12T19:05:12Z", "pool", 5_000_000),
  coinbase("nexa", 1168212, "2026-10-12T19:03:08Z", "pool", 5_000_000),
  coinbase("nexa", 1168211, "2026-10-12T19:00:22Z", "pool", 5_000_000),
  coinbase("nexa", 1168210, "2026-10-12T18:57:40Z", "pool", 5_000_000),
  coinbase("nexa", 1168209, "2026-10-12T18:55:02Z", "pool", 5_000_000),
  coinbase("nexa", 1168208, "2026-10-12T18:52:18Z", "pool", 5_000_000),
  coinbase("nexa", 1168207, "2026-10-12T18:49:40Z", "pool", 5_000_000),
  coinbase("nexa", 1168206, "2026-10-12T18:46:55Z", "pool", 5_000_000),
  {
    id: "agnar-250",
    chain: "nexa",
    hash: fakeHash("agnar-250"),
    time: "2026-10-12T19:00:22Z",
    blockHeight: 1168211,
    fee: 2,
    size: 486,
    feeRate: "0.0041 NEX/byte",
    coinbase: false,
    inputs: [
      { addressId: "sigrid", amount: 1200, token: { tokenId: "agnar", amount: 250_000 } },
    ],
    outputs: [
      { addressId: "leif", amount: 0, token: { tokenId: "agnar", amount: 250_000 } },
      { addressId: "sigrid", amount: 1198 },
    ],
  },
  {
    id: "nex-harbour",
    chain: "nexa",
    hash: fakeHash("nex-harbour"),
    time: "2026-10-12T18:57:40Z",
    blockHeight: 1168210,
    fee: 1.5,
    size: 392,
    feeRate: "0.0038 NEX/byte",
    coinbase: false,
    inputs: [{ addressId: "leif", amount: 20_000 }],
    outputs: [
      { addressId: "harbour", amount: 12_500 },
      { addressId: "leif", amount: 7498.5 },
    ],
  },
  {
    id: "taplt-move",
    chain: "nexa",
    hash: fakeHash("taplt-move"),
    time: "2026-10-12T18:55:02Z",
    blockHeight: 1168209,
    fee: 2,
    size: 510,
    feeRate: "0.0039 NEX/byte",
    coinbase: false,
    inputs: [{ addressId: "leif", amount: 400, token: { tokenId: "taplt", amount: 1_000_000 } }],
    outputs: [
      { addressId: "harbour", amount: 0, token: { tokenId: "taplt", amount: 1_000_000 } },
      { addressId: "leif", amount: 398 },
    ],
  },
  {
    id: "kibl-send",
    chain: "nexa",
    hash: fakeHash("kibl-send"),
    time: "2026-10-12T18:52:18Z",
    blockHeight: 1168208,
    fee: 1.8,
    size: 498,
    feeRate: "0.0036 NEX/byte",
    coinbase: false,
    inputs: [{ addressId: "harbour", amount: 500, token: { tokenId: "kibl", amount: 100_000 } }],
    outputs: [
      { addressId: "sigrid", amount: 0, token: { tokenId: "kibl", amount: 100_000 } },
      { addressId: "harbour", amount: 498.2 },
    ],
  },
  {
    id: "mp-sigrid",
    chain: "nexa",
    hash: fakeHash("mp-sigrid"),
    time: null,
    blockHeight: null,
    fee: 0.8,
    size: 374,
    feeRate: "0.0021 NEX/byte",
    coinbase: false,
    inputs: [{ addressId: "leif", amount: 2000 }],
    outputs: [
      { addressId: "sigrid", amount: 800 },
      { addressId: "leif", amount: 1199.2 },
    ],
  },
  coinbase("bch", 972618, "2026-10-12T19:03:43Z", "viabtc", 3.125),
  coinbase("bch", 972617, "2026-10-12T18:54:11Z", "viabtc", 3.125),
  coinbase("bch", 972616, "2026-10-12T18:41:02Z", "viabtc", 3.125),
  coinbase("bch", 972615, "2026-10-12T18:33:48Z", "viabtc", 3.125),
  coinbase("bch", 972614, "2026-10-12T18:22:19Z", "viabtc", 3.125),
  coinbase("bch", 972613, "2026-10-12T18:11:55Z", "viabtc", 3.125),
  coinbase("bch", 972612, "2026-10-12T18:04:06Z", "viabtc", 3.125),
  coinbase("bch", 972611, "2026-10-12T17:51:40Z", "viabtc", 3.125),
  {
    id: "bch-pay",
    chain: "bch",
    hash: fakeHash("bch-pay"),
    time: "2026-10-12T18:54:11Z",
    blockHeight: 972617,
    fee: 0.000012,
    size: 382,
    feeRate: "1 sat/byte",
    coinbase: false,
    inputs: [{ addressId: "sigrid-bch", amount: 1.25 }],
    outputs: [
      { addressId: "harbour-bch", amount: 0.08441265 },
      { addressId: "sigrid-bch", amount: 1.16557535 },
    ],
  },
  {
    id: "fjord-send",
    chain: "bch",
    hash: fakeHash("fjord-send"),
    time: "2026-10-12T18:41:02Z",
    blockHeight: 972616,
    fee: 0.00001254,
    size: 548,
    feeRate: "2 sat/byte",
    coinbase: false,
    inputs: [{ addressId: "leif-bch", amount: 0.4, token: { tokenId: "fjord", amount: 25 } }],
    outputs: [
      { addressId: "sigrid-bch", amount: 0.00000546, token: { tokenId: "fjord", amount: 25 } },
      { addressId: "leif-bch", amount: 0.399982 },
    ],
  },
  {
    id: "aurora-12",
    chain: "bch",
    hash: fakeHash("aurora-12"),
    time: "2026-10-12T18:22:19Z",
    blockHeight: 972614,
    fee: 0.000018,
    size: 612,
    feeRate: "2 sat/byte",
    coinbase: false,
    inputs: [{ addressId: "leif-bch", amount: 0.02, token: { tokenId: "aurora", amount: 1 } }],
    outputs: [
      { addressId: "sigrid-bch", amount: 0.00000546, token: { tokenId: "aurora", amount: 1 } },
      { addressId: "leif-bch", amount: 0.01997654 },
    ],
  },
  {
    id: "bch-wait",
    chain: "bch",
    hash: fakeHash("bch-wait"),
    time: null,
    blockHeight: null,
    fee: 0.000021,
    size: 404,
    feeRate: "5 sat/byte",
    coinbase: false,
    inputs: [{ addressId: "leif-bch", amount: 0.2 }],
    outputs: [
      { addressId: "harbour-bch", amount: 0.05 },
      { addressId: "leif-bch", amount: 0.149979 },
    ],
  },
  {
    id: "bch-wait-2",
    chain: "bch",
    hash: fakeHash("bch-wait-2"),
    time: null,
    blockHeight: null,
    fee: 0.000008,
    size: 226,
    feeRate: "2 sat/byte",
    coinbase: false,
    inputs: [{ addressId: "harbour-bch", amount: 0.04 }],
    outputs: [
      { addressId: "sigrid-bch", amount: 0.01 },
      { addressId: "harbour-bch", amount: 0.029992 },
    ],
  },
  {
    id: "bch-wait-3",
    chain: "bch",
    hash: fakeHash("bch-wait-3"),
    time: null,
    blockHeight: null,
    fee: 0.000004,
    size: 226,
    feeRate: "1 sat/byte",
    coinbase: false,
    inputs: [{ addressId: "sigrid-bch", amount: 0.02 }],
    outputs: [
      { addressId: "leif-bch", amount: 0.005 },
      { addressId: "sigrid-bch", amount: 0.014996 },
    ],
  },
];

function block(partial: Omit<Block, "hash" | "previous" | "merkle" | "difficulty" | "bits"> & { bits: string; difficulty: string }): Block {
  return {
    ...partial,
    hash: fakeHash(`block-${partial.chain}-${partial.height}`),
    previous: fakeHash(`block-${partial.chain}-${partial.height - 1}`),
    merkle: fakeHash(`merkle-${partial.chain}-${partial.height}`),
  };
}

const nexaBits = "1d0123ab";
const bchBits = "1806a4c2";

const blocks: Block[] = [
  block({
    chain: "nexa",
    height: 1168213,
    time: "2026-10-12T19:05:12Z",
    miner: "m2pool.com",
    minerAddressId: "pool",
    txIds: ["cb-nexa-1168213"],
    size: 256,
    reward: 5_000_000,
    difficulty: "70,790",
    bits: nexaBits,
  }),
  block({
    chain: "nexa",
    height: 1168212,
    time: "2026-10-12T19:03:08Z",
    miner: "m2pool.com",
    minerAddressId: "pool",
    txIds: ["cb-nexa-1168212"],
    size: 256,
    reward: 5_000_000,
    difficulty: "70,790",
    bits: nexaBits,
  }),
  block({
    chain: "nexa",
    height: 1168211,
    time: "2026-10-12T19:00:22Z",
    miner: "m2pool.com",
    minerAddressId: "pool",
    txIds: ["cb-nexa-1168211", "agnar-250"],
    size: 1842,
    reward: 5_000_000,
    difficulty: "70,790",
    bits: nexaBits,
  }),
  block({
    chain: "nexa",
    height: 1168210,
    time: "2026-10-12T18:57:40Z",
    miner: "m2pool.com",
    minerAddressId: "pool",
    txIds: ["cb-nexa-1168210", "nex-harbour"],
    size: 980,
    reward: 5_000_000,
    difficulty: "70,790",
    bits: nexaBits,
  }),
  block({
    chain: "nexa",
    height: 1168209,
    time: "2026-10-12T18:55:02Z",
    miner: "m2pool.com",
    minerAddressId: "pool",
    txIds: ["cb-nexa-1168209", "taplt-move"],
    size: 1124,
    reward: 5_000_000,
    difficulty: "70,790",
    bits: nexaBits,
  }),
  block({
    chain: "nexa",
    height: 1168208,
    time: "2026-10-12T18:52:18Z",
    miner: "m2pool.com",
    minerAddressId: "pool",
    txIds: ["cb-nexa-1168208", "kibl-send"],
    size: 1604,
    reward: 5_000_000,
    difficulty: "70,790",
    bits: nexaBits,
  }),
  block({
    chain: "nexa",
    height: 1168207,
    time: "2026-10-12T18:49:40Z",
    miner: "Unknown",
    txIds: ["cb-nexa-1168207"],
    size: 249,
    reward: 5_000_000,
    difficulty: "70,790",
    bits: nexaBits,
  }),
  block({
    chain: "nexa",
    height: 1168206,
    time: "2026-10-12T18:46:55Z",
    miner: "m2pool.com",
    minerAddressId: "pool",
    txIds: ["cb-nexa-1168206"],
    size: 256,
    reward: 5_000_000,
    difficulty: "70,790",
    bits: nexaBits,
  }),
  block({
    chain: "bch",
    height: 972618,
    time: "2026-10-12T19:03:43Z",
    miner: "ViaBTC",
    minerAddressId: "viabtc",
    txIds: ["cb-bch-972618"],
    size: 412,
    reward: 3.125,
    difficulty: "491,316,613,434",
    bits: bchBits,
  }),
  block({
    chain: "bch",
    height: 972617,
    time: "2026-10-12T18:54:11Z",
    miner: "ViaBTC",
    minerAddressId: "viabtc",
    txIds: ["cb-bch-972617", "bch-pay"],
    size: 48_220,
    reward: 3.125,
    difficulty: "491,316,613,434",
    bits: bchBits,
  }),
  block({
    chain: "bch",
    height: 972616,
    time: "2026-10-12T18:41:02Z",
    miner: "Unknown",
    txIds: ["cb-bch-972616", "fjord-send"],
    size: 12_840,
    reward: 3.125,
    difficulty: "491,316,613,434",
    bits: bchBits,
  }),
  block({
    chain: "bch",
    height: 972615,
    time: "2026-10-12T18:33:48Z",
    miner: "ViaBTC",
    minerAddressId: "viabtc",
    txIds: ["cb-bch-972615"],
    size: 1_204,
    reward: 3.125,
    difficulty: "491,316,613,434",
    bits: bchBits,
  }),
  block({
    chain: "bch",
    height: 972614,
    time: "2026-10-12T18:22:19Z",
    miner: "ViaBTC",
    minerAddressId: "viabtc",
    txIds: ["cb-bch-972614", "aurora-12"],
    size: 86_412,
    reward: 3.125,
    difficulty: "491,316,613,434",
    bits: bchBits,
  }),
  block({
    chain: "bch",
    height: 972613,
    time: "2026-10-12T18:11:55Z",
    miner: "ViaBTC",
    minerAddressId: "viabtc",
    txIds: ["cb-bch-972613"],
    size: 9_440,
    reward: 3.125,
    difficulty: "491,316,613,434",
    bits: bchBits,
  }),
  block({
    chain: "bch",
    height: 972612,
    time: "2026-10-12T18:04:06Z",
    miner: "Unknown",
    txIds: ["cb-bch-972612"],
    size: 2_218,
    reward: 3.125,
    difficulty: "491,316,613,434",
    bits: bchBits,
  }),
  block({
    chain: "bch",
    height: 972611,
    time: "2026-10-12T17:51:40Z",
    miner: "ViaBTC",
    minerAddressId: "viabtc",
    txIds: ["cb-bch-972611"],
    size: 640,
    reward: 3.125,
    difficulty: "491,316,613,434",
    bits: bchBits,
  }),
];

/** Chain selector, nav, and static paths. Bitcoin Cash is the first choice. */
export const chainOrder = ["bch", "nexa"] as const satisfies readonly ChainId[];

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

export function latestBlocks(chain: ChainId, limit = 8) {
  return blocks.filter((b) => b.chain === chain).sort((a, b) => b.height - a.height).slice(0, limit);
}

export function getBlock(chain: ChainId, height: number) {
  return blocks.find((b) => b.chain === chain && b.height === height);
}

export function getTx(id: string) {
  return txs.find((t) => t.id === id);
}

export function getAddress(id: string) {
  return addresses.find((a) => a.id === id);
}

export function getToken(id: string) {
  return tokens.find((t) => t.id === id);
}

export function tokensOn(chain: ChainId) {
  return tokens.filter((t) => t.chain === chain);
}

export function mempool(chain: ChainId) {
  return txs.filter((t) => t.chain === chain && t.blockHeight == null);
}

export function recentTxs(chain: ChainId, limit = 6) {
  return txs
    .filter((t) => t.chain === chain && t.time && !t.coinbase)
    .sort((a, b) => Date.parse(b.time!) - Date.parse(a.time!))
    .slice(0, limit);
}

export function blockFees(block: Block) {
  return block.txIds.reduce((sum, id) => sum + (getTx(id)?.fee ?? 0), 0);
}

export function confirmations(tx: Tx) {
  if (tx.blockHeight == null) return 0;
  return chains[tx.chain].height - tx.blockHeight + 1;
}

export function previousBlock(block: Block) {
  return getBlock(block.chain, block.height - 1);
}

export function nextBlock(block: Block) {
  return getBlock(block.chain, block.height + 1);
}

export { addresses, blocks, tokens, txs };
