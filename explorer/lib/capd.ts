import { hexToBytes } from "./bytes";
import { chains } from "./chains";
import { connectChain, RpcError, UnreachableError, type ConnectOptions, type Session } from "./electrum";
import type { ServerEndpoint } from "./types";

/**
 * CAPD on the wire, as nexad actually returns it (src/capd/capd_rpc.cpp).
 *
 * `capd info` is { size, count, minPriority, maxPriority, relayPriority }.
 * There is no pool-wide difficulty in that object.
 *
 * `capd list` walks the pool from lowest priority to highest and returns hashes.
 * `capd get` returns one message. `expiration` is a uint16 count of seconds after
 * `created`, and it is omitted when the message has no expiry (the field is
 * 65535). The RPC help text calls that an absolute epoch time; the struct does not.
 *
 * Rostrum 14.0.1 does not register any of these names. This module asks anyway
 * and refuses to fill in a pool the server did not return.
 */

/** How many of the highest-priority hashes to read. Priority falls with age, so the newest messages sit at the end of `capd list`. */
export const CAPD_READ_LIMIT = 48;
/** How many of those, newest first, to show. */
export const CAPD_RECENT_LIMIT = 24;

const RELATIVE_EXPIRY_MAX = 65535;
const ABSOLUTE_EXPIRY_MIN = 1_000_000_000;

export type CapdFamily = {
  infoMethod: string;
  infoParams: unknown[];
  listMethod: string;
  listParams: unknown[];
  getMethod: string;
  getParams: (hash: string) => unknown[];
};

/** Names a browser can ask over Electrum. The last one matches nexad’s `capd <subcommand>` RPC. */
export const CAPD_FAMILIES: CapdFamily[] = [
  {
    infoMethod: "capd.info",
    infoParams: [],
    listMethod: "capd.list",
    listParams: [],
    getMethod: "capd.get",
    getParams: (hash) => [hash],
  },
  {
    infoMethod: "blockchain.capd.info",
    infoParams: [],
    listMethod: "blockchain.capd.list",
    listParams: [],
    getMethod: "blockchain.capd.get",
    getParams: (hash) => [hash],
  },
  {
    infoMethod: "capd",
    infoParams: ["info"],
    listMethod: "capd",
    listParams: ["list"],
    getMethod: "capd",
    getParams: (hash) => ["get", hash],
  },
];

export function capdMethodLabel(family: CapdFamily, kind: "info" | "list" | "get"): string {
  if (kind === "info") return family.infoParams.length ? `${family.infoMethod} ${family.infoParams.join(" ")}` : family.infoMethod;
  if (kind === "list") return family.listParams.length ? `${family.listMethod} ${family.listParams.join(" ")}` : family.listMethod;
  return family.getMethod === "capd" ? "capd get <hash>" : `${family.getMethod} <hash>`;
}

export const CAPD_INFO_LABELS = CAPD_FAMILIES.map((family) => capdMethodLabel(family, "info"));

export type CapdInfo = {
  count: number;
  size: number;
  minPriority: number | null;
  maxPriority: number | null;
  relayPriority: number | null;
};

export type CapdMessage = {
  hash: string;
  /** Unix seconds. */
  created: number | null;
  /** Unix seconds when the message expires, if it has an expiry. */
  expires: number | null;
  priority: number | null;
  initialPriority: number | null;
  difficultyBits: number | null;
  /** 256-bit proof-of-work target, when the server sent one. */
  powTarget: string | null;
  size: number | null;
  dataHex: string;
  /** UTF-8 preview when the payload is text. */
  text: string | null;
};

export type CapdLookup = {
  query: string;
  message: CapdMessage | null;
  error: string | null;
};

export type CapdPage = {
  serverLabel: string;
  serverVersion: string;
  fallback: boolean;
  info: CapdInfo;
  messages: CapdMessage[];
  /** Entries returned by the list call. Null when that method is missing. */
  listed: number | null;
  /** List entries whose bodies were read. */
  read: number | null;
  lookup: CapdLookup | null;
};

export type AnsweredServer = {
  label: string;
  version: string;
  primary: boolean;
};

export class CapdUnsupportedError extends Error {
  readonly answered: AnsweredServer[];
  readonly silent: string[];
  readonly methods: string[];
  constructor(answered: AnsweredServer[], silent: string[]) {
    super("CAPD is not available on these servers");
    this.name = "CapdUnsupportedError";
    this.answered = answered;
    this.silent = silent;
    this.methods = CAPD_INFO_LABELS;
  }
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

export function parseCapdInfo(raw: unknown): CapdInfo {
  const row = asObject(raw);
  const count = asNumber(row?.count);
  const size = asNumber(row?.size);
  if (count == null || size == null || count < 0 || size < 0) {
    throw new Error("CAPD info did not include a message count and a pool size");
  }
  return {
    count,
    size,
    minPriority: asNumber(row?.minPriority),
    maxPriority: asNumber(row?.maxPriority),
    relayPriority: asNumber(row?.relayPriority),
  };
}

/** Turn nexad’s expiry field into an absolute unix time. 65535 means “no expiry”. */
export function expiryUnix(created: number | null, expiration: number | null): number | null {
  if (expiration == null || expiration === RELATIVE_EXPIRY_MAX) return null;
  if (expiration >= ABSOLUTE_EXPIRY_MIN) return expiration;
  if (created == null || expiration < 0) return null;
  return created + expiration;
}

export function capdText(hex: string): string | null {
  if (!hex || hex.length % 2 !== 0) return null;
  let bytes: Uint8Array;
  try {
    bytes = hexToBytes(hex);
  } catch {
    return null;
  }
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
  if (/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(text)) return null;
  const trimmed = text.trim();
  if (!trimmed) return null;
  return trimmed.length > 80 ? `${trimmed.slice(0, 80)}…` : trimmed;
}

export function hexPreview(hex: string, bytes = 32): string {
  const clean = hex.toLowerCase();
  const max = bytes * 2;
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max)}…`;
}

export function parseCapdMessage(raw: unknown): CapdMessage {
  const row = asObject(raw);
  const hash = typeof row?.hash === "string" ? row.hash.trim().toLowerCase() : "";
  if (!/^[0-9a-f]{64}$/.test(hash)) throw new Error("CAPD message had no hash");
  const created = asNumber(row?.created);
  const dataRaw = typeof row?.data === "string" ? row.data.trim().toLowerCase() : "";
  const dataHex = /^[0-9a-f]*$/.test(dataRaw) && dataRaw.length % 2 === 0 ? dataRaw : "";
  const pow = typeof row?.powTarget === "string" ? row.powTarget : typeof row?.difficulty === "string" ? row.difficulty : null;
  return {
    hash,
    created,
    expires: expiryUnix(created, asNumber(row?.expiration)),
    priority: asNumber(row?.priority),
    initialPriority: asNumber(row?.initialPriority),
    difficultyBits: asNumber(row?.difficultyBits),
    powTarget: pow,
    size: asNumber(row?.size),
    dataHex,
    text: capdText(dataHex),
  };
}

export function normalizeCapdHash(raw: string | null | undefined): { hash: string | null; error: string | null; query: string } {
  const query = raw?.trim() ?? "";
  if (!query) return { hash: null, error: null, query: "" };
  const hash = query.toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(hash)) return { hash: null, error: "A CAPD message hash is 64 hex characters.", query };
  return { hash, error: null, query: hash };
}

export function unixSecondsIso(seconds: number | null): string | null {
  if (seconds == null || !Number.isFinite(seconds)) return null;
  const date = new Date(seconds * 1000);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function isMethodMissing(error: unknown): boolean {
  return error instanceof RpcError && error.code === -32601;
}

function sortRecent(messages: CapdMessage[]): CapdMessage[] {
  return [...messages].sort((a, b) => (b.created ?? -1) - (a.created ?? -1) || a.hash.localeCompare(b.hash));
}

async function probeInfo(session: Session): Promise<{ info: CapdInfo; family: CapdFamily } | "unsupported"> {
  let missing = 0;
  let other: unknown;
  for (const family of CAPD_FAMILIES) {
    try {
      const raw = await session.call(family.infoMethod, family.infoParams);
      return { info: parseCapdInfo(raw), family };
    } catch (error) {
      if (isMethodMissing(error)) {
        missing += 1;
        continue;
      }
      other = error;
    }
  }
  if (missing === CAPD_FAMILIES.length) return "unsupported";
  throw other instanceof Error ? other : new Error("CAPD info failed");
}

async function readList(session: Session, family: CapdFamily): Promise<{ messages: CapdMessage[]; listed: number; read: number } | null> {
  let raw: unknown;
  try {
    raw = await session.call(family.listMethod, family.listParams);
  } catch (error) {
    if (isMethodMissing(error)) return null;
    throw error instanceof Error ? error : new Error("CAPD list failed");
  }
  if (!Array.isArray(raw)) throw new Error("CAPD list was not a list");
  // nexad walks lowest priority first. The newest messages, priority still high, are at the end.
  const rows = raw.slice(Math.max(0, raw.length - CAPD_READ_LIMIT));
  const full: CapdMessage[] = [];
  const hashes: string[] = [];
  for (const item of rows) {
    if (typeof item === "string" && /^[0-9a-f]{64}$/i.test(item)) hashes.push(item.toLowerCase());
    else if (item && typeof item === "object") {
      try {
        full.push(parseCapdMessage(item));
      } catch {
        /* One bad row does not invent the others. */
      }
    }
  }
  const fetched: CapdMessage[] = [];
  for (const hash of hashes) {
    try {
      fetched.push(parseCapdMessage(await session.call(family.getMethod, family.getParams(hash))));
    } catch (error) {
      if (isMethodMissing(error)) break;
    }
  }
  const messages = sortRecent([...full, ...fetched]).slice(0, CAPD_RECENT_LIMIT);
  return { messages, listed: raw.length, read: rows.length };
}

async function readOne(session: Session, family: CapdFamily, hash: string): Promise<CapdMessage> {
  try {
    return parseCapdMessage(await session.call(family.getMethod, family.getParams(hash)));
  } catch (error) {
    if (isMethodMissing(error)) throw new Error("This server does not look up a CAPD message.");
    throw new Error("No message with that hash is in the pool.");
  }
}

async function loadFromSession(session: Session, server: ServerEndpoint, hash: { hash: string | null; error: string | null; query: string }): Promise<CapdPage> {
  const probed = await probeInfo(session);
  if (probed === "unsupported") throw new CapdUnsupportedError([{ label: server.label, version: session.version, primary: server.primary }], []);
  const listed = await readList(session, probed.family);
  let lookup: CapdLookup | null = null;
  if (hash.error) lookup = { query: hash.query, message: null, error: hash.error };
  else if (hash.hash) {
    const already = listed?.messages.find((message) => message.hash === hash.hash) ?? null;
    if (already) lookup = { query: hash.hash, message: already, error: null };
    else {
      try {
        lookup = { query: hash.hash, message: await readOne(session, probed.family, hash.hash), error: null };
      } catch (error) {
        lookup = { query: hash.hash, message: null, error: error instanceof Error ? error.message : "No message with that hash is in the pool." };
      }
    }
  }
  return {
    serverLabel: server.label,
    serverVersion: session.version,
    fallback: !server.primary,
    info: probed.info,
    messages: listed?.messages ?? [],
    listed: listed ? listed.listed : null,
    read: listed ? listed.read : null,
    lookup,
  };
}

/** Walk the Nexa server list. A server that answers but has no CAPD method is skipped for the next one. */
export async function loadCapd(hashRaw: string | null, options: ConnectOptions = {}): Promise<CapdPage> {
  const servers = options.servers ?? chains.nexa.servers;
  const wanted = normalizeCapdHash(hashRaw);
  const answered: AnsweredServer[] = [];
  const silent: string[] = [];
  for (const server of servers) {
    let session: Session;
    try {
      session = await connectChain("nexa", { ...options, servers: [server] });
    } catch (error) {
      if (error instanceof UnreachableError) {
        silent.push(server.label);
        continue;
      }
      throw error;
    }
    try {
      try {
        return await loadFromSession(session, server, wanted);
      } catch (error) {
        if (error instanceof CapdUnsupportedError) {
          answered.push({ label: server.label, version: session.version, primary: server.primary });
          continue;
        }
        throw error;
      }
    } finally {
      session.close();
    }
  }
  if (answered.length === 0) throw new UnreachableError(silent.length ? silent : servers.map((server) => server.label));
  throw new CapdUnsupportedError(answered, silent);
}
