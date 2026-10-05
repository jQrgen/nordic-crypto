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

    body = markets.empty_failure("boom")
    body["tickers"] = firi
    body["exchanges"][0]["status"] = "ok"
    body["exchanges"][0]["ticker_count"] = len(firi)
    body["count"] = len(firi)
    doc = markets.public_document(body, generated_at=FETCHED, preview=False)
    files = markets.documents(doc)
    for rel in ("api/v1/markets.json", "api/v1/markets/firi.json", "api/v1/markets/by-asset/BTC.json"):
        if rel not in files:
            fails.append("missing " + rel)
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
        skipped = {s["id"] for s in live["skipped"]}
        for need in ("safello", "goobit", "northcrypto", "kvarn-x", "iceland", "denmark"):
            if need not in skipped:
                fails.append("skip missing " + need)
        print("live", live["count"], "tickers", [(e["id"], e["status"], e["ticker_count"]) for e in live["exchanges"]])

    if fails:
        print("FAILED")
        for f in fails:
            print(" -", f)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
