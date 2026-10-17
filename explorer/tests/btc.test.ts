import assert from "node:assert/strict";
import test from "node:test";
import { chains, tokenChains } from "../lib/chains";
import { MissingError, UnreachableError } from "../lib/electrum";
import { coinCostAtFeeRate, formatSatPerByte } from "../lib/format";
import { interpretQuery } from "../lib/lookup";
import {
  bandHistogram,
  clearMempoolCache,
  getJson,
  isBtcAddress,
  LIVE_TTL_MS,
  loadBtcAddress,
  loadBtcBlock,
  loadBtcOverview,
  loadBtcTx,
  mapBlock,
  mapRecommended,
  mapTx,
  MEMPOOL_API,
} from "../lib/mempool-space";
import { parseGecko } from "../lib/prices";
import { prettyRedirect } from "../lib/routes";

const HASH = "000000000000000000007596eef82bfb6bcb67fd6b6932f4d3290a79958bdc90";
const TXID = "33decd689c10b3849d2109f2e01f654abe13b3cb6c06204ecb4d20757da636eb";
const ADDRESS = "bc1q5lxp5g6396lgdpu2mpf86cj8hdkr657s5ee2hp";

// Trimmed from mempool.space replies on 17 Oct 2026.
const BLOCK = {
  id: HASH,
  height: 971857,
  timestamp: 1792239095,
  tx_count: 4153,
  size: 1611350,
  weight: 3994913,
  merkle_root: "2a6e96246a06ed3c51a18dc6dc1c02e11abab77fe585b34289cab892674c0771",
  previousblockhash: "000000000000000000015781636d8854b45053b983048fef4836aec7a5bd2c30",
  bits: 386007187,
  difficulty: 140577680051919.62,
  extras: { reward: 314162841, pool: { id: 115, name: "MARA Pool" }, coinbaseAddress: "32i1m6gNcSHwiPX9nfTNXVjme9j5DU8y5g" },
};

const TX = {
  txid: TXID,
  vin: [
    {
      txid: "ccfe7f6db8a75c12e4c3bc9083e60818dc2666687f3589e027423a5b516d43c9",
      vout: 1,
      prevout: { scriptpubkey_type: "v0_p2wpkh", scriptpubkey_address: ADDRESS, value: 3639486 },
      is_coinbase: false,
    },
  ],
  vout: [
    { scriptpubkey_type: "v0_p2wpkh", scriptpubkey_address: "bc1qfm3ay305ulutyvvm82gw3wsz323h84p6233jfj", value: 895148 },
    { scriptpubkey_type: "v0_p2wpkh", scriptpubkey_address: ADDRESS, value: 2736583 },
    { scriptpubkey_type: "op_return", value: 0 },
  ],
  size: 223,
  weight: 562,
  fee: 7755,
  status: { confirmed: true, block_height: 971857, block_hash: HASH, block_time: 1792239095 },
};

type Reply = { status?: number; body: unknown };

function mockFetch(routes: Record<string, Reply | (() => Reply)>) {
  const calls: string[] = [];
  const fetchImpl = async (url: string) => {
    calls.push(url);
    const path = url.slice(MEMPOOL_API.length);
    const route = routes[path];
    if (!route) return { ok: false, status: 404, json: async () => ({}), text: async () => "Not found" };
    const reply = typeof route === "function" ? route() : route;
    const status = reply.status ?? 200;
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => reply.body,
      text: async () => String(reply.body),
    };
  };
  return { fetchImpl, calls };
}

test("Bitcoin is a third chain read from mempool.space, with no token pages", () => {
  assert.equal(chains.btc.name, "Bitcoin");
  assert.equal(chains.btc.ticker, "BTC");
  assert.equal(chains.btc.backend, "mempool-space");
  assert.equal(chains.btc.feeUnit, "vB");
  assert.equal(chains.btc.servers[0].url, "https://mempool.space/api");
  assert.equal(chains.bch.backend, "electrum");
  assert.deepEqual(tokenChains, ["bch", "nexa"]);
});

test("a mempool.space block maps to the shared block model", () => {
  const block = mapBlock(BLOCK, 971860, [TXID]);
  assert.ok(block);
  assert.equal(block.chain, "btc");
  assert.equal(block.height, 971857);
  assert.equal(block.confirmations, 4);
  assert.equal(block.miner, "MARA Pool");
  assert.equal(block.minerAddress, "32i1m6gNcSHwiPX9nfTNXVjme9j5DU8y5g");
  assert.equal(block.reward, 3.14162841);
  assert.equal(block.bits, "17020093");
  assert.equal(block.time, "2026-10-17T12:11:35.000Z");
  assert.deepEqual(block.txIds, [TXID]);
  assert.equal(mapBlock({}, 1), null);
});

test("a transaction keeps prevout amounts, fee and sat/vB", () => {
  const tx = mapTx(TX, 971860);
  assert.equal(tx.confirmations, 4);
  assert.equal(tx.blockHeight, 971857);
  assert.equal(tx.coinbase, false);
  assert.deepEqual(tx.inputs, [{ address: ADDRESS, amount: 0.03639486 }]);
  assert.equal(tx.outputs.length, 3);
  assert.equal(tx.outputs[2].label, "OP_RETURN data");
  assert.equal(tx.fee, 0.00007755);
  assert.equal(tx.size, 141);
  assert.equal(tx.satPerByte, 55);
  const waiting = mapTx({ ...TX, status: { confirmed: false } }, 971860);
  assert.equal(waiting.confirmations, 0);
  assert.equal(waiting.blockHeight, null);
  const coinbase = mapTx({ ...TX, vin: [{ is_coinbase: true }], fee: undefined }, 971860);
  assert.equal(coinbase.coinbase, true);
  assert.deepEqual(coinbase.inputs, []);
  assert.equal(coinbase.fee, 0);
});

test("recommended fees and the histogram become fee rows", () => {
  const rows = mapRecommended({ fastestFee: 3, halfHourFee: 2, hourFee: 1.5, economyFee: 1, minimumFee: 0.5 });
  assert.deepEqual(
    rows.map((row) => [row.label, row.satPerByte]),
    [
      ["Next block", 3],
      ["Within 30 min", 2],
      ["Within 1 hour", 1.5],
      ["Economy", 1],
      ["Minimum", 0.5],
    ],
  );
  const bands = bandHistogram([
    [120, 1000],
    [55, 500],
    [1.73, 50_000],
    [0.48, 40_000],
    [0.22, 10_000],
    [0.21, 5_000],
    ["bad", 1],
  ]);
  assert.deepEqual(
    bands.map((row) => [row.satPerByte, row.vsize]),
    [
      [100, 1000],
      [50, 500],
      [1, 50_000],
      [0.2, 55_000],
    ],
  );
});

test("fee rates read sat/vB on Bitcoin and still price a typical transaction", () => {
  assert.equal(formatSatPerByte(2.5, "vB"), "2.5 sat/vB");
  assert.equal(formatSatPerByte(1), "1 sat/byte");
  assert.equal(coinCostAtFeeRate("2 sat/vB"), 0.000005);
});

test("replies are cached; failures are not, and map to the page states", async () => {
  clearMempoolCache();
  let count = 0;
  const { fetchImpl, calls } = mockFetch({
    "/blocks/tip/height": () => ({ body: String(800000 + count++) }),
    "/limited": { status: 429, body: "Too many requests" },
  });
  const first = await getJson<string>("/blocks/tip/height", { text: true, fetchImpl });
  const second = await getJson<string>("/blocks/tip/height", { text: true, fetchImpl });
  assert.equal(first, "800000");
  assert.equal(second, "800000");
  assert.equal(calls.length, 1);
  assert.ok(LIVE_TTL_MS >= 30_000, "do not ask mempool.space more often than every 30 s");

  await assert.rejects(getJson("/nope", { fetchImpl, missing: "gone" }), (error: unknown) => error instanceof MissingError && error.message === "gone");
  await assert.rejects(getJson("/limited", { fetchImpl }), (error: unknown) => error instanceof UnreachableError && /rate limited/.test(error.servers[0]));
  await assert.rejects(getJson("/limited", { fetchImpl }), UnreachableError);
  assert.equal(calls.filter((url) => url.endsWith("/limited")).length, 2);
  await assert.rejects(
    getJson("/down", { fetchImpl: async () => Promise.reject(new Error("offline")) }),
    (error: unknown) => error instanceof UnreachableError && error.servers[0] === "mempool.space",
  );
});

test("overview, block, transaction and address load through the REST API", async () => {
  clearMempoolCache();
  const { fetchImpl } = mockFetch({
    "/blocks/tip/height": { body: "971860" },
    "/v1/blocks": { body: [{ ...BLOCK, height: 971860 }, { ...BLOCK, height: 971859 }] },
    "/v1/fees/recommended": { body: { fastestFee: 2, halfHourFee: 1, hourFee: 1, economyFee: 1, minimumFee: 1 } },
    "/mempool": { body: { count: 72257, vsize: 38911926, fee_histogram: [[1.7, 50880]] } },
    "/block-height/971857": { body: HASH },
    [`/v1/block/${HASH}`]: { body: BLOCK },
    [`/block/${HASH}/txids`]: { body: [TXID, "ab".repeat(32)] },
    [`/tx/${TXID}`]: { body: TX },
    [`/address/${ADDRESS}`]: {
      body: {
        address: ADDRESS,
        chain_stats: { funded_txo_sum: 5_000_000, spent_txo_sum: 1_000_000, tx_count: 3 },
        mempool_stats: { funded_txo_sum: 10_000, spent_txo_sum: 0, tx_count: 1 },
      },
    },
    [`/address/${ADDRESS}/txs`]: { body: [{ txid: "cd".repeat(32), status: { confirmed: false } }, { txid: TXID, status: { confirmed: true, block_height: 971857 } }] },
  });
  const overview = await loadBtcOverview({ fetchImpl });
  assert.equal(overview.serverLabel, "mempool.space");
  assert.equal(overview.blocks[0].height, 971860);
  assert.equal(overview.mempoolCount, 72257);
  assert.equal(overview.fees[0].label, "Next block");
  assert.ok(overview.fees.every((row) => row.vsize == null));

  const byHeight = await loadBtcBlock({ height: 971857 }, { fetchImpl });
  const byHash = await loadBtcBlock({ hash: HASH }, { fetchImpl });
  assert.equal(byHeight.hash, HASH);
  assert.equal(byHash.height, 971857);
  assert.equal(byHash.txIds.length, 2);
  await assert.rejects(loadBtcBlock({ height: 999999999 }, { fetchImpl }), MissingError);

  const tx = await loadBtcTx(TXID.toUpperCase(), { fetchImpl });
  assert.equal(tx.confirmations, 4);
  await assert.rejects(loadBtcTx("abc", { fetchImpl }), MissingError);
  await assert.rejects(loadBtcTx("ef".repeat(32), { fetchImpl }), MissingError);

  const address = await loadBtcAddress(ADDRESS, { fetchImpl });
  assert.equal(address.balance, 0.04);
  assert.equal(address.unconfirmed, 0.0001);
  assert.equal(address.historyTotal, 4);
  assert.deepEqual(
    address.history.map((row) => row.height),
    [null, 971857],
  );
  await assert.rejects(loadBtcAddress("bitcoincash:qqf2sakdcjvh37wx9cdqrx05vjnm30ecr5v9rere8h", { fetchImpl }), MissingError);
});

test("search on Bitcoin finds heights, block hashes, txids and addresses", () => {
  assert.equal(interpretQuery("971857", "btc")[0].href, "/btc/block/?height=971857");
  assert.equal(interpretQuery(HASH, "btc")[0].href, `/btc/block/?hash=${HASH}`);
  assert.equal(interpretQuery(HASH, "btc")[0].kind, "Block");
  assert.equal(interpretQuery(TXID, "btc")[0].href, `/btc/tx/?txid=${TXID}`);
  assert.equal(interpretQuery(HASH, "bch")[0].kind, "Transaction");
  const segwit = interpretQuery(ADDRESS, "bch");
  assert.equal(segwit.length, 1);
  assert.equal(segwit[0].href, `/btc/address/?address=${ADDRESS}`);
  const taproot = interpretQuery("bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297", "nexa");
  assert.equal(taproot[0].chain, "btc");
  const legacy = interpretQuery("32i1m6gNcSHwiPX9nfTNXVjme9j5DU8y5g", "btc");
  assert.deepEqual(
    legacy.map((hit) => hit.chain),
    ["btc", "bch"],
  );
  assert.deepEqual(
    interpretQuery("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2", "bch").map((hit) => hit.chain),
    ["bch", "btc"],
  );
  assert.ok(isBtcAddress("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"));
  assert.ok(!isBtcAddress("bitcoincash:qqf2sakdcjvh37wx9cdqrx05vjnm30ecr5v9rere8h"));
});

test("Bitcoin path-style urls redirect, including a block by hash", () => {
  assert.equal(prettyRedirect("/btc/block/971857/"), "/btc/block/?height=971857");
  assert.equal(prettyRedirect(`/btc/block/${HASH}`), `/btc/block/?hash=${HASH}`);
  assert.equal(prettyRedirect(`/btc/tx/${TXID}/`), `/btc/tx/?txid=${TXID}`);
  assert.equal(prettyRedirect(`/btc/address/${ADDRESS}`), `/btc/address/?address=${ADDRESS}`);
});

test("CoinGecko's bitcoin quote prices BTC in NOK", () => {
  const book = parseGecko({ bitcoin: { nok: 880000, usd: 81453, nok_24h_change: -1.2 } });
  assert.ok(book);
  assert.equal(book.btc.quotes.NOK, 880000);
  assert.equal(book.btc.change.NOK, -1.2);
  assert.deepEqual(book.bch.quotes, {});
});
