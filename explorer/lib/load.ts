import { chains } from "./chains";
import { MissingError, type Session } from "./electrum";
import { parseHeaderBundle, parseHeaderHex } from "./headers";
import {
  blockFromHeader,
  feeFromSides,
  feeTargets,
  histogramVsize,
  mapHistogram,
  mapHistory,
  mapTokenBalances,
  mapTokenInfo,
  mapTransaction,
  mapVerboseHeader,
  minerFromCoinbase,
  rowsFromEstimates,
  sideFrom,
} from "./protocol";
import type { AddressModel, BlockModel, ChainId, FeeRow, OverviewModel, TokenModel, TxModel, TxSide } from "./types";

const HISTORY_LIMIT = 40;
const TX_LIST_LIMIT = 12;

function headerHex(result: unknown): string {
  if (typeof result === "string") return result;
  if (result && typeof result === "object" && typeof (result as { hex?: unknown }).hex === "string") {
    return (result as { hex: string }).hex;
  }
  throw new Error("header missing");
}

function bundleCount(result: unknown, fallback: number): number {
  if (result && typeof result === "object" && typeof (result as { count?: unknown }).count === "number") {
    return (result as { count: number }).count;
  }
  return fallback;
}

async function enrichInputs(session: Session, inputs: TxSide[], rawInputs: unknown[]): Promise<TxSide[]> {
  return Promise.all(
    inputs.map(async (side, index) => {
      if (side.amount != null && side.address) return side;
      const vin = rawInputs[index] && typeof rawInputs[index] === "object" ? (rawInputs[index] as { txid?: unknown; vout?: unknown }) : null;
      if (!vin || typeof vin.txid !== "string" || typeof vin.vout !== "number") return side;
      try {
        const prev = (await session.call("blockchain.transaction.get", [vin.txid, true])) as { vout?: unknown[] };
        const output = Array.isArray(prev?.vout) ? prev.vout[vin.vout] : undefined;
        if (!output) return side;
        const filled = sideFrom(session.chain, output, false);
        return {
          address: side.address ?? filled.address,
          label: side.address || filled.address ? undefined : side.label,
          amount: side.amount ?? filled.amount,
          token: side.token ?? filled.token,
        };
      } catch {
        return side;
      }
    }),
  );
}

function finishFee(chain: ChainId, tx: TxModel): TxModel {
  const fee = tx.coinbase ? 0 : tx.fee != null ? tx.fee : feeFromSides(false, tx.inputs, tx.outputs);
  const satPerByte = fee != null && tx.size ? Math.round(((fee * chains[chain].subunits) / tx.size) * 1000) / 1000 : null;
  return { ...tx, fee, satPerByte };
}

export async function loadRecentHeaders(session: Session, limit = 8): Promise<BlockModel[]> {
  const count = Math.min(limit, session.tipHeight + 1);
  const start = session.tipHeight - count + 1;
  if (session.chain === "nexa") {
    try {
      const rows = await Promise.all(
        Array.from({ length: count }, (_, index) => session.call("blockchain.block.header_verbose", [start + index])),
      );
      const blocks = rows
        .map((row) => mapVerboseHeader(session.chain, row, session.tipHeight))
        .filter((row): row is BlockModel => row != null);
      if (blocks.length === count) return blocks.reverse();
    } catch {
      /* Older servers only have the raw header blob. */
    }
  }
  const bundle = await session.call("blockchain.block.headers", [start, count]);
  const parsed = await parseHeaderBundle(session.chain, headerHex(bundle), start, bundleCount(bundle, count));
  return parsed
    .map((header) => blockFromHeader({ ...header, tipHeight: session.tipHeight }))
    .reverse();
}

export async function loadFeeTable(session: Session): Promise<{ rows: FeeRow[]; vsize: number; count: number | null }> {
  const targets = feeTargets(session.chain);
  const [estimates, histogramRaw, relay, countRaw] = await Promise.all([
    Promise.all(targets.map(async (target) => ({ label: target.label, value: await session.call("blockchain.estimatefee", [target.blocks]).catch(() => -1) }))),
    session.call("mempool.get_fee_histogram", []).catch(() => []),
    session.call("blockchain.relayfee", []).catch(() => -1),
    session.call("mempool.count", []).catch(() => null),
  ]);
  const histogram = mapHistogram(histogramRaw);
  const rows = rowsFromEstimates(session.chain, [{ label: "Minimum relay", value: relay }, ...estimates], histogram);
  const countRecord = countRaw && typeof countRaw === "object" ? (countRaw as { count?: unknown }).count : null;
  return {
    rows,
    vsize: histogramVsize(histogram),
    count: typeof countRecord === "number" ? countRecord : null,
  };
}

export async function loadOverview(session: Session): Promise<OverviewModel> {
  const [blocks, fees] = await Promise.all([loadRecentHeaders(session), loadFeeTable(session)]);
  return {
    serverLabel: session.server.label,
    serverVersion: session.version,
    fallback: !session.server.primary,
    blocks,
    mempoolCount: fees.count,
    mempoolVsize: fees.vsize,
    fees: fees.rows,
  };
}

async function loadTxIds(session: Session, height: number, count: number | null): Promise<string[]> {
  const n = count == null ? 1 : Math.min(Math.max(count, 1), TX_LIST_LIMIT);
  const ids: string[] = [];
  for (let index = 0; index < n; index++) {
    try {
      const id = await session.call("blockchain.transaction.id_from_pos", [height, index, false]);
      if (typeof id !== "string") break;
      ids.push(id);
    } catch {
      break;
    }
  }
  return ids;
}

export async function loadBlock(session: Session, height: number): Promise<BlockModel> {
  if (!Number.isInteger(height) || height < 0) throw new MissingError("That is not a block height.");
  if (height > session.tipHeight) {
    throw new MissingError(`The tip is ${session.tipHeight.toLocaleString("en-GB")}. That height is not in the chain yet.`);
  }
  let block: BlockModel;
  if (session.chain === "nexa") {
    const verbose = mapVerboseHeader(session.chain, await session.call("blockchain.block.header_verbose", [height]).catch(() => null), session.tipHeight);
    if (verbose) block = verbose;
    else {
      const hex = headerHex(await session.call("blockchain.block.header", [height]));
      block = blockFromHeader({ ...(await parseHeaderHex(session.chain, hex, height)), tipHeight: session.tipHeight });
    }
  } else {
    const hex = headerHex(await session.call("blockchain.block.header", [height]));
    block = blockFromHeader({ ...(await parseHeaderHex(session.chain, hex, height)), tipHeight: session.tipHeight });
  }
  const txIds = await loadTxIds(session, height, block.txCount);
  block = { ...block, txIds };
  if (txIds[0]) {
    try {
      const coinbase = await session.call("blockchain.transaction.get", [txIds[0], true]);
      const mined = minerFromCoinbase(session.chain, coinbase);
      block = { ...block, miner: mined.name, minerAddress: mined.address, reward: mined.reward };
    } catch {
      /* The header is still the block. */
    }
  }
  return block;
}

export async function loadTransaction(session: Session, txid: string): Promise<TxModel> {
  const id = txid.trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(id)) throw new MissingError("A transaction id is 64 hex characters.");
  let raw: unknown;
  try {
    raw = await session.call("blockchain.transaction.get", [id, true]);
  } catch {
    throw new MissingError("No transaction with that id is on this chain or in the mempool.");
  }
  const mapped = mapTransaction(session.chain, raw, session.tipHeight);
  const inputs = asInputs(raw);
  if (mapped.coinbase || inputs.length === 0) return finishFee(session.chain, mapped);
  const enriched = await enrichInputs(session, mapped.inputs, inputs);
  return finishFee(session.chain, { ...mapped, inputs: enriched });
}

function asInputs(raw: unknown): unknown[] {
  if (!raw || typeof raw !== "object" || !Array.isArray((raw as { vin?: unknown }).vin)) return [];
  return (raw as { vin: unknown[] }).vin;
}

export async function loadAddress(session: Session, address: string): Promise<AddressModel> {
  const text = address.trim();
  if (text.length < 10) throw new MissingError("That address is too short to look up.");
  let balanceRaw: unknown;
  try {
    balanceRaw = await session.call("blockchain.address.get_balance", [text]);
  } catch {
    throw new MissingError("The server did not recognise that address.");
  }
  const balance = balanceRaw && typeof balanceRaw === "object" ? (balanceRaw as { confirmed?: unknown; unconfirmed?: unknown }) : {};
  const confirmed = typeof balance.confirmed === "number" ? balance.confirmed : 0;
  const unconfirmed = typeof balance.unconfirmed === "number" ? balance.unconfirmed : 0;
  const historyRaw = await session.call("blockchain.address.get_history", [text]).catch(() => []);
  const history = mapHistory(historyRaw, HISTORY_LIMIT);
  const tokens = mapTokenBalances(await session.call("token.address.get_balance", [text]).catch(() => null));
  return {
    chain: session.chain,
    address: text,
    balance: confirmed / chains[session.chain].subunits,
    unconfirmed: unconfirmed / chains[session.chain].subunits,
    tokens,
    history: history.entries,
    historyTotal: history.total,
  };
}

export async function loadToken(session: Session, id: string): Promise<TokenModel> {
  const text = id.trim();
  if (text.length < 4) throw new MissingError("Enter a token id.");
  try {
    const raw = await session.call("token.genesis.info", [text]);
    return mapTokenInfo(session.chain, text, raw);
  } catch {
    throw new MissingError("The server has no genesis record for that token.");
  }
}
