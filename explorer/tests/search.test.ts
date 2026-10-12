import assert from "node:assert/strict";
import test from "node:test";
import { formatCoin, formatCompact, formatFiat } from "../lib/format";
import { searchAll } from "../lib/lookup";

test("a block height on the chain you are on wins", () => {
  const hits = searchAll("1168213", "nexa");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].href, "/nexa/block/1168213");
});

test("Sigrid is on both chains", () => {
  const hits = searchAll("Sigrid", "bch");
  assert.equal(hits.length, 2);
  assert.equal(hits[0].chain, "bch");
  assert.equal(hits[1].chain, "nexa");
});

test("an unknown query matches nothing", () => {
  assert.deepEqual(searchAll("not-a-thing", "nexa"), []);
});

test("AGNAR resolves to the Nexa token", () => {
  const hits = searchAll("agnar", "bch");
  assert.equal(hits[0].href, "/nexa/token/agnar");
});

test("Nexa supply compacts in trillions and fiat stays in the chosen currency", () => {
  assert.equal(formatCompact(11_091_025_000_000), "11.09 trillion");
  assert.equal(formatFiat(50.319, "NOK"), "50.32 NOK");
  assert.match(formatCoin(5_000_000, { ticker: "NEX", decimals: 2 }), /^5,000,000\.00 NEX$/);
});
