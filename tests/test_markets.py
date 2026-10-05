#!/usr/bin/env python3
"""Parser checks (no network) and one live fetch of the Nordic exchange tickers.
  python3 tests/test_markets.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import markets

FETCHED = "2026-10-05T21:00:00+00:00"
DECIMAL = markets.DECIMAL


def main():
    fails = []

    firi = markets.parse_firi(
        [{"id": "BTCNOK", "last": "827301.99", "high": "839994.22", "low": "813881.71", "volume": "3.13", "change": "-0.57"},
         {"id": "BTCDKK", "last": "566966.12", "high": "0", "low": "0", "volume": "0", "change": "0"}],
        [{"market": "BTCNOK", "bid": "822000.0000000000000000", "ask": "827756.5600000000000000", "spread": "5756.56"}],
        FETCHED,
    )
    btc = next(t for t in firi if t["symbol"] == "BTC-NOK")
    if btc["last"] != "827301.99" or btc["bid"] != "822000.0000000000000000" or btc["exchange"]["country"] != "NO":
        fails.append("firi BTC-NOK fields")
    if btc["source_url"] != "https://api.firi.com/v2/markets/BTCNOK":
        fails.append("firi source url")
    if not any(t["quote"] == "DKK" for t in firi):
        fails.append("firi DKK pair dropped")

    nbx = markets.parse_nbx(
        [{"id": "BTC-NOK", "baseAsset": "BTC", "quoteAsset": "NOK", "disabled": False, "status": "OK"},
         {"id": "OLD-NOK", "baseAsset": "OLD", "quoteAsset": "NOK", "disabled": True, "status": "OK"}],
        [{"id": "BTC-NOK", "baseAsset": "BTC", "quoteAsset": "NOK", "lastTradePrice": "825709.43",
          "currentHighestBuyPrice": "820000.00", "currentLowestSellPrice": "830000.00",
          "volumeBaseAssetLast24Hours": "0.06", "volumeQuoteAssetLast24Hours": "50000.00"},
         {"id": "BTC-USDM", "baseAsset": "BTC", "quoteAsset": "USDM", "lastTradePrice": "80000"},
         {"id": "OLD-NOK", "baseAsset": "OLD", "quoteAsset": "NOK", "lastTradePrice": "1"}],
        FETCHED,
    )
    if [t["symbol"] for t in nbx] != ["BTC-NOK"]:
        fails.append("nbx filter: " + ",".join(t["symbol"] for t in nbx))
    if nbx[0]["volume_base_24h"] != "0.06" or nbx[0]["bid"] != "820000.00":
        fails.append("nbx bid/volume")

    cm = markets.parse_coinmotion({
        "success": True,
        "payload": {
            "btcEur": {"currencyCode": "BTC", "baseCurrencyCode": "EUR", "buy": "76156.47", "sell": "76811.91", "high": "77480.30", "low": "75862.70"},
            "btcUsdc": {"currencyCode": "BTC", "baseCurrencyCode": "USDC", "buy": "1", "sell": "2"},
            "ltcBtc": {"currencyCode": "LTC", "baseCurrencyCode": "BTC", "buy": "1", "sell": "2"},
            "market": {"changeAmount": 1},
            "timestamp": 1791235630,
        },
    }, FETCHED)
    if len(cm) != 1 or cm[0]["symbol"] != "BTC-EUR" or cm[0]["last"] is not None:
        fails.append("coinmotion pair filter")
    if cm and (cm[0]["bid"] != "76156.47" or cm[0]["ask"] != "76811.91"):
        fails.append("coinmotion bid/ask mapping")
    if cm and not cm[0].get("exchange_time", "").startswith("2026-"):
        fails.append("coinmotion exchange_time")

    if markets.decimal("1e2") is not None or markets.decimal(None) is not None:
        fails.append("decimal rejects junk")
    if markets.format_price("827301.9900") != "827 301.99":
        fails.append("format " + markets.format_price("827301.9900"))

    def check(got, exp, label):
        if got != exp:
            fails.append(label + " got " + str(got) + " expected " + str(exp))

    check(markets.mean_decimal(["827301.99", "825709.43"]), "826505.71", "mean last")
    check(markets.mean_decimal(["0.1", "0.2"]), "0.15", "mean not float")
    check(markets.mean_decimal(["1", "2"]), "1.5", "mean half")
    check(markets.mean_decimal(["1", "1", "2"]), "1.333333333333", "mean repeating")
    check(markets.mean_decimal(["1", "0", "0", "0", "0", "0"]), "0.166666666667", "mean round half up")
    check(markets.mean_decimal(["1.50", "2.50"]), "2.00", "mean keeps scale")
    check(markets.mean_decimal(["-2", "-4"]), "-3", "mean negative")
    check(markets.mean_decimal(["76156.47", "76811.91"]), "76484.19", "bid ask mid")
    check(markets.sum_decimal(["0.10", "0.20"]), "0.30", "sum")
    check(markets.sum_decimal(["50000.00", "1.50"]), "50001.50", "sum quote")
    check(markets.sum_decimal(["0", "0"]), "0", "sum zero")
    if markets.mean_decimal([]) is not None or markets.sum_decimal([]) is not None:
        fails.append("empty mean invented a number")

    other = {"id": "other", "name": "Other", "country": "SE"}
    nok_a = markets.ticker(markets.EXCHANGE_META["firi"], "BTCNOK", "BTC", "NOK", FETCHED, "https://api.firi.com/v2/markets/BTCNOK", last="10.00", bid="9.00", ask="11.00", volume_base="3.13")
    nok_b = markets.ticker(other, "BTC-NOK", "BTC", "NOK", FETCHED, "https://example.invalid/ticker", last="30.00", volume_base_24h="2.00", volume_quote_24h="40.00")
    nok_b_old = markets.ticker(other, "BTC-NOK", "BTC", "NOK", "2026-10-05T20:00:00+00:00", "https://example.invalid/old", last="1.00", volume_base_24h="9.00")
    eur = markets.ticker(markets.EXCHANGE_META["coinmotion"], "btcEur", "BTC", "EUR", FETCHED, "https://api.coinmotion.com/v2/rates", bid="8.00", ask="12.00")
    bare = markets.ticker(markets.EXCHANGE_META["nbx"], "NOCOIN-NOK", "NOCOIN", "NOK", FETCHED, "https://api.nbx.com/tickers", bid="5")
    pol = markets.ticker(markets.EXCHANGE_META["firi"], "POLNOK", "POL", "NOK", FETCHED, "https://api.firi.com/v2/markets/POLNOK", last="1.00")
    pairs = {p["symbol"]: p for p in markets.aggregate_pairs([nok_a, nok_b, nok_b_old, eur, bare, pol])}
    btc_nok = pairs["BTC-NOK"]
    check(btc_nok["currency"], "NOK", "nok currency")
    check(btc_nok["method"], "mean_last", "nok method")
    check(btc_nok["price"], "20.00", "nok mean ignores older duplicate")
    check(btc_nok["min"], "10.00", "nok min")
    check(btc_nok["max"], "30.00", "nok max")
    check(btc_nok["exchange_count"], 2, "nok exchanges")
    check(btc_nok["last_count"], 2, "nok lasts")
    check(btc_nok["mid"], "10.00", "nok mid separate")
    check(btc_nok["vwap"], None, "no vwap")
    check(btc_nok["volume_used_for_price"], False, "volume not in price")
    check(btc_nok["volume"]["volume_base"], "3.13", "unlabeled volume")
    check(btc_nok["volume"]["volume_base_exchanges"], 1, "unlabeled count")
    check(btc_nok["volume"]["volume_base_24h"], "2.00", "24h not mixed with unlabeled")
    check(btc_nok["volume"]["volume_quote_24h"], "40.00", "quote 24h")
    check(btc_nok["volume"]["volume_quote"], None, "missing quote volume stays null")
    if btc_nok["logo_path"] != "api/v1/markets/logos/btc.svg" or btc_nok["logo"]["license"] != "CC0-1.0":
        fails.append("btc logo")
    if not btc_nok["logo_url"].endswith("/api/v1/markets/logos/btc.svg"):
        fails.append("btc logo url")
    btc_eur = pairs["BTC-EUR"]
    check(btc_eur["currency"], "EUR", "eur stays eur")
    check(btc_eur["method"], "mean_bid_ask_mid", "eur method")
    check(btc_eur["last"], None, "eur last not invented")
    check(btc_eur["price"], "10.00", "eur mid")
    check(btc_eur["min"], "10.00", "eur min is the mid")
    check(btc_eur["volume"]["volume_base"], None, "coinmotion volume not invented")
    check(btc_eur["exchange_count"], 1, "eur one exchange")
    if pairs["NOCOIN-NOK"]["price"] is not None or pairs["NOCOIN-NOK"]["logo_url"] is not None:
        fails.append("bid-only invented a price or a logo")
    if pairs["POL-NOK"]["logo_url"] is not None or pairs["POL-NOK"]["logo_path"] is not None:
        fails.append("pol reused another icon")
    if "BTC-NOK" in {c.get("quote") for c in btc_eur["contributors"]}:
        fails.append("eur contributors mixed")
    # a published zero is kept; a missing field is not counted as zero
    zero = markets.ticker(markets.EXCHANGE_META["firi"], "ETHNOK", "ETH", "NOK", FETCHED, "https://api.firi.com/v2/markets/ETHNOK", last="2", volume_base="0")
    missing = markets.ticker(other, "ETH-NOK", "ETH", "NOK", FETCHED, "https://example.invalid/eth", last="4")
    eth = markets.aggregate_pairs([zero, missing])[0]
    check(eth["price"], "3", "eth mean")
    check(eth["volume"]["volume_base"], "0", "published zero")
    check(eth["volume"]["volume_base_exchanges"], 1, "missing volume not counted")

    body = markets.empty_failure("boom")
    body["tickers"] = firi
    body["exchanges"][0]["status"] = "ok"
    body["exchanges"][0]["ticker_count"] = len(firi)
    body["count"] = len(firi)
    doc = markets.public_document(body, generated_at=FETCHED, preview=False)
    files = markets.documents(doc)
    for rel in ("api/v1/markets.json", "api/v1/markets/aggregated.json", "api/v1/markets/firi.json", "api/v1/markets/by-asset/BTC.json"):
        if rel not in files:
            fails.append("missing " + rel)
    btc_file = files["api/v1/markets/by-asset/BTC.json"]
    if not btc_file.get("aggregated") or btc_file.get("logo_path") != "api/v1/markets/logos/btc.svg":
        fails.append("by-asset aggregate or logo")
    if files["api/v1/markets/aggregated.json"].get("kind") != "markets-aggregated":
        fails.append("aggregated kind")
    if files["api/v1/markets.json"].get("aggregated") is None:
        fails.append("markets.json aggregate")
    raw = json.dumps(files["api/v1/markets.json"])
    if "https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json" not in raw:
        fails.append("raw url")
    if "827301.99" not in raw or "safello" not in raw.lower():
        fails.append("catalogue contents")
    # a total failure must not invent a last price
    if any(t.get("last") for t in markets.empty_failure("x")["tickers"]):
        fails.append("empty failure invented a price")

    try:
        live = markets.fetch()
    except Exception as ex:
        fails.append("live fetch: " + type(ex).__name__)
        live = None
    if live:
        firi_btc = [t for t in live["tickers"] if t["exchange"]["id"] == "firi" and t["symbol"] == "BTC-NOK"]
        if not firi_btc or not DECIMAL.fullmatch(firi_btc[0]["last"] or ""):
            fails.append("live firi BTC-NOK missing")
        else:
            print("live firi BTC-NOK last", firi_btc[0]["last"], "bid", firi_btc[0]["bid"], "at", firi_btc[0]["fetched_at"])
        nbx_rows = [t for t in live["tickers"] if t["exchange"]["id"] == "nbx" and t["quote"] == "NOK" and t.get("last")]
        if not nbx_rows:
            fails.append("live nbx NOK missing")
        cm_btc = [t for t in live["tickers"] if t["exchange"]["id"] == "coinmotion" and t["symbol"] == "BTC-EUR"]
        if not cm_btc or cm_btc[0]["last"] is not None or not DECIMAL.fullmatch(cm_btc[0]["bid"] or "") or not DECIMAL.fullmatch(cm_btc[0]["ask"] or ""):
            fails.append("live coinmotion BTC-EUR")
        if any(t["quote"] not in markets.FIAT for t in live["tickers"]):
            fails.append("non-fiat quote leaked")
        live_pairs = markets.aggregate_pairs(live["tickers"])
        by_sym = {}
        for p in live_pairs:
            if p["symbol"] in by_sym:
                fails.append("duplicate aggregate " + p["symbol"])
            by_sym[p["symbol"]] = p
            if p["currency"] != p["quote"]:
                fails.append("currency label " + p["symbol"])
            if p["vwap"] is not None or p["volume_used_for_price"]:
                fails.append("live vwap " + p["symbol"])
            contrib_lasts = [c["last"] for c in p["contributors"] if c.get("last")]
            if contrib_lasts and p["last"] != markets.mean_decimal(contrib_lasts):
                fails.append("live mean drift " + p["symbol"])
            if any(c.get("exchange_id") is None for c in p["contributors"]):
                fails.append("contributor without exchange " + p["symbol"])
        if "BTC-NOK" in by_sym and "BTC-EUR" in by_sym and by_sym["BTC-NOK"]["price"] == by_sym["BTC-EUR"]["price"]:
            fails.append("nok and eur collapsed")
        if by_sym.get("BTC-NOK", {}).get("logo_path") != "api/v1/markets/logos/btc.svg":
            fails.append("live btc logo")
        cm_live = next((t for t in live["tickers"] if t["exchange"]["id"] == "coinmotion" and t["symbol"] == "BTC-EUR"), None)
        if cm_live and any(cm_live.get(k) not in (None, "") and not DECIMAL.fullmatch(cm_live.get(k) or "") for k in ("volume_base", "volume_quote", "volume_base_24h", "volume_quote_24h")):
            fails.append("coinmotion volume not a published decimal")
        skipped = {s["id"] for s in live["skipped"]}
        for need in ("safello", "goobit", "northcrypto", "kvarn-x", "iceland", "denmark"):
            if need not in skipped:
                fails.append("skip missing " + need)
        print("live", live["count"], "tickers", [(e["id"], e["status"], e["ticker_count"]) for e in live["exchanges"]])

    import subprocess
    js = subprocess.run(["node", os.path.join(ROOT, "tests", "markets_aggregate.test.js")], capture_output=True, text=True)
    if js.returncode != 0:
        fails.append("js aggregate: " + (js.stdout + js.stderr).strip().split("\n")[0])

    if fails:
        print("FAILED")
        for f in fails:
            print(" -", f)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
