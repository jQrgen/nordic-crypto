#!/usr/bin/env python3
"""Nordic exchange prices for the public JSON API.

Fetches official public REST tickers (no login, no scraping). Prices are copied
from the exchange response. A failed exchange is recorded with a timestamp and
omitted from the ticker list. Nothing is invented.

  python3 tools/markets.py                 # fetch and print a short summary
  python3 tools/markets.py --write DIR     # write api/v1/markets*.json into DIR
  python3 tools/markets.py --write DIR --keep-if-empty
      # hourly gh-pages job: do not replace a previous file when every exchange failed

Included when the public API answers:
  Firi (NO)          https://api.firi.com/v2/markets and /v2/markets/tickers
  NBX (NO)           https://api.nbx.com/markets and /tickers
  Coinmotion (FI)    https://api.coinmotion.com/v2/rates

Skipped (no unauthenticated public ticker): Safello, Goobit/BTCX, Trijo,
Northcrypto, Kvarn X, and no Danish- or Icelandic-registered venue with one.
DKK and SEK pairs that Firi, NBX or Coinmotion do publish are included.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "NordicCrypto/1.0 (+https://jqrgen.github.io/nordic-crypto/markets/; public market data)"
RAW_URL = "https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json"
PAGES_BASE = "https://jqrgen.github.io/nordic-crypto/"
CUSTOM_BASE = "https://cryptonordic.no/"
FIAT = ("NOK", "SEK", "DKK", "EUR")
ASSET_ORDER = ["BTC", "ETH", "SOL", "XRP", "ADA", "LTC", "DOGE", "DOT", "LINK", "BNB", "AVAX", "UNI", "AAVE", "XLM", "ATOM", "ALGO", "POL", "MATIC", "USDC"]
ASSET_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ether", "SOL": "Solana", "XRP": "XRP", "ADA": "Cardano",
    "LTC": "Litecoin", "DOGE": "Dogecoin", "DOT": "Polkadot", "LINK": "Chainlink",
    "BNB": "BNB", "AVAX": "Avalanche", "UNI": "Uniswap", "AAVE": "Aave", "XLM": "Stellar",
    "ATOM": "Cosmos", "ALGO": "Algorand", "POL": "Polygon", "MATIC": "Polygon", "USDC": "USD Coin",
}
IOS_TESTFLIGHT = "https://testflight.apple.com/join/nQ2fpjZn"
QUOTE_ORDER = list(FIAT)
DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")
TIMEOUT = 15

DISCLAIMER = (
    "Market data, not investment advice. Each figure is the value published by the named exchange "
    "at fetched_at. Nordic Crypto does not set these prices and does not tell anyone to buy or sell."
)
REFRESH = {
    "build": "Fetched when the site is built (./build.sh and ./publish.sh).",
    "github_actions": (
        ".github/workflows/markets-refresh.yml rewrites these JSON files on the gh-pages branch "
        "about once an hour (minute 17). It does not republish the rest of the site. "
        "If every exchange fails, the previous files are left as they are."
    ),
    "browser": (
        "The markets page reloads this file about every 15 minutes. "
        "Firi and Coinmotion send Access-Control-Allow-Origin: *, so the page also requests those "
        "APIs from the browser about every 5 minutes. "
        "api.nbx.com does not send that header, so a browser on this site cannot read NBX directly. "
        "NBX rows follow this file."
    ),
    "browser_json_seconds": 900,
    "browser_exchange_seconds": 300,
    "actions_cron": "17 * * * *",
}

# Static CORS results checked against the live responses (5 Oct 2026).
# The page still tolerates a failed browser fetch and keeps the file.
EXCHANGE_META = {
    "firi": {
        "id": "firi",
        "name": "Firi",
        "country": "NO",
        "website": "https://firi.com/",
        "docs_url": "https://developers.firi.com/",
        "source_url": "https://api.firi.com/v2/markets",
        "cors": True,
        "note": (
            "Norwegian exchange (also lists DKK pairs). "
            "last, high, low, volume and change come from GET /v2/markets/{market}. "
            "bid and ask come from GET /v2/markets/tickers. "
            "The public payload does not name a 24-hour window on those fields."
        ),
    },
    "nbx": {
        "id": "nbx",
        "name": "Norwegian Block Exchange",
        "country": "NO",
        "website": "https://nbx.com/",
        "docs_url": "https://app.nbx.com/developers",
        "source_url": "https://api.nbx.com/tickers",
        "cors": False,
        "note": (
            "Norwegian exchange. Public tickers include NOK, SEK, DKK and EUR. "
            "last is lastTradePrice. bid is currentHighestBuyPrice. ask is currentLowestSellPrice. "
            "volume_*_24h is the exchange's last-24-hours field. "
            "GET /markets/{id}/orders (the order book) is not public. "
            "The API does not send Access-Control-Allow-Origin."
        ),
    },
    "coinmotion": {
        "id": "coinmotion",
        "name": "Coinmotion",
        "country": "FI",
        "website": "https://coinmotion.com/",
        "docs_url": "https://api.coinmotion.com/v2/rates",
        "source_url": "https://api.coinmotion.com/v2/rates",
        "cors": True,
        "note": (
            "Finnish broker. Public rates include EUR and SEK. "
            "There is no last-trade field, so last is null. "
            "bid is the buy field (the price Coinmotion pays for the asset) and "
            "ask is the sell field (the price Coinmotion charges). "
            "Pairs quoted in BTC or USDC are left out. "
            "The response sends Access-Control-Allow-Origin: *."
        ),
    },
}

SKIPPED = [
    {
        "id": "safello",
        "name": "Safello",
        "country": "SE",
        "reason": "GET https://api.safello.com/v2/market/tickers requires an OAuth token with the market scope. No unauthenticated ticker was found.",
    },
    {
        "id": "goobit",
        "name": "Goobit (BTCX)",
        "country": "SE",
        "reason": "No public ticker was found. btcx.se redirects to bt.cx, and https://bt.cx/sv/api/ticker returns 404.",
    },
    {
        "id": "trijo",
        "name": "Trijo",
        "country": "SE",
        "reason": "No public unauthenticated ticker API was found.",
    },
    {
        "id": "northcrypto",
        "name": "Northcrypto",
        "country": "FI",
        "reason": "No public ticker was found. Common paths on northcrypto.com (/api, /api/markets, /api/tickers) return 404.",
    },
    {
        "id": "kvarn-x",
        "name": "Kvarn X",
        "country": "FI",
        "reason": "The documented REST API is a partner integration for customer orders, not a public ticker.",
    },
    {
        "id": "denmark",
        "name": "Danish-registered exchange",
        "country": "DK",
        "reason": "No Danish-registered exchange with a public ticker was found. DKK pairs published by Firi and NBX (both Norway) are included.",
    },
    {
        "id": "iceland",
        "name": "Icelandic exchange",
        "country": "IS",
        "reason": "No Icelandic crypto exchange with a public ticker API was found. Monerium issues e-money and does not publish a spot-market ticker.",
    },
]


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def format_price(value):
    """Grouping for the page. The API keeps the exchange's decimal string."""
    if value is None or value == "":
        return "—"
    s = str(value)
    neg = s.startswith("-")
    body = s[1:] if neg else s
    whole, dot, frac = body.partition(".")
    if dot:
        frac = frac.rstrip("0")
    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    text = " ".join(reversed(groups))
    if frac:
        text += "." + frac
    return ("-" if neg else "") + text


def decimal(value):
    """Exchange decimal as published, or None. Never coerced through float."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        # JSON numbers only; reject non-finite. Format without binary noise when the
        # payload used a JSON number instead of a string (Coinmotion timestamps aside).
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return None
        text = str(value)
        if "e" in text.lower():
            return None
    else:
        text = str(value).strip()
    if not DECIMAL.fullmatch(text):
        return None
    return text


def split_suffix(symbol, suffixes):
    for quote in suffixes:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[: -len(quote)], quote
    return None, None


def ticker(exchange, exchange_symbol, base, quote, fetched_at, source_url, last=None, bid=None, ask=None, **extra):
    base = (base or "").upper()
    quote = (quote or "").upper()
    if not base or quote not in FIAT:
        return None
    last, bid, ask = decimal(last), decimal(bid), decimal(ask)
    if last is None and bid is None and ask is None:
        return None
    row = {
        "id": f"{exchange['id']}:{base}-{quote}",
        "symbol": f"{base}-{quote}",
        "exchange_symbol": exchange_symbol,
        "base": base,
        "quote": quote,
        "last": last,
        "bid": bid,
        "ask": ask,
        "exchange": {"id": exchange["id"], "name": exchange["name"], "country": exchange["country"]},
        "fetched_at": fetched_at,
        "source_url": source_url,
        "volume_base": decimal(extra.get("volume_base")),
        "volume_quote": decimal(extra.get("volume_quote")),
        "volume_base_24h": decimal(extra.get("volume_base_24h")),
        "volume_quote_24h": decimal(extra.get("volume_quote_24h")),
        "high": decimal(extra.get("high")),
        "low": decimal(extra.get("low")),
        "change_pct": decimal(extra.get("change_pct")),
    }
    if extra.get("exchange_time"):
        row["exchange_time"] = extra["exchange_time"]
    return row


def http_json(url, retried=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            cors = resp.headers.get("Access-Control-Allow-Origin")
            status = resp.status
    except urllib.error.HTTPError as ex:
        if ex.code in (429, 500, 502, 503, 504) and not retried:
            time.sleep(2)
            return http_json(url, retried=True)
        raise RuntimeError(f"HTTP {ex.code} from {url}") from None
    except urllib.error.URLError as ex:
        if not retried:
            time.sleep(2)
            return http_json(url, retried=True)
        raise RuntimeError(f"Could not reach {url}") from ex
    if status != 200:
        raise RuntimeError(f"HTTP {status} from {url}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as ex:
        raise RuntimeError(f"Not JSON from {url}") from ex
    return data, cors


def parse_firi(markets, tickers, fetched_at):
    meta = EXCHANGE_META["firi"]
    by_id = {}
    if isinstance(tickers, list):
        for row in tickers:
            if isinstance(row, dict) and row.get("market"):
                by_id[row["market"]] = row
    out = []
    if not isinstance(markets, list):
        raise RuntimeError("Firi /v2/markets was not a list")
    for row in markets:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        base, quote = split_suffix(row["id"], FIAT)
        book = by_id.get(row["id"]) or {}
        item = ticker(
            meta, row["id"], base, quote, fetched_at,
            f"https://api.firi.com/v2/markets/{row['id']}",
            last=row.get("last"), bid=book.get("bid"), ask=book.get("ask"),
            volume_base=row.get("volume"), high=row.get("high"), low=row.get("low"),
            change_pct=row.get("change"),
        )
        if item:
            out.append(item)
    return out


def parse_nbx(markets, tickers, fetched_at):
    meta = EXCHANGE_META["nbx"]
    disabled = set()
    if isinstance(markets, list):
        for row in markets:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            if row.get("disabled") or row.get("status") not in (None, "OK"):
                disabled.add(row["id"])
    out = []
    if not isinstance(tickers, list):
        raise RuntimeError("NBX /tickers was not a list")
    for row in tickers:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        if row["id"] in disabled:
            continue
        item = ticker(
            meta, row["id"], row.get("baseAsset"), row.get("quoteAsset"), fetched_at,
            "https://api.nbx.com/tickers",
            last=row.get("lastTradePrice"),
            bid=row.get("currentHighestBuyPrice"),
            ask=row.get("currentLowestSellPrice"),
            volume_base_24h=row.get("volumeBaseAssetLast24Hours"),
            volume_quote_24h=row.get("volumeQuoteAssetLast24Hours"),
        )
        if item:
            out.append(item)
    return out


def parse_coinmotion(payload, fetched_at):
    meta = EXCHANGE_META["coinmotion"]
    if not isinstance(payload, dict) or payload.get("success") is False:
        raise RuntimeError("Coinmotion /v2/rates did not succeed")
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    exchange_time = None
    ts = body.get("timestamp") if isinstance(body, dict) else None
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        try:
            exchange_time = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).replace(microsecond=0).isoformat()
        except (OverflowError, OSError, ValueError):
            exchange_time = None
    out = []
    for key, row in body.items():
        if not isinstance(row, dict):
            continue
        # currencyCode is the asset; baseCurrencyCode is the quote (EUR, SEK, …).
        base = row.get("currencyCode")
        quote = row.get("baseCurrencyCode")
        if not base or not quote:
            continue
        item = ticker(
            meta, key, base, quote, fetched_at,
            "https://api.coinmotion.com/v2/rates",
            last=None, bid=row.get("buy"), ask=row.get("sell"),
            high=row.get("high"), low=row.get("low"),
            exchange_time=exchange_time,
        )
        if item:
            out.append(item)
    return out


def _exchange_record(eid, fetched_at, status, error, count):
    meta = dict(EXCHANGE_META[eid])
    meta.update(status=status, fetched_at=fetched_at, error=error, ticker_count=count)
    return meta


def _one(eid, calls, parse):
    fetched_at = now_iso()
    try:
        loaded = []
        for url in calls:
            data, _cors = http_json(url)
            loaded.append(data)
        rows = parse(*loaded, fetched_at)
    except Exception as ex:
        message = str(ex).split("\n")[0][:300]
        print(f"markets: {eid} failed: {message}", file=sys.stderr)
        return _exchange_record(eid, fetched_at, "error", message, 0), []
    return _exchange_record(eid, fetched_at, "ok", None, len(rows)), rows


def fetch():
    """Live fetch. One exchange failing does not drop the others."""
    exchanges = []
    tickers = []
    jobs = (
        ("firi", (
            "https://api.firi.com/v2/markets",
            "https://api.firi.com/v2/markets/tickers",
        ), parse_firi),
        ("nbx", (
            "https://api.nbx.com/markets",
            "https://api.nbx.com/tickers",
        ), parse_nbx),
        ("coinmotion", (
            "https://api.coinmotion.com/v2/rates",
        ), parse_coinmotion),
    )
    for eid, urls, parser in jobs:
        rec, rows = _one(eid, urls, parser)
        exchanges.append(rec)
        tickers.extend(rows)
        print(f"markets: {eid} {rec['status']} {len(rows)} tickers")
    tickers.sort(key=lambda t: (t["exchange"]["id"], _asset_key(t["base"]), _quote_key(t["quote"])))
    return {
        "disclaimer": DISCLAIMER,
        "sign_off": "The Nordic Crypto team",
        "not_investment_advice": True,
        "quotes": list(FIAT),
        "quote_note": "Only NOK, SEK, DKK and EUR quotes are included. A price in one currency is not converted into another.",
        "refresh": REFRESH,
        "exchanges": exchanges,
        "skipped": SKIPPED,
        "count": len(tickers),
        "tickers": tickers,
    }


def _asset_key(base):
    return (ASSET_ORDER.index(base) if base in ASSET_ORDER else len(ASSET_ORDER), base)


def _quote_key(quote):
    return (QUOTE_ORDER.index(quote) if quote in QUOTE_ORDER else len(QUOTE_ORDER), quote)


def public_document(body, *, generated_at, preview, base=PAGES_BASE, custom=CUSTOM_BASE):
    base = base if base.endswith("/") else base + "/"
    custom = custom if custom.endswith("/") else custom + "/"
    doc = {
        "api_version": "1",
        "name": "Nordic Crypto",
        "generated_at": generated_at,
        "preview": bool(preview),
        "kind": "markets",
        "disclaimer": body["disclaimer"],
        "sign_off": body["sign_off"],
        "not_investment_advice": True,
        "quotes": body["quotes"],
        "quote_note": body["quote_note"],
        "refresh": body["refresh"],
        "urls": {
            "github_pages": base + "api/v1/markets.json",
            "raw_githubusercontent": RAW_URL,
            "custom_domain": custom + "api/v1/markets.json",
        },
        "exchanges": body["exchanges"],
        "skipped": body["skipped"],
        "count": len(body["tickers"]),
        "tickers": body["tickers"],
    }
    return doc


def documents(doc):
    """Relative path -> JSON object, including per-exchange and per-asset files."""
    out = {"api/v1/markets.json": doc}
    by_ex = {}
    by_asset = {}
    for row in doc["tickers"]:
        by_ex.setdefault(row["exchange"]["id"], []).append(row)
        by_asset.setdefault(row["base"], []).append(row)
    for ex in doc["exchanges"]:
        rows = by_ex.get(ex["id"], [])
        out[f"api/v1/markets/{ex['id']}.json"] = _slice(
            doc, exchange=ex, count=len(rows), tickers=rows,
        )
    for base, rows in by_asset.items():
        safe = re.sub(r"[^A-Za-z0-9._-]+", "", base) or "asset"
        out[f"api/v1/markets/by-asset/{safe}.json"] = _slice(
            doc, symbol=base, count=len(rows), tickers=rows,
        )
    return out


def _slice(doc, **kw):
    return {
        "api_version": doc["api_version"],
        "name": doc["name"],
        "generated_at": doc["generated_at"],
        "preview": doc["preview"],
        "kind": "markets",
        "disclaimer": doc["disclaimer"],
        "sign_off": doc["sign_off"],
        "not_investment_advice": True,
        "urls": doc["urls"],
        **kw,
    }


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def write_dir(directory, doc):
    for rel, obj in documents(doc).items():
        dump(os.path.join(directory, rel), obj)
    return len(doc["tickers"])


def empty_failure(message):
    fetched_at = now_iso()
    exchanges = [_exchange_record(eid, fetched_at, "error", message, 0) for eid in EXCHANGE_META]
    return {
        "disclaimer": DISCLAIMER,
        "sign_off": "The Nordic Crypto team",
        "not_investment_advice": True,
        "quotes": list(FIAT),
        "quote_note": "Only NOK, SEK, DKK and EUR quotes are included. A price in one currency is not converted into another.",
        "refresh": REFRESH,
        "exchanges": exchanges,
        "skipped": SKIPPED,
        "count": 0,
        "tickers": [],
    }


def main():
    write_to = None
    keep_if_empty = False
    args = sys.argv[1:]
    if "--write" in args:
        i = args.index("--write")
        if i + 1 >= len(args):
            print("usage: tools/markets.py [--write DIR] [--keep-if-empty]", file=sys.stderr)
            return 2
        write_to = args[i + 1]
    keep_if_empty = "--keep-if-empty" in args
    body = fetch()
    doc = public_document(body, generated_at=now_iso(), preview=False)
    if write_to:
        if keep_if_empty and not doc["tickers"]:
            print("markets: every exchange failed; leaving existing files")
            return 0
        n = write_dir(write_to, doc)
        print(f"markets: wrote {n} tickers under {write_to}")
    else:
        print(json.dumps({
            "count": doc["count"],
            "exchanges": [{k: ex[k] for k in ("id", "status", "ticker_count", "error", "fetched_at")} for ex in doc["exchanges"]],
        }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
