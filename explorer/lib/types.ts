export type ChainId = "bch" | "nexa";

export type Fiat = "NOK" | "SEK" | "DKK" | "EUR" | "USD";

export type ServerEndpoint = {
  url: string;
  /** Short name shown next to figures. */
  label: string;
  /** The first server to try. Later entries are fallbacks. */
  primary: boolean;
};

export type ChainMeta = {
  id: ChainId;
  name: string;
  ticker: string;
  /** Decimal places of one whole coin. Bitcoin Cash is 8, Nexa is 2. */
  decimals: number;
  /** Smallest units in one whole coin. */
  subunits: number;
  /** How estimatefee numbers are quoted by this chain's servers. */
  feeEstimate: "coin-per-kb" | "sat-per-kb";
  target: string;
  servers: ServerEndpoint[];
  apiHref: string;
  about: string;
};

export type TokenMove = {
  id: string;
  amount: string;
  kind: string;
};

export type TxSide = {
  address?: string;
  label?: string;
  /** Whole coins. Null when the server did not report an amount. */
  amount: number | null;
  token?: TokenMove;
};

export type TxModel = {
  chain: ChainId;
  txid: string;
  time: string | null;
  blockHeight: number | null;
  confirmations: number;
  /** Whole coins. Null when the fee cannot be derived. */
  fee: number | null;
  size: number | null;
  satPerByte: number | null;
  coinbase: boolean;
  inputs: TxSide[];
  outputs: TxSide[];
};

export type BlockModel = {
  chain: ChainId;
  height: number;
  hash: string;
  previous: string;
  merkle: string;
  time: string;
  bits: string;
  difficulty: string;
  size: number | null;
  txCount: number | null;
  confirmations: number;
  miner: string | null;
  minerAddress: string | null;
  reward: number | null;
  txIds: string[];
};

export type AddressModel = {
  chain: ChainId;
  address: string;
  balance: number;
  unconfirmed: number;
  tokens: { id: string; amount: string }[];
  history: { txid: string; height: number | null }[];
  historyTotal: number;
};

export type FeeRow = {
  label: string;
  satPerByte: number;
  /** Cumulative virtual size of mempool transactions in this fee bucket. */
  vsize?: number;
};

export type OverviewModel = {
  serverLabel: string;
  serverVersion: string;
  fallback: boolean;
  blocks: BlockModel[];
  mempoolCount: number | null;
  mempoolVsize: number;
  fees: FeeRow[];
};

export type TokenModel = {
  chain: ChainId;
  id: string;
  name: string | null;
  ticker: string | null;
  decimals: number | null;
  height: number | null;
  txid: string | null;
  documentUrl: string | null;
};

export type SearchHit = {
  href: string;
  chain: ChainId;
  kind: string;
  title: string;
  detail: string;
};
