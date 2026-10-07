/* Same aggregation cases as tests/test_markets.py. No network. */
const m = require("../tools/markets.js");
const fails = [];
function check(got, exp, label) {
  if (got !== exp) fails.push(label + " got " + got + " expected " + exp);
}
check(m.meanDecimal(["827301.99", "825709.43"]), "826505.71", "mean last");
check(m.meanDecimal(["0.1", "0.2"]), "0.15", "mean not float");
check(m.meanDecimal(["1", "2"]), "1.5", "mean half");
check(m.meanDecimal(["1", "1", "2"]), "1.333333333333", "mean repeating");
check(m.meanDecimal(["1", "0", "0", "0", "0", "0"]), "0.166666666667", "mean round");
check(m.meanDecimal(["1.50", "2.50"]), "2.00", "mean scale");
check(m.meanDecimal(["-2", "-4"]), "-3", "mean negative");
check(m.meanDecimal(["76156.47", "76811.91"]), "76484.19", "mid");
check(m.sumDecimal(["0.10", "0.20"]), "0.30", "sum");
check(m.sumDecimal(["50000.00", "1.50"]), "50001.50", "sum quote");
check(m.sumDecimal(["0", "0"]), "0", "sum zero");
if (m.meanDecimal([]) !== null || m.sumDecimal([]) !== null) fails.push("empty invented a number");

const pairs = m.aggregatePairs([
  {base: "BTC", quote: "NOK", last: "10.00", bid: "9.00", ask: "11.00", volume_base: "3.13", exchange: {id: "firi", name: "Firi", country: "NO"}, fetched_at: "2026-10-05T21:00:00+00:00"},
  {base: "BTC", quote: "NOK", last: "1.00", volume_base_24h: "9.00", exchange: {id: "other", name: "Other", country: "SE"}, fetched_at: "2026-10-05T20:00:00+00:00"},
  {base: "BTC", quote: "NOK", last: "30.00", volume_base_24h: "2.00", volume_quote_24h: "40.00", exchange: {id: "other", name: "Other", country: "SE"}, fetched_at: "2026-10-05T21:00:00+00:00"},
  {base: "BTC", quote: "EUR", bid: "8.00", ask: "12.00", exchange: {id: "coinmotion", name: "Coinmotion", country: "FI"}, fetched_at: "2026-10-05T21:00:00+00:00"}
], {BTC: {logo_path: "api/v1/markets/logos/btc.svg", logo_url: "https://example.invalid/btc.svg", logo: {license: "CC0-1.0"}}});
const by = {};
pairs.forEach(function (p) { by[p.symbol] = p; });
const nok = by["BTC-NOK"];
check(nok.currency, "NOK", "currency");
check(nok.method, "mean_last", "method");
check(nok.price, "20.00", "price");
check(nok.min, "10.00", "min");
check(nok.max, "30.00", "max");
check(nok.exchange_count, 2, "count");
check(nok.mid, "10.00", "mid separate");
check(nok.vwap, null, "vwap");
check(nok.volume.volume_base, "3.13", "vol base");
check(nok.volume.volume_base_24h, "2.00", "vol 24h");
check(nok.volume.volume_quote_24h, "40.00", "vol quote");
check(nok.volume.volume_quote, null, "missing vol");
check(nok.logo_path, "api/v1/markets/logos/btc.svg", "logo");
const eur = by["BTC-EUR"];
check(eur.currency, "EUR", "eur");
check(eur.method, "mean_bid_ask_mid", "eur method");
check(eur.last, null, "eur last");
check(eur.price, "10.00", "eur price");
check(eur.volume.volume_base, null, "eur vol");
const shares = m.volumeShares([
  {base: "BTC", quote: "NOK", volume_quote_24h: "50", volume_base: "999", exchange: {id: "nbx", name: "Norwegian Block Exchange"}, fetched_at: "2026-10-05T21:00:00+00:00", source_url: "https://api.nbx.com/tickers"},
  {base: "BTC", quote: "NOK", volume_quote_24h: "999", exchange: {id: "nbx", name: "Norwegian Block Exchange"}, fetched_at: "2026-10-05T20:00:00+00:00", source_url: "https://api.nbx.com/tickers"},
  {base: "ETH", quote: "NOK", volume_quote_24h: "30", exchange: {id: "nbx", name: "Norwegian Block Exchange"}, fetched_at: "2026-10-05T21:00:00+00:00", source_url: "https://api.nbx.com/tickers"},
  {base: "XRP", quote: "NOK", volume_quote_24h: "15", exchange: {id: "nbx", name: "Norwegian Block Exchange"}, fetched_at: "2026-10-05T21:00:00+00:00", source_url: "https://api.nbx.com/tickers"},
  {base: "SOL", quote: "NOK", volume_quote_24h: "2", exchange: {id: "nbx", name: "Norwegian Block Exchange"}, fetched_at: "2026-10-05T21:00:00+00:00", source_url: "https://api.nbx.com/tickers"},
  {base: "ADA", quote: "NOK", volume_quote_24h: "2", exchange: {id: "nbx", name: "Norwegian Block Exchange"}, fetched_at: "2026-10-05T21:00:00+00:00", source_url: "https://api.nbx.com/tickers"},
  {base: "DOGE", quote: "NOK", volume_quote_24h: "1", exchange: {id: "nbx", name: "Norwegian Block Exchange"}, fetched_at: "2026-10-05T21:00:00+00:00", source_url: "https://api.nbx.com/tickers"},
  {base: "BTC", quote: "NOK", volume_base: "999", exchange: {id: "firi", name: "Firi"}, fetched_at: "2026-10-05T21:00:00+00:00", source_url: "https://api.firi.com/v2/markets/BTCNOK"},
  {base: "ETH", quote: "EUR", volume_quote_24h: "50", exchange: {id: "nbx", name: "Norwegian Block Exchange"}, fetched_at: "2026-10-05T21:00:00+00:00", source_url: "https://api.nbx.com/tickers"}
], {BTC: "Bitcoin"}, {BTC: {logo_path: "api/v1/markets/logos/btc.svg"}});
const jsBy = {};
shares.forEach(function (g) { jsBy[g.quote] = g; });
check(Object.keys(jsBy).join(","), "NOK,EUR", "share quotes");
const jsNok = jsBy.NOK;
check(jsNok.slices.map(function (s) { return s.base; }).join(","), "BTC,ETH,XRP,", "nok slices");
check(jsNok.slices[0].volume, "50", "deduped volume");
check(jsNok.slices[0].pct, "50.0", "btc pct");
check(jsNok.slices[0].logo_path, "api/v1/markets/logos/btc.svg", "logo");
check(jsNok.slices[3].other, true, "other flag");
check(jsNok.slices[3].volume, "5", "other volume");
check(jsNok.slices[3].members.join(","), "ADA,SOL,DOGE", "other members");
check(jsNok.slices[3].pct, "5.0", "other pct");
check(jsNok.window, "24h", "window");
check(jsNok.total, "100", "total");
if (jsNok.slices.reduce(function (n, s) { return n + s.tenths; }, 0) !== 1000) fails.push("nok tenths");
if (jsNok.sources.some(function (s) { return s.id === "firi"; })) fails.push("firi in sources");
check(jsBy.EUR.slices[0].pct, "100.0", "eur pct");
const thirds = m.volumeShares([
  {base: "AAA", quote: "SEK", volume_quote_24h: "1", exchange: {id: "nbx", name: "NBX"}, fetched_at: "2026-10-05T21:00:00+00:00"},
  {base: "BBB", quote: "SEK", volume_quote_24h: "1", exchange: {id: "nbx", name: "NBX"}, fetched_at: "2026-10-05T21:00:00+00:00"},
  {base: "CCC", quote: "SEK", volume_quote_24h: "1", exchange: {id: "nbx", name: "NBX"}, fetched_at: "2026-10-05T21:00:00+00:00"}
]);
check(thirds[0].slices.map(function (s) { return s.pct; }).join(","), "33.4,33.3,33.3", "remainder");

if (fails.length) {
  console.log("FAILED");
  fails.forEach(function (f) { console.log(" -", f); });
  process.exit(1);
}
console.log("ok");
