export type ChainId = "bch" | "nexa";

export type Fiat = "NOK" | "SEK" | "DKK" | "EUR" | "USD";

export type ChainInfo = {
  id: ChainId;
  name: string;
  ticker: string;
  decimals: number;
  target: string;
  height: number;
  mempoolCount: number;
  /** Fiat price of one whole coin. */
  prices: Record<Fiat, number>;
  change24h: number | null;
  supply: number;
  hashrate: string;
  difficulty: string;
  size: string;
  utxo: string;
  txCount: string;
  serverName: string;
  serverUrl: string;
  apiHref: string;
  about: string;
};

export type TokenMove = {
  tokenId: string;
  amount: number;
};

export type TxSide = {
  addressId?: string;
  label?: string;
  amount: number;
  token?: TokenMove;
};

export type Tx = {
  id: string;
  chain: ChainId;
  hash: string;
  time: string | null;
  blockHeight: number | null;
  fee: number;
  size: number;
  feeRate: string;
  coinbase: boolean;
  inputs: TxSide[];
  outputs: TxSide[];
};

export type Block = {
  chain: ChainId;
  height: number;
  hash: string;
  previous: string;
  merkle: string;
  time: string;
  miner: string;
  minerAddressId?: string;
  txIds: string[];
  size: number;
  reward: number;
  difficulty: string;
  bits: string;
};

export type Address = {
  id: string;
  chain: ChainId;
  address: string;
  label?: string;
  balance: number;
  tokens: { tokenId: string; amount: number }[];
  txIds: string[];
};

export type TokenInfo = {
  id: string;
  chain: ChainId;
  ticker: string;
  name: string;
  supply: number;
  decimals: number;
  kind: string;
  about: string;
  txIds: string[];
};

export type SearchHit = {
  href: string;
  chain: ChainId;
  kind: string;
  title: string;
  detail: string;
};
