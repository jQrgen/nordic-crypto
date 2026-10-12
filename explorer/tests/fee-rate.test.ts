import assert from "node:assert/strict";
import test from "node:test";
import {
  TYPICAL_TX_BYTES,
  TYPICAL_TX_NOTE,
  coinCostAtFeeRate,
  formatFeeRateLabel,
  formatFeeRateQuote,
  formatLocalFiat,
} from "../lib/format";
import type { Fiat } from "../lib/types";

const FIATS: Fiat[] = ["NOK", "SEK", "DKK", "EUR", "USD"];
const QUOTES: Record<Fiat, number> = { NOK: 2600, SEK: 2700, DKK: 1800, EUR: 240, USD: 270 };

test("a sat/byte rate is priced for a ~250 byte transaction from the price it is given", () => {
  assert.equal(TYPICAL_TX_BYTES, 250);
  assert.equal(TYPICAL_TX_NOTE, "for a ~250 byte transaction");
  assert.equal(coinCostAtFeeRate("5 sat/byte"), 0.0000125);
  // 1,250 sats at 9,600 per coin is 0.12 exactly.
  assert.equal(formatFeeRateQuote("5 sat/byte", 9600, "NOK"), "5 sat/byte · ≈ 0.12 kr");
  assert.equal(formatFeeRateQuote("5 sat/byte", 9600, "SEK"), "5 sat/byte · ≈ 0.12 kr");
  assert.equal(formatFeeRateQuote("5 sat/byte", 9600, "DKK"), "5 sat/byte · ≈ 0.12 kr");
  assert.equal(formatFeeRateQuote("5 sat/byte", 9600, "EUR"), "5 sat/byte · ≈ €0.12");
  assert.equal(formatFeeRateQuote("5 sat/byte", 9600, "USD"), "5 sat/byte · ≈ $0.12");
  assert.deepEqual(formatFeeRateLabel("5 sat/byte", 9600, "NOK"), {
    quote: "5 sat/byte · ≈ 0.12 kr",
    note: "for a ~250 byte transaction",
  });
});

test("the fiat amount follows the price input", () => {
  assert.equal(formatFeeRateQuote("5 sat/byte", 19200, "NOK"), "5 sat/byte · ≈ 0.24 kr");
  assert.equal(formatFeeRateQuote("5 sat/byte", 0, "USD"), "5 sat/byte · ≈ $0.00");
  assert.equal(formatFeeRateQuote("5 sat/byte", Number.NaN, "NOK"), "5 sat/byte");
  assert.equal(formatFeeRateLabel("5 sat/byte", Number.NaN, "NOK").note, null);
});

test("NEX/byte is whole coins, not satoshis", () => {
  assert.equal(coinCostAtFeeRate("0.004 NEX/byte"), 1);
  assert.equal(formatFeeRateQuote("0.004 NEX/byte", 0.12, "SEK"), "0.004 NEX/byte · ≈ 0.12 kr");
  assert.equal(formatLocalFiat(0.000010317, "NOK"), "0.00001 kr");
});

test("an unrecognised fee rate is left unchanged", () => {
  assert.equal(formatFeeRateQuote("n/a", 9600, "NOK"), "n/a");
  assert.equal(coinCostAtFeeRate("5 sat/byte extra"), null);
  assert.equal(formatFeeRateQuote("0 sat/byte", 9600, "EUR"), "0 sat/byte · ≈ €0.00");
});

test("a caller-supplied price is the only fiat input", () => {
  for (const fiat of FIATS) {
    const quote = formatFeeRateQuote("5 sat/byte", QUOTES[fiat], fiat);
    assert.match(quote, /^5 sat\/byte · ≈ /);
    const mark = fiat === "EUR" ? "€" : fiat === "USD" ? "\\$" : "kr";
    assert.match(quote, new RegExp(mark));
    assert.equal(formatFeeRateLabel("1 sat/byte", QUOTES[fiat], fiat).note, TYPICAL_TX_NOTE);
  }
});

test("Nexa sat/byte uses 100 subunits per coin", () => {
  assert.equal(coinCostAtFeeRate("1 sat/byte", TYPICAL_TX_BYTES, 100), 2.5);
  assert.equal(formatFeeRateQuote("1 sat/byte", 0.12, "NOK", TYPICAL_TX_BYTES, 100), "1 sat/byte · ≈ 0.30 kr");
});
