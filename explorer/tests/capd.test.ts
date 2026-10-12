import assert from "node:assert/strict";
import test from "node:test";
import {
  CAPD_READ_LIMIT,
  CAPD_RECENT_LIMIT,
  CapdUnsupportedError,
  capdText,
  expiryUnix,
  hexPreview,
  loadCapd,
  normalizeCapdHash,
  parseCapdInfo,
  parseCapdMessage,
} from "../lib/capd";
import { chains } from "../lib/chains";
import { UnreachableError, type Connector, type SocketLike } from "../lib/electrum";

const primary = chains.nexa.servers[0];
const fallback = chains.nexa.servers[2];

function hashOf(n: number) {
  return n.toString(16).padStart(64, "0");
}

function message(n: number, expiration: number | null = 60) {
  const body: Record<string, unknown> = {
    hash: hashOf(n),
    created: 1_700_000_000 + n,
    difficultyBits: 0x1d00ffff,
    priority: n,
    initialPriority: n + 1,
    powTarget: "f".repeat(64),
    nonce: "01",
    size: 20 + n,
    data: Buffer.from(`offer ${n}`, "utf8").toString("hex"),
  };
  if (expiration != null) body.expiration = expiration;
  return body;
}

const INFO = { size: 4096, count: 3, minPriority: 0.25, maxPriority: 8.5, relayPriority: 1 };

function miss(method: string) {
  return { rpcError: { code: -32601, message: `unknown method ${method}` } };
}

function scripted(handlers: Record<string, (method: string, params: unknown[]) => unknown>): Connector {
  return (url) => {
    const handler = handlers[url];
    const ws: SocketLike = {
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
      send(data: string) {
        if (!handler) return;
        const message = JSON.parse(data) as { id: number; method: string; params?: unknown[] };
        queueMicrotask(() => {
          try {
            const result = handler(message.method, message.params ?? []);
            if (result && typeof result === "object" && "rpcError" in result) {
              const rpcError = (result as { rpcError: { code: number; message: string } }).rpcError;
              ws.onmessage?.({ data: JSON.stringify({ id: message.id, error: rpcError }) });
              return;
            }
            ws.onmessage?.({ data: JSON.stringify({ id: message.id, result }) });
          } catch (error) {
            const text = error instanceof Error ? error.message : "error";
            ws.onmessage?.({ data: JSON.stringify({ id: message.id, error: { code: 1, message: text } }) });
          }
        });
      },
      close() {
        queueMicrotask(() => ws.onclose?.({}));
      },
    };
    if (handler) queueMicrotask(() => ws.onopen?.({}));
    return ws;
  };
}

function handshake(method: string, params: unknown[], next: (method: string, params: unknown[]) => unknown) {
  if (method === "server.version") return ["Rostrum 14.0.1", "1.4"];
  if (method === "blockchain.headers.subscribe") return { height: 12, hex: "" };
  return next(method, params);
}

function noCapd(method: string) {
  return miss(method);
}

test("CAPD info keeps the server’s count and does not invent a difficulty", () => {
  const info = parseCapdInfo(INFO);
  assert.equal(info.count, 3);
  assert.equal(info.size, 4096);
  assert.equal(info.minPriority, 0.25);
  assert.equal(info.relayPriority, 1);
  assert.equal("minDifficulty" in info, false);
  assert.throws(() => parseCapdInfo({ minPriority: 1 }), /count and a pool size/);
  assert.throws(() => parseCapdInfo(null), /count and a pool size/);
});

test("a message expiry is seconds after creation, and 65535 means none", () => {
  assert.equal(expiryUnix(1_700_000_000, 3600), 1_700_003_600);
  assert.equal(expiryUnix(1_700_000_000, 65535), null);
  assert.equal(expiryUnix(1_700_000_000, null), null);
  assert.equal(expiryUnix(1_700_000_000, 1_800_000_000), 1_800_000_000);
  const parsed = parseCapdMessage(message(4, 3600));
  assert.equal(parsed.expires, 1_700_000_000 + 4 + 3600);
  assert.equal(parsed.text, "offer 4");
  assert.equal(parsed.difficultyBits, 0x1d00ffff);
  const open = parseCapdMessage(message(4, null));
  assert.equal(open.expires, null);
  assert.equal(capdText("000102"), null);
  assert.equal(capdText(Buffer.from("hello", "utf8").toString("hex")), "hello");
  assert.equal(hexPreview("ab".repeat(40), 4), "abababab…");
  assert.deepEqual(normalizeCapdHash("zz"), { hash: null, error: "A CAPD message hash is 64 hex characters.", query: "zz" });
});

test("a server that answers without CAPD is not given a made-up pool", async () => {
  const tried: string[] = [];
  await assert.rejects(
    () =>
      loadCapd(null, {
        servers: [primary, fallback],
        primaryTimeoutMs: 40,
        fallbackTimeoutMs: 40,
        connect: (url) => {
          tried.push(url);
          return scripted({
            [primary.url]: (method, params) => handshake(method, params, noCapd),
            [fallback.url]: (method, params) => handshake(method, params, noCapd),
          })(url);
        },
      }),
    (error: unknown) => {
      assert.ok(error instanceof CapdUnsupportedError);
      assert.deepEqual(
        error.answered.map((server) => server.label),
        [primary.label, fallback.label],
      );
      assert.equal(error.answered[0].version, "Rostrum 14.0.1");
      assert.equal(error.silent.length, 0);
      assert.ok(error.methods.includes("capd.info"));
      assert.equal("count" in error, false);
      return true;
    },
  );
  assert.deepEqual(tried, [primary.url, fallback.url]);
});

test("the next server is used when the first one has no CAPD method", async () => {
  const gets: string[] = [];
  const page = await loadCapd(null, {
    servers: [primary, fallback],
    primaryTimeoutMs: 40,
    fallbackTimeoutMs: 40,
    connect: scripted({
      [primary.url]: (method, params) => handshake(method, params, noCapd),
      [fallback.url]: (method, params) =>
        handshake(method, params, (name, args) => {
          if (name === "capd.info") return { ...INFO, count: 2, size: 80 };
          if (name === "capd.list") return [hashOf(1), hashOf(2)];
          if (name === "capd.get") {
            gets.push(String(args[0]));
            return message(Number.parseInt(String(args[0]), 16));
          }
          return miss(name);
        }),
    }),
  });
  assert.equal(page.serverLabel, fallback.label);
  assert.equal(page.fallback, true);
  assert.equal(page.info.count, 2);
  assert.equal(page.info.size, 80);
  assert.deepEqual(gets, [hashOf(1), hashOf(2)]);
  assert.deepEqual(
    page.messages.map((row) => row.hash),
    [hashOf(2), hashOf(1)],
  );
  assert.equal(page.messages[0].text, "offer 2");
  assert.equal(page.lookup, null);
});

test("only the high-priority end of a long list is read, then sorted by creation time", async () => {
  const hashes = Array.from({ length: 50 }, (_, n) => hashOf(n));
  const gets: string[] = [];
  const page = await loadCapd(hashOf(49), {
    servers: [primary],
    primaryTimeoutMs: 40,
    fallbackTimeoutMs: 40,
    connect: scripted({
      [primary.url]: (method, params) =>
        handshake(method, params, (name, args) => {
          if (name === "capd.info") return { size: 9000, count: 50, minPriority: 1, maxPriority: 50, relayPriority: 2 };
          if (name === "capd.list") return hashes;
          if (name === "capd.get") {
            gets.push(String(args[0]));
            const n = Number.parseInt(String(args[0]), 16);
            return message(n, null);
          }
          return miss(name);
        }),
    }),
  });
  assert.equal(gets.length, CAPD_READ_LIMIT);
  assert.equal(gets[0], hashOf(50 - CAPD_READ_LIMIT));
  assert.equal(gets.at(-1), hashOf(49));
  assert.equal(gets.includes(hashOf(0)), false);
  assert.equal(page.messages.length, CAPD_RECENT_LIMIT);
  assert.equal(page.messages[0].hash, hashOf(49));
  assert.equal(page.messages[0].expires, null);
  assert.equal(page.listed, 50);
  assert.equal(page.read, CAPD_READ_LIMIT);
  assert.equal(page.lookup?.message?.hash, hashOf(49));
  assert.equal(page.lookup?.error, null);
});

test("nexad’s capd subcommand is accepted when the dotted methods are missing", async () => {
  const calls: string[] = [];
  const page = await loadCapd("not-a-hash", {
    servers: [primary],
    primaryTimeoutMs: 40,
    fallbackTimeoutMs: 40,
    connect: scripted({
      [primary.url]: (method, params) =>
        handshake(method, params, (name, args) => {
          calls.push(args.length ? `${name} ${args.join(" ")}` : name);
          if (name === "capd" && args[0] === "info") return { size: 0, count: 0, minPriority: 1, maxPriority: 1, relayPriority: 1 };
          if (name === "capd" && args[0] === "list") return [];
          return miss(name);
        }),
    }),
  });
  assert.equal(page.info.count, 0);
  assert.equal(page.info.size, 0);
  assert.deepEqual(page.messages, []);
  assert.equal(page.lookup?.error, "A CAPD message hash is 64 hex characters.");
  assert.equal(page.lookup?.query, "not-a-hash");
  assert.equal(calls.includes("capd send"), false);
  assert.ok(calls.includes("capd info"));
  assert.ok(calls.includes("capd list"));
});

test("a hash the pool does not hold is reported missing, and the pool figures stay", async () => {
  const page = await loadCapd(hashOf(9), {
    servers: [primary],
    primaryTimeoutMs: 40,
    fallbackTimeoutMs: 40,
    connect: scripted({
      [primary.url]: (method, params) =>
        handshake(method, params, (name, args) => {
          if (name === "capd.info") return INFO;
          if (name === "capd.list") return [hashOf(1)];
          if (name === "capd.get" && args[0] === hashOf(1)) return message(1);
          if (name === "capd.get") return { rpcError: { code: -1, message: "no such message" } };
          return miss(name);
        }),
    }),
  });
  assert.equal(page.info.count, 3);
  assert.equal(page.lookup?.message, null);
  assert.match(page.lookup?.error ?? "", /No message with that hash/);
});

test("every server failing is unreachable, with no stand-in pool", async () => {
  await assert.rejects(
    () =>
      loadCapd(null, {
        servers: [primary, fallback],
        primaryTimeoutMs: 30,
        fallbackTimeoutMs: 30,
        connect: scripted({}),
      }),
    (error: unknown) => {
      assert.ok(error instanceof UnreachableError);
      assert.deepEqual(error.servers, [primary.label, fallback.label]);
      return true;
    },
  );
});
