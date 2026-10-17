import { hexToBytes } from "./bytes";
import { chains } from "./chains";
import { bitsHex, difficultyFromBits } from "./headers";
import { formatDifficulty } from "./format";
import type { BlockModel, ChainId, FeeRow, TokenModel, TxModel, TxSide } from "./types";

export function satsToCoins(sats: number, chain: ChainId): number {
  return sats / chains[chain].subunits;
}

/** estimatefee → satoshis per byte. Nexa's Rostrum returns satoshis per kilobyte (an integer such as 1000). */
export function estimateSatPerByte(chain: ChainId, value: unknown): number | null {
  const n = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
  if (!Number.isFinite(n) || n < 0) return null;
  const sat = chains[chain].feeEstimate === "coin-per-kb" ? (n * chains[chain].subunits) / 1000 : n / 1000;
  return Math.round(sat * 1000) / 1000;
}

export function mapHistogram(rows: unknown): { satPerByte: number; vsize: number }[] {
  if (!Array.isArray(rows)) return [];
  const out: { satPerByte: number; vsize: number }[] = [];
  for (const row of rows) {
    if (!Array.isArray(row) || row.length < 2) continue;
    const satPerByte = Number(row[0]);
    const vsize = Number(row[1]);
    if (!Number.isFinite(satPerByte) || !Number.isFinite(vsize) || vsize < 0) continue;
    out.push({ satPerByte, vsize });
  }
  return out;
}

export function histogramVsize(rows: { vsize: number }[]): number {
  return rows.reduce((sum, row) => sum + row.vsize, 0);
}

type Json = Record<string, unknown>;

function asObject(value: unknown): Json | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : null;
}

/** Whole coins. value_coin and value are coins on both chains; value_satoshi is chain subunits. */
export function amountOf(chain: ChainId, value: Json): number | null {
  if (typeof value.value_coin === "number" && Number.isFinite(value.value_coin)) return value.value_coin;
  if (typeof value.value === "number" && Number.isFinite(value.value)) return value.value;
  if (typeof value.value_satoshi === "number" && Number.isFinite(value.value_satoshi)) {
    return value.value_satoshi / chains[chain].subunits;
  }
  return null;
}

function firstAddress(value: Json): string | undefined {
  if (typeof value.address === "string") return value.address;
  const direct = value.addresses;
  if (Array.isArray(direct) && typeof direct[0] === "string") return direct[0];
  const script = asObject(value.scriptPubKey);
  const nested = script?.addresses;
  if (Array.isArray(nested) && typeof nested[0] === "string") return nested[0];
  return undefined;
}

function tokenOf(chain: ChainId, value: Json): TxSide["token"] | undefined {
  const tokenData = asObject(value.tokenData);
  if (tokenData && typeof tokenData.category === "string") {
    const nft = asObject(tokenData.nft);
    const kind = nft ? `CashToken NFT${typeof nft.capability === "string" ? `, ${nft.capability}` : ""}` : "CashToken";
    const amount = tokenData.amount == null ? "0" : String(tokenData.amount);
    return { id: tokenData.category, amount, kind };
  }
  const script = asObject(value.scriptPubKey) ?? value;
  const id =
    (typeof script.token_id_hex === "string" && script.token_id_hex) ||
    (typeof script.group === "string" && script.group) ||
    (typeof value.token_id_hex === "string" && value.token_id_hex) ||
    (typeof value.group === "string" && value.group) ||
    "";
  if (!id) return undefined;
  const quantity = script.groupQuantity ?? value.groupQuantity;
  if (quantity == null) return undefined;
  return { id, amount: String(quantity), kind: chain === "nexa" ? "Nexa group token" : "Token" };
}

function outpointLabel(value: Json): string {
  const txid = typeof value.txid === "string" ? value.txid : typeof value.outpoint === "string" ? value.outpoint : "";
  const vout = typeof value.vout === "number" ? `:${value.vout}` : "";
  if (!txid) return "Unknown input";
  return `${txid.slice(0, 12)}…${txid.slice(-6)}${vout}`;
}

export function sideFrom(chain: ChainId, value: unknown, input = false): TxSide {
  const row = asObject(value) ?? {};
  if (input && (typeof row.coinbase === "string" || row.coinbase === "")) {
    return { label: "Coinbase", amount: null };
  }
  const address = firstAddress(row);
  const amount = amountOf(chain, row);
  const token = tokenOf(chain, row);
  return {
    address,
    label: address ? undefined : input ? outpointLabel(row) : undefined,
    amount,
    token,
  };
}

export function printableText(hex: string): string | null {
  let bytes: Uint8Array;
  try {
    bytes = hexToBytes(hex);
  } catch {
    return null;
  }
  let best = "";
  let current = "";
  const keep = (run: string) => {
    const cleaned = run.replace(/\s+/g, " ").trim();
    if (cleaned.length > best.length) best = cleaned;
  };
  for (const byte of bytes) {
    if (byte >= 32 && byte < 127) current += String.fromCharCode(byte);
    else {
      keep(current);
      current = "";
    }
  }
  keep(current);
  if (best.length < 3) return null;
  return best.slice(0, 64);
}

export function minerFromCoinbase(chain: ChainId, tx: unknown): { name: string | null; address: string | null; reward: number | null } {
  const row = asObject(tx);
  if (!row) return { name: null, address: null, reward: null };
  const hexes: string[] = [];
  const inputs = Array.isArray(row.vin) ? row.vin : [];
  for (const input of inputs) {
    const vin = asObject(input);
    if (vin && typeof vin.coinbase === "string") hexes.push(vin.coinbase);
    const script = asObject(vin?.scriptSig);
    if (script && typeof script.hex === "string") hexes.push(script.hex);
  }
  const outputs = Array.isArray(row.vout) ? row.vout : [];
  let reward = 0;
  let sawAmount = false;
  let address: string | null = null;
  for (const output of outputs) {
    const vout = asObject(output);
    if (!vout) continue;
    const script = asObject(vout.scriptPubKey);
    if (script && typeof script.hex === "string") hexes.push(script.hex);
    const type = script && typeof script.type === "string" ? script.type : "";
    if (type === "nulldata") continue;
    const amount = amountOf(chain, vout);
    if (amount != null) {
      reward += amount;
      sawAmount = true;
    }
    if (!address) address = firstAddress(vout) ?? null;
  }
  let name: string | null = null;
  for (const hex of hexes) {
    const text = printableText(hex);
    if (text && (!name || text.length > name.length)) name = text;
  }
  return { name, address, reward: sawAmount ? reward : null };
}

export function feeFromSides(coinbase: boolean, inputs: TxSide[], outputs: TxSide[]): number | null {
  if (coinbase) return 0;
  if (inputs.length === 0 || inputs.some((side) => side.amount == null) || outputs.some((side) => side.amount == null)) return null;
  const delta = inputs.reduce((sum, side) => sum + (side.amount ?? 0), 0) - outputs.reduce((sum, side) => sum + (side.amount ?? 0), 0);
  if (!Number.isFinite(delta) || delta < 0) return null;
  return delta;
}

export function mapTransaction(chain: ChainId, raw: unknown, tipHeight: number): TxModel {
  const row = asObject(raw);
  if (!row || typeof row.txid !== "string" && typeof row.hash !== "string") {
    throw new Error("transaction missing");
  }
  const txid = typeof row.txid === "string" ? row.txid : String(row.hash);
  const inputsRaw = Array.isArray(row.vin) ? row.vin : [];
  const outputsRaw = Array.isArray(row.vout) ? row.vout : [];
  const coinbase = inputsRaw.length === 0 || inputsRaw.some((input) => {
    const vin = asObject(input);
    return !!vin && (typeof vin.coinbase === "string" || vin.coinbase === "");
  });
  const inputs = coinbase ? [] : inputsRaw.map((input) => sideFrom(chain, input, true));
  const outputs = outputsRaw.map((output) => sideFrom(chain, output, false));
  let fee: number | null = null;
  if (typeof row.fee_satoshi === "number" && Number.isFinite(row.fee_satoshi)) fee = satsToCoins(row.fee_satoshi, chain);
  else if (coinbase) fee = 0;
  else fee = feeFromSides(false, inputs, outputs);
  const size = typeof row.size === "number" && Number.isFinite(row.size) ? row.size : null;
  const satPerByte = fee != null && size ? Math.round((fee * chains[chain].subunits * 1000) / size) / 1000 : null;
  const confirmations = typeof row.confirmations === "number" && row.confirmations > 0 ? row.confirmations : 0;
  let blockHeight: number | null = typeof row.height === "number" ? row.height : null;
  if (blockHeight == null && confirmations > 0) blockHeight = tipHeight - confirmations + 1;
  const unix = typeof row.blocktime === "number" ? row.blocktime : typeof row.time === "number" ? row.time : null;
  return {
    chain,
    txid,
    time: unix ? new Date(unix * 1000).toISOString() : null,
    blockHeight,
    confirmations,
    fee,
    size,
    satPerByte,
    coinbase,
    inputs,
    outputs,
  };
}

export function blockFromHeader(partial: {
  chain: ChainId;
  height: number;
  hash: string;
  previous: string;
  merkle: string;
  time: number;
  bits: number;
  size: number | null;
  txCount: number | null;
  tipHeight: number;
}): BlockModel {
  return {
    chain: partial.chain,
    height: partial.height,
    hash: partial.hash,
    previous: partial.previous,
    merkle: partial.merkle,
    time: new Date(partial.time * 1000).toISOString(),
    bits: bitsHex(partial.bits),
    difficulty: formatDifficulty(difficultyFromBits(partial.bits)),
    size: partial.size,
    txCount: partial.txCount,
    confirmations: partial.tipHeight - partial.height + 1,
    miner: null,
    minerAddress: null,
    reward: null,
    txIds: [],
  };
}

export function mapVerboseHeader(chain: ChainId, raw: unknown, tipHeight: number): BlockModel | null {
  const row = asObject(raw);
  if (!row || typeof row.hash !== "string" || typeof row.height !== "number") return null;
  const bits = typeof row.bits === "number" ? row.bits : Number.parseInt(String(row.bits ?? ""), 16);
  const time = typeof row.time === "number" ? row.time : 0;
  return {
    chain,
    height: row.height,
    hash: row.hash,
    previous: typeof row.previousblockhash === "string" ? row.previousblockhash : "",
    merkle: typeof row.merkleroot === "string" ? row.merkleroot : "",
    time: time ? new Date(time * 1000).toISOString() : "",
    bits: Number.isFinite(bits) ? bitsHex(bits) : "",
    difficulty: Number.isFinite(bits) ? formatDifficulty(difficultyFromBits(bits)) : "—",
    size: typeof row.size === "number" ? row.size : null,
    txCount: typeof row.txcount === "number" ? row.txcount : null,
    confirmations: tipHeight - row.height + 1,
    miner: null,
    minerAddress: null,
    reward: null,
    txIds: [],
  };
}

export function mapHistory(raw: unknown, limit: number): { entries: { txid: string; height: number | null }[]; total: number } {
  if (!Array.isArray(raw)) return { entries: [], total: 0 };
  const rows = raw.flatMap((item) => {
    const row = asObject(item);
    if (!row || typeof row.tx_hash !== "string") return [];
    const height = typeof row.height === "number" && row.height > 0 ? row.height : null;
    return [{ txid: row.tx_hash, height }];
  });
  const newest = rows.slice().reverse();
  return { entries: newest.slice(0, limit), total: rows.length };
}

export function mapTokenBalances(raw: unknown): { id: string; amount: string }[] {
  const row = asObject(raw);
  const list = Array.isArray(raw) ? raw : Array.isArray(row?.confirmed) ? row.confirmed : Array.isArray(row?.balances) ? row.balances : [];
  const out: { id: string; amount: string }[] = [];
  for (const item of list) {
    const token = asObject(item);
    if (!token) continue;
    const id =
      (typeof token.token_id_hex === "string" && token.token_id_hex) ||
      (typeof token.token === "string" && token.token) ||
      (typeof token.group === "string" && token.group) ||
      "";
    if (!id) continue;
    const confirmed = token.confirmed ?? token.amount ?? token.balance;
    const amount = confirmed == null ? "0" : String(confirmed);
    if (amount === "0") continue;
    out.push({ id, amount });
  }
  return out;
}

export function mapTokenInfo(chain: ChainId, id: string, raw: unknown): TokenModel {
  const row = asObject(raw) ?? {};
  const crc = asObject(row.crc20);
  const name = typeof row.name === "string" ? row.name : typeof crc?.name === "string" ? crc.name : null;
  const ticker = typeof row.ticker === "string" ? row.ticker : typeof crc?.symbol === "string" ? crc.symbol : null;
  const decimals =
    typeof row.decimal_places === "number" ? row.decimal_places : typeof crc?.decimals === "number" ? crc.decimals : null;
  return {
    chain,
    id: typeof row.token_id_hex === "string" ? row.token_id_hex : id,
    name,
    ticker,
    decimals,
    height: typeof row.height === "number" ? row.height : null,
    txid: typeof row.txid === "string" ? row.txid : typeof row.tx_hash === "string" ? row.tx_hash : null,
    documentUrl: typeof row.document_url === "string" ? row.document_url : null,
    documentHash: typeof row.document_hash === "string" ? row.document_hash : null,
    icon: null,
    group: typeof row.group === "string" ? row.group : id,
  };
}

export function feeTargets(chain: ChainId): { blocks: number; label: string }[] {
  if (chain === "nexa") {
    return [
      { blocks: 2, label: "Within 2 blocks" },
      { blocks: 5, label: "Within 5 blocks" },
      { blocks: 15, label: "Within 15 blocks" },
    ];
  }
  return [
    { blocks: 1, label: "Next block" },
    { blocks: 2, label: "Within 2 blocks" },
    { blocks: 6, label: "Within 6 blocks" },
  ];
}

export function rowsFromEstimates(chain: ChainId, estimates: { label: string; value: unknown }[], histogram: { satPerByte: number; vsize: number }[]): FeeRow[] {
  const rows: FeeRow[] = [];
  for (const estimate of estimates) {
    const satPerByte = estimateSatPerByte(chain, estimate.value);
    if (satPerByte == null) continue;
    rows.push({ label: estimate.label, satPerByte });
  }
  for (const bucket of histogram) {
    rows.push({ label: "In the mempool", satPerByte: bucket.satPerByte, vsize: bucket.vsize });
  }
  return rows;
}
