import { chains } from "./chains";
import type { ChainId, ServerEndpoint } from "./types";

const CLIENT_NAME = "Nordic Crypto Explorer";
const PROTOCOL = "1.4";

/** Primary server must answer quickly; fallbacks get a little longer. */
export const PRIMARY_TIMEOUT_MS = 3000;
export const FALLBACK_TIMEOUT_MS = 5000;
const CALL_TIMEOUT_MS = 12000;

export class RpcError extends Error {
  code?: number;
  constructor(message: string, code?: number) {
    super(message);
    this.name = "RpcError";
    this.code = code;
  }
}

export class UnreachableError extends Error {
  readonly servers: string[];
  constructor(servers: string[]) {
    super("Could not reach chain servers");
    this.name = "UnreachableError";
    this.servers = servers;
  }
}

export class MissingError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MissingError";
  }
}

export type SocketLike = {
  send(data: string): void;
  close(): void;
  onopen: ((event?: unknown) => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onerror: ((event?: unknown) => void) | null;
  onclose: ((event?: unknown) => void) | null;
};

export type Connector = (url: string) => SocketLike;

export type Session = {
  chain: ChainId;
  server: ServerEndpoint;
  version: string;
  tipHeight: number;
  tipHex: string;
  call(method: string, params?: unknown[]): Promise<unknown>;
  close(): void;
};

export type ConnectOptions = {
  servers?: ServerEndpoint[];
  connect?: Connector;
  primaryTimeoutMs?: number;
  fallbackTimeoutMs?: number;
};

type Pending = { resolve: (value: unknown) => void; reject: (error: Error) => void };

function browserConnect(url: string): SocketLike {
  if (typeof WebSocket === "undefined") throw new Error("WebSocket is not available");
  return new WebSocket(url) as unknown as SocketLike;
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("timed out")), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error instanceof Error ? error : new Error("connection failed"));
      },
    );
  });
}

function waitOpen(ws: SocketLike): Promise<void> {
  return new Promise((resolve, reject) => {
    ws.onopen = () => resolve();
    ws.onerror = () => reject(new Error("socket error"));
    ws.onclose = () => reject(new Error("connection closed"));
  });
}

function versionLabel(result: unknown): string {
  if (Array.isArray(result) && result.length > 0) return String(result[0]);
  if (typeof result === "string") return result;
  return "";
}

function bindRpc(ws: SocketLike): { call: Session["call"]; close: () => void } {
  let nextId = 1;
  const pending = new Map<number, Pending>();

  ws.onmessage = (event) => {
    let message: { id?: number; result?: unknown; error?: { message?: string; code?: number } };
    try {
      message = JSON.parse(String(event.data));
    } catch {
      return;
    }
    if (message.id == null || !pending.has(message.id)) return;
    const waiter = pending.get(message.id)!;
    pending.delete(message.id);
    if (message.error) waiter.reject(new RpcError(message.error.message || "RPC error", message.error.code));
    else waiter.resolve(message.result);
  };
  ws.onclose = () => {
    for (const waiter of pending.values()) waiter.reject(new Error("connection closed"));
    pending.clear();
  };

  return {
    call(method, params = []) {
      const id = nextId++;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pending.delete(id);
          reject(new Error(`no answer for ${method}`));
        }, CALL_TIMEOUT_MS);
        pending.set(id, {
          resolve: (value) => {
            clearTimeout(timer);
            resolve(value);
          },
          reject: (error) => {
            clearTimeout(timer);
            reject(error);
          },
        });
        try {
          ws.send(JSON.stringify({ jsonrpc: "2.0", id, method, params }));
        } catch (error) {
          clearTimeout(timer);
          pending.delete(id);
          reject(error instanceof Error ? error : new Error("send failed"));
        }
      });
    },
    close() {
      try {
        ws.close();
      } catch {
        /* already closed */
      }
    },
  };
}

async function openSession(chain: ChainId, server: ServerEndpoint, timeoutMs: number, connect: Connector): Promise<Session> {
  const ws = connect(server.url);
  try {
    const rpc = await withTimeout(
      (async () => {
        await waitOpen(ws);
        const bound = bindRpc(ws);
        const version = await bound.call("server.version", [CLIENT_NAME, PROTOCOL]);
        const tip = (await bound.call("blockchain.headers.subscribe", [])) as { height?: unknown; hex?: unknown } | null;
        const height = Number(tip?.height);
        if (!Number.isInteger(height) || height < 0) throw new Error("no tip");
        return {
          bound,
          version: versionLabel(version),
          height,
          hex: typeof tip?.hex === "string" ? tip.hex : "",
        };
      })(),
      timeoutMs,
    );
    return {
      chain,
      server,
      version: rpc.version,
      tipHeight: rpc.height,
      tipHex: rpc.hex,
      call: rpc.bound.call,
      close: rpc.bound.close,
    };
  } catch (error) {
    try {
      ws.close();
    } catch {
      /* already closed */
    }
    throw error instanceof Error ? error : new Error("connection failed");
  }
}

/** Try the primary server, then each fallback. Throws UnreachableError when every server fails. */
export async function connectChain(chain: ChainId, options: ConnectOptions = {}): Promise<Session> {
  const servers = options.servers ?? chains[chain].servers;
  const connect = options.connect ?? browserConnect;
  const primaryMs = options.primaryTimeoutMs ?? PRIMARY_TIMEOUT_MS;
  const fallbackMs = options.fallbackTimeoutMs ?? FALLBACK_TIMEOUT_MS;
  let last: unknown;
  for (const server of servers) {
    try {
      return await openSession(chain, server, server.primary ? primaryMs : fallbackMs, connect);
    } catch (error) {
      last = error;
    }
  }
  void last;
  throw new UnreachableError(servers.map((server) => server.label));
}

const sessions = new Map<ChainId, Promise<Session>>();

function isConnectionError(error: unknown): boolean {
  if (error instanceof RpcError) return false;
  return true;
}

/** One live socket per chain for the page. A dead socket is dropped so the next call reconnects. */
export function getSession(chain: ChainId): Promise<Session> {
  const cached = sessions.get(chain);
  if (cached) return cached;
  const pending = connectChain(chain)
    .then((session) => {
      const call = session.call.bind(session);
      session.call = async (method, params) => {
        try {
          return await call(method, params);
        } catch (error) {
          if (isConnectionError(error)) sessions.delete(chain);
          throw error;
        }
      };
      return session;
    })
    .catch((error) => {
      sessions.delete(chain);
      throw error;
    });
  sessions.set(chain, pending);
  return pending;
}

export function dropSession(chain: ChainId) {
  const pending = sessions.get(chain);
  sessions.delete(chain);
  pending?.then((session) => session.close()).catch(() => {});
}

/** Test hook. */
export function resetSessions() {
  for (const chain of sessions.keys()) dropSession(chain);
}
