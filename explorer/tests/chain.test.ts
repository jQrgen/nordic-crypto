import assert from "node:assert/strict";
import test from "node:test";
import { chains } from "../lib/chains";
import { UnreachableError, connectChain, type Connector, type Session, type SocketLike } from "../lib/electrum";
import { parseBchHeader, parseNexaHeader } from "../lib/headers";
import { hexToBytes } from "../lib/bytes";
import { loadAddress, loadOverview } from "../lib/load";
import { fiatAmount, parseGecko } from "../lib/prices";
import { estimateSatPerByte, mapHistogram, mapTransaction, minerFromCoinbase, printableText } from "../lib/protocol";

const BCH_HEADER =
  "00e0ff37e5dd394aecfbd0e522eb26967cce29b7465c45124c12b6010000000000000000011cac1e84b492eafc01da5b959ef606450f95ad7f33306cbaf2ad03a7e67b94a956cd6abe430218693fe019";

const NEXA_HEADER =
  "7defb4b9b5b71444220b00c176d6fb3a69864512920ec8bcf921adfb037834c1b3ec001bc51701376e1ece908a6260083f0ebc6918a754cb5733fb16b9f371b49be59447ee49d6f7cb7651d4b775a4a97b7e5976ccaa003400a504219df321e79e1f4ffd0000000000000000000000000000000000000000000000000000000000000000105ccd6ac6a636a2d29d2075ff02bb290000000000000000000000000000000000000000000000000100000000000001000000101526211e00002100b64f120000000000";

const NEXA_VECTOR =
  "0000000000000000000000000000000000000000000000000000000000000000ffff7f20000000000000000000000000000000000000000000000000000000000000000049317c27d6893f423308ccd46e1f51ec0310892a49b8e6645e176e7235ba04c8000000000000000000000000000000000000000000000000000000000000000027ffee60000200000000000000000000000000000000000000000000000000000000000000e700000000000000010000000105";

type Handler = (method: string, params: unknown[]) => unknown;

function mockConnect(handlers: Record<string, Handler | "silent">): Connector {
  return (url) => {
    const handler = handlers[url];
    const ws: SocketLike = {
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
      send(data: string) {
        if (typeof handler !== "function") return;
        const message = JSON.parse(data) as { id: number; method: string; params?: unknown[] };
        queueMicrotask(() => {
          try {
            const result = handler(message.method, message.params ?? []);
            ws.onmessage?.({ data: JSON.stringify({ jsonrpc: "2.0", id: message.id, result }) });
          } catch (error) {
            const text = error instanceof Error ? error.message : "error";
            ws.onmessage?.({ data: JSON.stringify({ jsonrpc: "2.0", id: message.id, error: { code: 1, message: text } }) });
          }
        });
      },
      close() {
        queueMicrotask(() => ws.onclose?.({}));
      },
    };
    if (typeof handler === "function") queueMicrotask(() => ws.onopen?.({}));
    return ws;
  };
}

function answering(tip = 100): Handler {
  return (method) => {
    if (method === "server.version") return ["Mock server", "1.4"];
    if (method === "blockchain.headers.subscribe") return { height: tip, hex: "" };
    throw new Error(`unexpected ${method}`);
  };
}

test("a Bitcoin Cash header hashes to the block id", async () => {
  const header = await parseBchHeader(hexToBytes(BCH_HEADER), 972620);
  assert.equal(header.hash, "0000000000000000023d5cb07deb57bcfa1a0f05a355f14ce971deb195016010");
  assert.equal(header.time, 1791841961);
  assert.equal(header.bits, 0x180243be);
  assert.equal(header.previous, "000000000000000001b6124c12455c46b729ce7c9626eb22e5d0fbec4a39dde5");
  assert.equal(header.bytesConsumed, 80);
});

test("a Nexa header exposes height, size and the block id", async () => {
  const header = await parseNexaHeader(hexToBytes(NEXA_HEADER));
  assert.equal(header.height, 1168310);
  assert.equal(header.hash, "c4a175bb7f9dacad54be1d6ac685fdff0dd0755f622833f106cc71dda9214dc6");
  assert.equal(header.size, 256);
  assert.equal(header.txCount, 1);
  assert.equal(header.time, 1791843344);
  assert.equal(header.previous, "c1347803fbad21f9bcc80e92124586693afbd676c1000b224414b7b5b9b4ef7d");
});

test("the Rostrum Nexa header vector decodes", async () => {
  const header = await parseNexaHeader(hexToBytes(NEXA_VECTOR));
  assert.equal(header.height, 0);
  assert.equal(header.bits, 545259519);
  assert.equal(header.time, 1626275623);
  assert.equal(header.size, 231);
  assert.equal(header.txCount, 1);
});

test("fee estimates use each chain's units", () => {
  assert.equal(estimateSatPerByte("bch", 0.00001), 1);
  assert.equal(estimateSatPerByte("nexa", 1000), 1);
  assert.equal(estimateSatPerByte("bch", -1), null);
  assert.deepEqual(mapHistogram([[2, 25522], [1, 64907]]), [
    { satPerByte: 2, vsize: 25522 },
    { satPerByte: 1, vsize: 64907 },
  ]);
});

test("a verbose transaction keeps reported amounts and does not invent a fee", () => {
  const tx = mapTransaction(
    "nexa",
    {
      txid: "c7f7124f6766602905e07c4111fd8cc68fa55e5b0744610f825a1669526655fd",
      height: 1168306,
      confirmations: 3,
      fee_satoshi: 935,
      size: 332,
      time: 1791842938,
      vin: [{ addresses: ["nexa:nqexample"], value_coin: 102527.1, value_satoshi: 10252710 }],
      vout: [{ value_coin: 102517.75, scriptPubKey: { addresses: ["nexa:nqchange"], type: "scripttemplate" } }],
    },
    1168308,
  );
  assert.equal(tx.fee, 9.35);
  assert.equal(tx.satPerByte, 2.816);
  assert.equal(tx.blockHeight, 1168306);
  assert.equal(tx.inputs[0].amount, 102527.1);
  assert.equal(tx.coinbase, false);
});

test("coinbase text is taken from the script and nowhere else", () => {
  assert.equal(printableText("006d32706f6f6c00"), "m2pool");
  const mined = minerFromCoinbase("bch", {
    vin: [{ coinbase: "006d32706f6f6c00" }],
    vout: [{ value: 3.125, scriptPubKey: { addresses: ["bitcoincash:qqexample"], type: "pubkeyhash" } }],
  });
  assert.equal(mined.name, "m2pool");
  assert.equal(mined.reward, 3.125);
  assert.equal(mined.address, "bitcoincash:qqexample");
});

test("fiat is omitted when the quote is missing", () => {
  assert.equal(fiatAmount(1.5, null), null);
  assert.equal(fiatAmount(2, 10), 20);
  const book = parseGecko({
    "bitcoin-cash": { usd: 271.14, usd_24h_change: -4.5, nok: 2597.91, nok_24h_change: null },
    nexacoin: { usd: 0.00000106, usd_24h_change: null },
  });
  assert.equal(book?.bch.quotes.NOK, 2597.91);
  assert.equal(book?.bch.change.NOK, null);
  assert.equal(book?.nexa.quotes.USD, 0.00000106);
  assert.equal(parseGecko({}), null);
});

test("the primary server is skipped when it does not answer", async () => {
  const tried: string[] = [];
  const primary = chains.bch.servers[0];
  const fallback = chains.bch.servers[2];
  const connect: Connector = (url) => {
    tried.push(url);
    return mockConnect({
      [primary.url]: "silent",
      [fallback.url]: answering(50),
    })(url);
  };
  const session = await connectChain("bch", {
    servers: [primary, fallback],
    connect,
    primaryTimeoutMs: 40,
    fallbackTimeoutMs: 40,
  });
  assert.deepEqual(tried, [primary.url, fallback.url]);
  assert.equal(session.server.label, fallback.label);
  assert.equal(session.server.primary, false);
  assert.equal(session.tipHeight, 50);
  assert.equal(session.version, "Mock server");
  session.close();
});

test("every server failing is an unreachable error and not a made-up tip", async () => {
  await assert.rejects(
    () =>
      connectChain("nexa", {
        servers: chains.nexa.servers.slice(0, 2),
        connect: mockConnect({
          [chains.nexa.servers[0].url]: "silent",
          [chains.nexa.servers[1].url]: "silent",
        }),
        primaryTimeoutMs: 30,
        fallbackTimeoutMs: 30,
      }),
    (error: unknown) => {
      assert.ok(error instanceof UnreachableError);
      assert.equal(error.message, "Could not reach chain servers");
      assert.equal(error.servers.length, 2);
      return true;
    },
  );
});

test("an overview is built only from what the server returned", async () => {
  const session: Session = {
    chain: "bch",
    server: chains.bch.servers[0],
    version: "Fulcrum test",
    tipHeight: 0,
    tipHex: "",
    close() {},
    async call(method) {
      if (method === "blockchain.block.headers") return { count: 1, hex: BCH_HEADER };
      if (method === "blockchain.estimatefee" || method === "blockchain.relayfee") return 0.00001;
      if (method === "mempool.get_fee_histogram") return [[1, 3000]];
      if (method === "mempool.count") throw new Error("unsupported");
      throw new Error(method);
    },
  };
  const overview = await loadOverview(session);
  assert.equal(overview.blocks.length, 1);
  assert.equal(overview.blocks[0].height, 0);
  assert.equal(overview.blocks[0].hash, "0000000000000000023d5cb07deb57bcfa1a0f05a355f14ce971deb195016010");
  assert.equal(overview.mempoolCount, null);
  assert.equal(overview.mempoolVsize, 3000);
  assert.ok(overview.fees.every((row) => row.satPerByte === 1));
  assert.equal(overview.serverLabel, "electrum-bch.nordiccrypto.no");
  assert.equal(overview.fallback, false);
});

test("an address balance is scaled from satoshis and unknown tokens stay empty", async () => {
  const session: Session = {
    chain: "bch",
    server: chains.bch.servers[0],
    version: "Fulcrum test",
    tipHeight: 10,
    tipHex: "",
    close() {},
    async call(method) {
      if (method === "blockchain.address.get_balance") return { confirmed: 100_000_000, unconfirmed: 0 };
      if (method === "blockchain.address.get_history") return [{ tx_hash: "aa".repeat(32), height: 0 }, { tx_hash: "bb".repeat(32), height: 9 }];
      if (method === "token.address.get_balance") throw new Error("unsupported");
      throw new Error(method);
    },
  };
  const address = await loadAddress(session, "bitcoincash:qqexampleaddress000000000000000000");
  assert.equal(address.balance, 1);
  assert.equal(address.tokens.length, 0);
  assert.equal(address.historyTotal, 2);
  assert.equal(address.history[0].height, 9);
  assert.equal(address.history[1].height, null);
});
