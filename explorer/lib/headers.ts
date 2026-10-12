import { bytesToHex, concatBytes, hashHex, hexToBytes, reverseBytes, sha256, u64le } from "./bytes";
import type { ChainId } from "./types";

export type ParsedHeader = {
  chain: ChainId;
  height: number;
  hash: string;
  previous: string;
  merkle: string;
  time: number;
  bits: number;
  size: number | null;
  txCount: number | null;
  bytesConsumed: number;
};

/** Compact-size integer used for vectors in Bitcoin and Nexa headers. */
export function readCompactSize(buf: Uint8Array, offset: number): [number, number] {
  const first = buf[offset];
  if (first === undefined) throw new Error("truncated header");
  if (first < 253) return [first, offset + 1];
  const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  if (first === 253) return [view.getUint16(offset + 1, true), offset + 3];
  if (first === 254) return [view.getUint32(offset + 1, true), offset + 5];
  const big = view.getBigUint64(offset + 1, true);
  if (big > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("compact size too large");
  return [Number(big), offset + 9];
}

/** Bitcoin Core VARINT (not the compact-size prefix). Nexa uses it for height and counts. */
export function readVarInt(buf: Uint8Array, offset: number): [number, number] {
  let n = BigInt(0);
  let cursor = offset;
  while (cursor < buf.length) {
    const ch = BigInt(buf[cursor++]);
    n = (n << BigInt(7)) | (ch & BigInt(0x7f));
    if (ch & BigInt(0x80)) n += BigInt(1);
    else {
      if (n > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("varint too large");
      return [Number(n), cursor];
    }
  }
  throw new Error("truncated varint");
}

function readVector(buf: Uint8Array, offset: number): [Uint8Array, number] {
  const start = offset;
  const [length, payload] = readCompactSize(buf, offset);
  const end = payload + length;
  if (end > buf.length) throw new Error("truncated vector");
  return [buf.subarray(start, end), end];
}

function take(buf: Uint8Array, offset: number, length: number): [Uint8Array, number] {
  const end = offset + length;
  if (end > buf.length) throw new Error("truncated header");
  return [buf.subarray(offset, end), end];
}

function u32(bytes: Uint8Array): number {
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(0, true);
}

function u64(bytes: Uint8Array): number {
  const big = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getBigUint64(0, true);
  if (big > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("integer too large");
  return Number(big);
}

/** Difficulty of a compact nBits target, against Bitcoin's maximum target. */
export function difficultyFromBits(bits: number): number {
  const exponent = bits >>> 24;
  const mantissa = bits & 0xffffff;
  if (mantissa === 0) return 0;
  const shift = 8 * (0x1d - exponent);
  return (0xffff / mantissa) * 2 ** shift;
}

export function bitsHex(bits: number): string {
  return (bits >>> 0).toString(16).padStart(8, "0");
}

async function bchHash(raw: Uint8Array): Promise<string> {
  return hashHex(await sha256(await sha256(raw)));
}

/**
 * Nexa identifies a block with sha256(mini || extended), displayed reversed.
 * The extended preimage uses uint64 for height, tx count and the fee pool,
 * and keeps the compact-size prefixes on the trailing vectors.
 */
async function nexaHash(parts: {
  previous: Uint8Array;
  bits: Uint8Array;
  ancestor: Uint8Array;
  txFilter: Uint8Array;
  merkle: Uint8Array;
  time: Uint8Array;
  height: number;
  chainWork: Uint8Array;
  size: Uint8Array;
  txCount: number;
  feePool: number;
  vectors: Uint8Array;
}): Promise<string> {
  const mini = await sha256(concatBytes([parts.previous, parts.bits]));
  const extended = await sha256(
    concatBytes([
      parts.ancestor,
      parts.txFilter,
      parts.merkle,
      parts.time,
      u64le(parts.height),
      parts.chainWork,
      parts.size,
      u64le(parts.txCount),
      u64le(parts.feePool),
      parts.vectors,
    ]),
  );
  return hashHex(await sha256(concatBytes([mini, extended])));
}

export async function parseBchHeader(raw: Uint8Array, height: number): Promise<ParsedHeader> {
  if (raw.length < 80) throw new Error("short Bitcoin Cash header");
  const header = raw.subarray(0, 80);
  const previous = header.subarray(4, 36);
  const merkle = header.subarray(36, 68);
  const time = u32(header.subarray(68, 72));
  const bits = u32(header.subarray(72, 76));
  return {
    chain: "bch",
    height,
    hash: await bchHash(header),
    previous: hashHex(previous),
    merkle: hashHex(merkle),
    time,
    bits,
    size: null,
    txCount: null,
    bytesConsumed: 80,
  };
}

export async function parseNexaHeader(raw: Uint8Array): Promise<ParsedHeader> {
  const [previous, o1] = take(raw, 0, 32);
  const [bitsBytes, o2] = take(raw, o1, 4);
  const [ancestor, o3] = take(raw, o2, 32);
  const [merkle, o4] = take(raw, o3, 32);
  const [txFilter, o5] = take(raw, o4, 32);
  const [timeBytes, o6] = take(raw, o5, 4);
  const [height, o7] = readVarInt(raw, o6);
  const [chainWork, o8] = take(raw, o7, 32);
  const [sizeBytes, o9] = take(raw, o8, 8);
  const [txCount, o10] = readVarInt(raw, o9);
  const [feePool, vectorStart] = readVarInt(raw, o10);
  const [, o11] = readVector(raw, vectorStart);
  const [, o12] = readVector(raw, o11);
  const [, offset] = readVector(raw, o12);
  const hash = await nexaHash({
    previous,
    bits: bitsBytes,
    ancestor,
    txFilter,
    merkle,
    time: timeBytes,
    height,
    chainWork,
    size: sizeBytes,
    txCount,
    feePool,
    vectors: raw.subarray(vectorStart, offset),
  });
  return {
    chain: "nexa",
    height,
    hash,
    previous: bytesToHex(reverseBytes(previous)),
    merkle: bytesToHex(reverseBytes(merkle)),
    time: u32(timeBytes),
    bits: u32(bitsBytes),
    size: u64(sizeBytes),
    txCount,
    bytesConsumed: offset,
  };
}

export async function parseHeaderHex(chain: ChainId, hex: string, height: number): Promise<ParsedHeader> {
  const raw = hexToBytes(hex);
  if (chain === "bch") return parseBchHeader(raw, height);
  return parseNexaHeader(raw);
}

/** Split a blockchain.block.headers blob into individual headers, oldest first. */
export async function parseHeaderBundle(chain: ChainId, hex: string, startHeight: number, count: number): Promise<ParsedHeader[]> {
  const raw = hexToBytes(hex);
  const headers: ParsedHeader[] = [];
  let offset = 0;
  for (let i = 0; i < count; i++) {
    const slice = raw.subarray(offset);
    const header = chain === "bch" ? await parseBchHeader(slice, startHeight + i) : await parseNexaHeader(slice);
    headers.push(header);
    offset += header.bytesConsumed;
  }
  if (offset !== raw.length) throw new Error("header blob did not match the reported count");
  return headers;
}
