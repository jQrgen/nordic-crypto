import assert from "node:assert/strict";
import test from "node:test";
import { chainOrder, chains, defaultChain, homePath, resolveChain } from "../lib/chains";
import { formatCoin, formatCompact, formatFiat } from "../lib/format";
import { interpretQuery } from "../lib/lookup";
import { prettyRedirect } from "../lib/routes";

test("Bitcoin is the default chain and is listed first", () => {
  assert.equal(defaultChain, "btc");
  assert.equal(homePath, "/btc/");
  assert.deepEqual(chainOrder, ["btc", "bch", "nexa"]);
  assert.equal(resolveChain(undefined), "btc");
  assert.equal(resolveChain(null), "btc");
  assert.equal(resolveChain(""), "btc");
  assert.equal(resolveChain("nope"), "btc");
  assert.equal(resolveChain("nexa"), "nexa");
  assert.equal(resolveChain("bch"), "bch");
});

test("chain metadata has no baked-in prices or heights", () => {
  assert.equal("prices" in chains.bch, false);
  assert.equal("height" in chains.bch, false);
  assert.equal(chains.bch.servers[0].primary, true);
  assert.equal(chains.bch.servers[0].url, "wss://electrum-bch.nordiccrypto.no:50004");
  assert.equal(chains.nexa.servers[0].url, "wss://electrum-nexa.nordiccrypto.no:20004");
  assert.ok(chains.bch.servers.slice(1).every((server) => server.primary === false));
});

test("a block height becomes a query route on the chain you are on", () => {
  const hits = interpretQuery("1168213", "nexa");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].href, "/nexa/block/?height=1168213");
  assert.equal(hits[0].kind, "Block");
});

test("a transaction id becomes a query route", () => {
  const txid = "38f7e67d86c1476638e56cc561e1f480a4e62ec8f41323a610e653d25c130e87";
  const hits = interpretQuery(txid, "bch");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].href, `/bch/tx/?txid=${txid}`);
  assert.equal(hits[0].kind, "Transaction");
});

test("addresses are routed by their prefix", () => {
  const bch = interpretQuery("bitcoincash:qqf2sakdcjvh37wx9cdqrx05vjnm30ecr5v9rere8h", "nexa");
  assert.equal(bch[0].chain, "bch");
  assert.match(bch[0].href, /^\/bch\/address\/\?address=/);
  const nexa = interpretQuery("nexa:nqtsq5g54692xaxstwa8je7u6g83uy2x0mlgl52w75uvrsg4", "bch");
  assert.equal(nexa[0].chain, "nexa");
  assert.match(nexa[0].href, /^\/nexa\/address\/\?address=/);
});

test("an unknown query matches nothing", () => {
  assert.deepEqual(interpretQuery("not-a-thing", defaultChain), []);
  assert.deepEqual(interpretQuery("Sigrid", defaultChain), []);
});

test("path-style urls redirect to the static query pages", () => {
  assert.equal(prettyRedirect("/bch/block/972620/"), "/bch/block/?height=972620");
  assert.equal(prettyRedirect("/nexa/tx/abc/"), "/nexa/tx/?txid=abc");
  assert.equal(prettyRedirect("/bch/"), null);
});

test("Nexa supply compacts in trillions and fiat stays in the chosen currency", () => {
  assert.equal(formatCompact(11_091_025_000_000), "11.09 trillion");
  assert.equal(formatFiat(50.319, "NOK"), "50.32 NOK");
  assert.match(formatCoin(5_000_000, { ticker: "NEX", decimals: 2 }), /^5,000,000\.00 NEX$/);
});
