import { MissingError, UnreachableError } from "./electrum";
import { formatDifficulty } from "./format";
import { bitsHex } from "./headers";
import type { AddressModel, BlockModel, FeeRow, OverviewModel, TxModel, TxSide } from "./types";

/**
 * Bitcoin is read from the public mempool.space REST API
 * (https://mempool.space/docs/api/rest), not from a node of our own.
 * mempool.space sends `Access-Control-Allow-Origin: *`, so the browser calls it directly.
 * It rate-limits per IP (HTTP 429) and does not publish the limit, so every reply is
 * cached in memory and nothing here polls. Pages fetch once when they open.
 */
export const MEMPOOL_API = "https://mempool.space/api";
export const MEMPOOL_LABEL = "mempool.space";

const SATS = 100_000_000;
const HISTORY_LIMIT = 40;
const TX_LIST_LIMIT = 12;
const OVERVIEW_BLOCKS = 8;

/** Figures that move with each block: tip, fees, mempool, address balances. */
export const LIVE_TTL_MS = 30_000;
/** A block by hash, or a confirmed transaction, does not change. */
export const FIXED_TTL_MS = 10 * 60_000;

type Json = Record<string, unknown>;
type FetchLike = (url: string, init?: { headers?: Record<string, string> }) => Promise<{ ok: boolean; status: number; json(): Promise<unknown>; text(): Promise<string> }>;

const cache = new Map<string, { at: number; ttl: number; value: Promise<unknown> }>();

/** Test hook, and what Retry clears. */
export function clearMempoolCache() {
  cache.clear();
}

function obj(value: unknown): Json {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : {};
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

/**
 * GET one path under the API. A 404 or 400 is a MissingError with `missing` as the message.
 * A 429, a 5xx, or no answer is an UnreachableError naming mempool.space.
 * Successful replies are kept for `ttl` ms; failures are not cached, so Retry asks again.
 */
export async function getJson<T = unknown>(
  path: string,
  { ttl = LIVE_TTL_MS, missing = "mempool.space has no record of that.", text = false, fetchImpl }: { ttl?: number; missing?: string; text?: boolean; fetchImpl?: FetchLike } = {},
): Promise<T> {
  const url = `${MEMPOOL_API}${path}`;
  const hit = cache.get(url);
  if (hit && Date.now() - hit.at < hit.ttl) return hit.value as Promise<T>;
  const doFetch: FetchLike = fetchImpl ?? ((input, init) => fetch(input, init));
  const value = (async () => {
    let response: Awaited<ReturnType<FetchLike>>;
    try {
      response = await doFetch(url, { headers: { accept: text ? "text/plain" : "application/json" } });
    } catch {
      throw new UnreachableError([MEMPOOL_LABEL]);
    }
    if (response.status === 404 || response.status === 400) throw new MissingError(missing);
    if (response.status === 429) throw new UnreachableError([`${MEMPOOL_LABEL} (rate limited, try again in a minute)`]);
    if (!response.ok) throw new UnreachableError([MEMPOOL_LABEL]);
    return text ? (await response.text()).trim() : await response.json();
  })();
  cache.set(url, { at: Date.now(), ttl, value });
  value.catch(() => {
    if (cache.get(url)?.value === value) cache.delete(url);
  });
  return value as Promise<T>;
}

export type MempoolOptions = { fetchImpl?: FetchLike };

function isoFromSeconds(seconds: unknown): string | null {
  const value = num(seconds);
  return value == null ? null : new Date(value * 1000).toISOString();
}

/** A block from `/v1/blocks` or `/v1/block/:hash`. `extras` carries the pool, reward and coinbase address. */
export function mapBlock(raw: unknown, tipHeight: number, txIds: string[] = []): BlockModel | null {
  const row = obj(raw);
  const height = num(row.height);
  const hash = str(row.id);
  if (height == null || !hash) return null;
  const extras = obj(row.extras);
  const pool = obj(extras.pool);
  const bits = num(row.bits);
  const difficulty = num(row.difficulty);
  const reward = num(extras.reward);
  return {
    chain: "btc",
    height,
    hash,
    previous: str(row.previousblockhash) ?? "",
    merkle: str(row.merkle_root) ?? "",
    time: isoFromSeconds(row.timestamp) ?? "",
    bits: bits == null ? "—" : bitsHex(bits),
    difficulty: difficulty == null ? "—" : formatDifficulty(difficulty),
    size: num(row.size),
    txCount: num(row.tx_count),
    confirmations: Math.max(0, tipHeight - height + 1),
    miner: str(pool.name),
    minerAddress: str(extras.coinbaseAddress),
    reward: reward == null ? null : reward / SATS,
    txIds,
  };
}

function outputLabel(out: Json): string {
  const type = str(out.scriptpubkey_type);
  if (type === "op_return") return "OP_RETURN data";
  if (type === "p2pk") return "Pay to public key";
  if (type === "multisig") return "Bare multisig";
  return "Non-standard script";
}

/** A transaction from `/tx/:txid`. Inputs carry their prevout, so no second lookup is needed. */
export function mapTx(raw: unknown, tipHeight: number): TxModel {
  const row = obj(raw);
  const txid = str(row.txid);
  if (!txid) throw new MissingError("mempool.space did not return a transaction.");
  const vin = Array.isArray(row.vin) ? row.vin.map(obj) : [];
  const vout = Array.isArray(row.vout) ? row.vout.map(obj) : [];
  const coinbase = vin.some((input) => input.is_coinbase === true);
  const inputs: TxSide[] = coinbase
    ? []
    : vin.map((input) => {
        const prev = obj(input.prevout);
        const value = num(prev.value);
        const address = str(prev.scriptpubkey_address);
        return address ? { address, amount: value == null ? null : value / SATS } : { label: outputLabel(prev), amount: value == null ? null : value / SATS };
      });
  const outputs: TxSide[] = vout.map((out) => {
    const value = num(out.value);
    const address = str(out.scriptpubkey_address);
    const amount = value == null ? null : value / SATS;
    return address ? { address, amount } : { label: outputLabel(out), amount };
  });
  const status = obj(row.status);
  const confirmed = status.confirmed === true;
  const blockHeight = confirmed ? num(status.block_height) : null;
  const weight = num(row.weight);
  const vsize = weight != null ? Math.ceil(weight / 4) : num(row.size);
  const feeSats = coinbase ? 0 : num(row.fee);
  return {
    chain: "btc",
    txid,
    time: confirmed ? isoFromSeconds(status.block_time) : null,
    blockHeight,
    confirmations: blockHeight != null ? Math.max(1, tipHeight - blockHeight + 1) : 0,
    fee: feeSats == null ? null : feeSats / SATS,
    size: vsize,
    satPerByte: feeSats != null && vsize ? Math.round((feeSats / vsize) * 1000) / 1000 : null,
    coinbase,
    inputs,
    outputs,
  };
}

/** `/v1/fees/recommended`, in sat/vB. */
export function mapRecommended(raw: unknown): FeeRow[] {
  const row = obj(raw);
  const targets: [string, string][] = [
    ["fastestFee", "Next block"],
    ["halfHourFee", "Within 30 min"],
    ["hourFee", "Within 1 hour"],
    ["economyFee", "Economy"],
    ["minimumFee", "Minimum"],
  ];
  return targets.flatMap(([key, label]) => {
    const value = num(row[key]);
    return value == null ? [] : [{ label, satPerByte: value }];
  });
}

/** Fee-rate floors (sat/vB) for the histogram. mempool.space sends hundreds of fine buckets; these are the rows shown. */
export const FEE_BANDS = [100, 50, 20, 10, 5, 3, 2, 1, 0.5, 0.2, 0.1, 0];

/** `/mempool` fee_histogram is `[feeRate, vsize]` pairs, highest rate first. Sum them into FEE_BANDS. */
export function bandHistogram(histogram: unknown): FeeRow[] {
  const sums = new Map<number, number>();
  if (Array.isArray(histogram)) {
    for (const pair of histogram) {
      if (!Array.isArray(pair) || pair.length < 2) continue;
      const rate = Number(pair[0]);
      const vsize = Number(pair[1]);
      if (!Number.isFinite(rate) || !Number.isFinite(vsize) || vsize < 0) continue;
      const band = FEE_BANDS.find((floor) => rate >= floor) ?? 0;
      sums.set(band, (sums.get(band) ?? 0) + vsize);
    }
  }
  return FEE_BANDS.filter((band) => sums.has(band)).map((band) => ({ label: `${band}+ sat/vB`, satPerByte: band, vsize: sums.get(band)! }));
}

export type BtcFees = { rows: FeeRow[]; vsize: number; count: number | null };

export async function loadBtcTip(options: MempoolOptions = {}): Promise<number> {
  const text = await getJson<string>("/blocks/tip/height", { text: true, ...options });
  const height = Number(text);
  if (!Number.isInteger(height) || height < 0) throw new UnreachableError([MEMPOOL_LABEL]);
  return height;
}

export async function loadBtcFees(options: MempoolOptions = {}): Promise<BtcFees> {
  const [recommended, mempool] = await Promise.all([getJson("/v1/fees/recommended", options), getJson("/mempool", options)]);
  const pool = obj(mempool);
  const histogram = bandHistogram(pool.fee_histogram);
  return {
    rows: [...mapRecommended(recommended), ...histogram],
    vsize: num(pool.vsize) ?? histogram.reduce((sum, row) => sum + (row.vsize ?? 0), 0),
    count: num(pool.count),
  };
}

export async function loadBtcOverview(options: MempoolOptions = {}): Promise<OverviewModel> {
  const [blocksRaw, fees] = await Promise.all([getJson<unknown[]>("/v1/blocks", options), loadBtcFees(options)]);
  const list = Array.isArray(blocksRaw) ? blocksRaw : [];
  const tip = num(obj(list[0]).height) ?? 0;
  const blocks = list
    .slice(0, OVERVIEW_BLOCKS)
    .map((row) => mapBlock(row, tip))
    .filter((row): row is BlockModel => row != null);
  return {
    serverLabel: MEMPOOL_LABEL,
    serverVersion: "REST API",
    fallback: false,
    blocks,
    mempoolCount: fees.count,
    mempoolVsize: fees.vsize,
    fees: fees.rows.filter((row) => row.vsize == null),
  };
}

export function isBlockHash(value: string) {
  return /^0{8}[0-9a-f]{56}$/i.test(value.trim());
}

/** By height (null is the tip) or by hash. */
export async function loadBtcBlock(target: { height: number | null } | { hash: string }, options: MempoolOptions = {}): Promise<BlockModel> {
  const tip = await loadBtcTip(options);
  let hash: string;
  if ("hash" in target) {
    hash = target.hash.trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/.test(hash)) throw new MissingError("A block hash is 64 hex characters.");
  } else {
    const height = target.height ?? tip;
    if (!Number.isInteger(height) || height < 0) throw new MissingError("That is not a block height.");
    if (height > tip) throw new MissingError(`The tip is ${tip.toLocaleString("en-GB")}. That height is not in the chain yet.`);
    // Height to hash can change in a reorg near the tip, so it is cached as live.
    hash = await getJson<string>(`/block-height/${height}`, { text: true, missing: "No block at that height.", ...options });
  }
  const [raw, txids] = await Promise.all([
    getJson(`/v1/block/${hash}`, { ttl: FIXED_TTL_MS, missing: "No Bitcoin block with that hash.", ...options }),
    getJson<unknown[]>(`/block/${hash}/txids`, { ttl: FIXED_TTL_MS, missing: "No Bitcoin block with that hash.", ...options }).catch(() => []),
  ]);
  const ids = (Array.isArray(txids) ? txids : []).filter((id): id is string => typeof id === "string").slice(0, TX_LIST_LIMIT);
  const block = mapBlock(raw, tip, ids);
  if (!block) throw new MissingError("No Bitcoin block with that hash.");
  return block;
}

export async function loadBtcTx(txid: string, options: MempoolOptions = {}): Promise<TxModel> {
  const id = txid.trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(id)) throw new MissingError("A transaction id is 64 hex characters.");
  const [raw, tip] = await Promise.all([
    getJson(`/tx/${id}`, { missing: "No transaction with that id is on Bitcoin or in the mempool.", ...options }),
    loadBtcTip(options),
  ]);
  return mapTx(raw, tip);
}

/** Base58 (1…, 3…) and bech32/bech32m (bc1…) mainnet addresses. Testnet is not served from this API root. */
export function isBtcAddress(value: string) {
  const q = value.trim();
  return /^bc1[02-9ac-hj-np-z]{11,87}$/i.test(q) || /^[13][1-9A-HJ-NP-Za-km-z]{25,34}$/.test(q);
}

export function mapAddress(address: string, info: unknown, txs: unknown): AddressModel {
  const row = obj(info);
  const chainStats = obj(row.chain_stats);
  const poolStats = obj(row.mempool_stats);
  const sum = (stats: Json) => (num(stats.funded_txo_sum) ?? 0) - (num(stats.spent_txo_sum) ?? 0);
  const list = Array.isArray(txs) ? txs.map(obj) : [];
  const history = list.flatMap((tx) => {
    const txid = str(tx.txid);
    if (!txid) return [];
    const status = obj(tx.status);
    return [{ txid, height: status.confirmed === true ? num(status.block_height) : null }];
  });
  return {
    chain: "btc",
    address: str(row.address) ?? address,
    balance: sum(chainStats) / SATS,
    unconfirmed: sum(poolStats) / SATS,
    tokens: [],
    history: history.slice(0, HISTORY_LIMIT),
    historyTotal: Math.max(history.length, (num(chainStats.tx_count) ?? 0) + (num(poolStats.tx_count) ?? 0)),
  };
}

export async function loadBtcAddress(address: string, options: MempoolOptions = {}): Promise<AddressModel> {
  const text = address.trim();
  if (!isBtcAddress(text)) throw new MissingError("That is not a Bitcoin mainnet address.");
  const path = `/address/${encodeURIComponent(text)}`;
  const missing = "mempool.space did not recognise that address.";
  const [info, txs] = await Promise.all([getJson(path, { missing, ...options }), getJson(`${path}/txs`, { missing, ...options })]);
  return mapAddress(text, info, txs);
}
