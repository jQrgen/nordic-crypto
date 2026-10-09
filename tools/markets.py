#!/usr/bin/env python3
"""Nordic exchange prices for the public JSON API.

Fetches official public REST tickers (no login, no scraping). Prices are copied
from the exchange response. A failed exchange is recorded with a timestamp and
omitted from the ticker list. Nothing is invented.

Also writes one aggregated row per base-quote pair (BTC-NOK stays separate from
BTC-EUR). last is the arithmetic mean of published last prices. Volume is summed
only inside the same field. Coin icons are copied from the CC0 cryptocurrency-icons
set when that set includes the asset.

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
import shutil
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import site_url  # noqa: E402
UA = f"NordicCrypto/1.0 (+{site_url.join('markets/')}; public market data)"
RAW_URL = "https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json"
# One public origin. Both names remain so older callers keep working.
PAGES_BASE = site_url.BASE
CUSTOM_BASE = site_url.BASE
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
        "about once an hour (minute 17), including api/v1/markets/aggregated.json, the per-asset files "
        "and the coin icons under api/v1/markets/logos/. It does not republish the rest of the site. "
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


def _load_coins():
    path = os.path.join(ROOT, "assets", "img", "coins", "coins.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


COINS = _load_coins()
EXCHANGE_ORDER = ["firi", "nbx", "coinmotion"]
LOGO_API = "api/v1/markets/logos"
VOLUME_UNITS = {
    "volume_base": "base asset; window not named by the exchange",
    "volume_quote": "quote currency; window not named by the exchange",
    "volume_base_24h": "base asset; last 24 hours, as named by the exchange",
    "volume_quote_24h": "quote currency; last 24 hours, as named by the exchange",
}
AGGREGATION = {
    "bucket": (
        "One row per base-quote pair. BTC-NOK is never averaged with BTC-EUR, BTC-SEK or BTC-DKK. "
        "Nordic Crypto does not convert between quote currencies."
    ),
    "last": (
        "Arithmetic mean of last prices from exchanges that published a last for this pair. "
        "Null when none did. Coinmotion publishes no last trade, so its row is left out of last."
    ),
    "mid": (
        "For each exchange that published both bid and ask, the midpoint is (bid+ask)/2. "
        "mid is the arithmetic mean of those midpoints. It is not blended with last."
    ),
    "price": "Equals last when any last exists, otherwise mid. min and max use that same series. Null when neither series exists. No price is invented.",
    "min": "Lowest value in the same series as price. The original published figure, or the midpoint when price is a bid/ask mean.",
    "max": "Highest value in the same series as price.",
    "exchange_count": "How many exchanges published a ticker for this pair.",
    "rounding": (
        "Decimal arithmetic on the published digit strings, not binary floating point. "
        "A mean keeps the widest fractional length among its inputs. "
        "If the quotient needs more places, further digits are kept up to 12 fractional digits, then half away from zero. "
        "A sum keeps the widest fractional length and is exact."
    ),
    "vwap": (
        "Not computed. Firi's volume is not labeled 24-hour, NBX labels a 24-hour volume, and Coinmotion publishes none. "
        "Those are not one weight, so the price is not volume-weighted."
    ),
    "volume": (
        "Each volume field is summed only with the same field, and only inside one pair. "
        "volume_base is the base asset and volume_quote is the quote currency; the exchange did not name a window (this is where Firi's volume is stored). "
        "volume_base_24h is the base asset over the last 24 hours and volume_quote_24h is the quote currency over the last 24 hours (NBX). "
        "The 24-hour fields are not added to the unlabeled fields. "
        "A null sum means no included exchange published that field. A published zero is kept. Missing volume is not treated as zero."
    ),
    "logos": (
        "SVG icons from cryptocurrency-icons 0.18.1 (CC0-1.0) when that set includes the asset. "
        "logo_url is null otherwise. Nordic Crypto does not draw new icons and does not reuse the MATIC icon for POL."
    ),
}


def _parse_decimal(text):
    if text is None or isinstance(text, bool) or not DECIMAL.fullmatch(str(text)):
        return None
    body = str(text)
    neg = body.startswith("-")
    if neg:
        body = body[1:]
    whole, _, frac = body.partition(".")
    return neg, whole or "0", frac


def _format_scaled(n, scale, neg):
    """n is a non-negative int. The value is n / 10**scale."""
    if scale <= 0:
        text = str(n)
    else:
        digits = str(n).rjust(scale + 1, "0")
        text = digits[:-scale] + "." + digits[-scale:]
    if neg and n != 0:
        text = "-" + text
    return text


def _scaled_ints(texts):
    parsed = []
    for text in texts:
        item = _parse_decimal(text)
        if item is None:
            return None
        parsed.append(item)
    if not parsed:
        return None
    scale = max(len(frac) for _, _, frac in parsed)
    ints = []
    for neg, whole, frac in parsed:
        n = int(whole + frac.ljust(scale, "0"))
        ints.append(-n if neg else n)
    return ints, scale


def sum_decimal(texts):
    """Exact sum of decimal strings. None when texts is empty. Missing values stay out."""
    scaled = _scaled_ints(texts)
    if scaled is None:
        return None
    ints, scale = scaled
    total = sum(ints)
    return _format_scaled(abs(total), scale, total < 0)


def mean_decimal(texts):
    """Arithmetic mean of decimal strings. None when texts is empty."""
    scaled = _scaled_ints(texts)
    if scaled is None:
        return None
    ints, scale = scaled
    count = len(ints)
    total = sum(ints)
    neg = total < 0
    total = abs(total)
    q, r = divmod(total, count)
    extra = []
    used = scale
    while r and used < 12:
        r *= 10
        digit, r = divmod(r, count)
        extra.append(digit)
        used += 1
    if r and (r * 10) // count >= 5:
        if extra:
            i = len(extra) - 1
            extra[i] += 1
            while extra[i] == 10:
                extra[i] = 0
                if i == 0:
                    q += 1
                    break
                i -= 1
                extra[i] += 1
        else:
            q += 1
    for digit in extra:
        q = q * 10 + digit
    return _format_scaled(q, scale + len(extra), neg)


def _extreme(texts, want):
    parsed = []
    for text in texts:
        item = _parse_decimal(text)
        if item is not None:
            parsed.append((text, item))
    if not parsed:
        return None
    scale = max(len(frac) for _, (_, _, frac) in parsed)
    best = None
    best_key = None
    for text, (neg, whole, frac) in parsed:
        n = int(whole + frac.ljust(scale, "0"))
        if neg:
            n = -n
        if best is None or (n < best_key if want == "min" else n > best_key):
            best, best_key = text, n
    return best


def logo_for(base, pages_base=PAGES_BASE, custom_base=CUSTOM_BASE):
    """Icon URLs for one asset, or nulls when cryptocurrency-icons has no file."""
    pages_base = pages_base if pages_base.endswith("/") else pages_base + "/"
    custom_base = custom_base if custom_base.endswith("/") else custom_base + "/"
    filename = (COINS.get("icons") or {}).get(base)
    if not filename:
        return {"logo_url": None, "logo_url_custom_domain": None, "logo_path": None, "logo": None}
    rel = f"{LOGO_API}/{filename}"
    return {
        "logo_url": pages_base + rel,
        "logo_url_custom_domain": custom_base + rel,
        "logo_path": rel,
        "logo": {
            "format": "svg",
            "source": COINS.get("source"),
            "source_url": COINS.get("source_url"),
            "version": COINS.get("version"),
            "license": COINS.get("license"),
            "license_name": COINS.get("license_name"),
            "license_url": COINS.get("license_url"),
            "authors": COINS.get("authors"),
            "attribution": (
                f"{base} icon from cryptocurrency-icons ({COINS.get('license')}), {COINS.get('source_url')}. "
                "Nordic Crypto does not claim these icons."
            ),
        },
    }


def _vol_block(rows):
    out = {"units": dict(VOLUME_UNITS)}
    for field in ("volume_base", "volume_quote", "volume_base_24h", "volume_quote_24h"):
        vals = [row.get(field) for row in rows if row.get(field) not in (None, "")]
        out[field] = sum_decimal(vals) if vals else None
        out[field + "_exchanges"] = len(vals) if vals else 0
    return out


def _contributor(row):
    bid, ask, last = row.get("bid"), row.get("ask"), row.get("last")
    mid = mean_decimal([bid, ask]) if bid is not None and ask is not None else None
    ex = row.get("exchange") or {}
    return {
        "exchange_id": ex.get("id"),
        "name": ex.get("name"),
        "country": ex.get("country"),
        "last": last,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "included_in_last": last is not None,
        "included_in_mid": mid is not None,
        "volume_base": row.get("volume_base"),
        "volume_quote": row.get("volume_quote"),
        "volume_base_24h": row.get("volume_base_24h"),
        "volume_quote_24h": row.get("volume_quote_24h"),
        "fetched_at": row.get("fetched_at"),
        "source_url": row.get("source_url"),
    }


def _dedupe_exchange(rows):
    """One ticker per exchange inside a pair. A later fetched_at replaces an earlier one."""
    chosen = {}
    order = []
    for row in rows:
        eid = (row.get("exchange") or {}).get("id") or ""
        prev = chosen.get(eid)
        if prev is None:
            chosen[eid] = row
            order.append(eid)
            continue
        if (row.get("fetched_at") or "") >= (prev.get("fetched_at") or ""):
            chosen[eid] = row
    rows = [chosen[eid] for eid in order]
    rows.sort(key=lambda row: (
        EXCHANGE_ORDER.index(row["exchange"]["id"]) if row["exchange"]["id"] in EXCHANGE_ORDER else len(EXCHANGE_ORDER),
        row["exchange"]["id"],
    ))
    return rows


def _dec_parts(text):
    return _parse_decimal(text)


def _dec_int(text, scale):
    item = _dec_parts(text)
    if item is None:
        return None
    neg, whole, frac = item
    n = int(whole + frac.ljust(scale, "0"))
    return -n if neg else n


def _is_positive_decimal(text):
    item = _dec_parts(text)
    if item is None or item[0]:
        return False
    _neg, whole, frac = item
    return bool(whole.strip("0")) or bool(frac.strip("0"))


def _below_share(part, total, num, den):
    """True when part/total is strictly under num/den. Non-positive part counts as under."""
    if not _is_positive_decimal(part) or not _is_positive_decimal(total):
        return True
    scale = max(len(_dec_parts(part)[2]), len(_dec_parts(total)[2]))
    p, t = _dec_int(part, scale), _dec_int(total, scale)
    return p * den < t * num


def _tenths_division(part, total):
    """floor(part/total*1000), remainder, divisor. (0, 0, 1) when total is not positive."""
    if not _is_positive_decimal(part) or not _is_positive_decimal(total):
        return 0, 0, 1
    scale = max(len(_dec_parts(part)[2]), len(_dec_parts(total)[2]))
    p, t = _dec_int(part, scale), _dec_int(total, scale)
    q, r = divmod(p * 1000, t)
    return q, r, t


def volume_shares(tickers, names=None, threshold=(3, 100)):
    """Share of 24-hour quote volume per coin. One group per quote currency.

    Uses volume_quote_24h only, summed across exchanges inside that currency.
    NOK is never added to SEK, DKK or EUR. Firi's unlabeled base-asset volume
    is not included, and a missing volume is not treated as zero. A published
    zero is left out of the share. Coins strictly under `threshold` (default
    3/100) are grouped as Other when at least one coin is at or above it.
    Displayed percentages are tenths and sum to 100.0 (largest remainder).
    """
    names = ASSET_NAMES if names is None else names
    num, den = threshold
    by_quote = {}
    for row in tickers or []:
        base, quote = row.get("base"), row.get("quote")
        vol = row.get("volume_quote_24h")
        if not base or not quote or not _is_positive_decimal(vol):
            continue
        by_quote.setdefault(quote, {}).setdefault(base, []).append(row)
    groups = []
    for quote in sorted(by_quote, key=_quote_key):
        coins = []
        for base, rows in by_quote[quote].items():
            rows = _dedupe_exchange(rows)
            vols = [row.get("volume_quote_24h") for row in rows if _is_positive_decimal(row.get("volume_quote_24h"))]
            total = sum_decimal(vols) if vols else None
            if not _is_positive_decimal(total):
                continue
            fetched = [row.get("fetched_at") for row in rows if row.get("fetched_at")]
            sources = []
            seen = set()
            for row in rows:
                if not _is_positive_decimal(row.get("volume_quote_24h")):
                    continue
                ex = row.get("exchange") or {}
                key = (ex.get("id") or "", row.get("source_url") or "")
                if key in seen:
                    continue
                seen.add(key)
                sources.append({"id": ex.get("id") or "", "name": ex.get("name") or ex.get("id") or "", "url": row.get("source_url") or ""})
            sources.sort(key=lambda src: (
                EXCHANGE_ORDER.index(src["id"]) if src["id"] in EXCHANGE_ORDER else len(EXCHANGE_ORDER),
                src["id"],
                src["url"],
            ))
            coins.append({
                "base": base,
                "name": names.get(base) or base,
                "volume": total,
                "logo_path": logo_for(base).get("logo_path"),
                "fetched": fetched,
                "sources": sources,
            })
        if not coins:
            continue
        grand = sum_decimal([c["volume"] for c in coins])
        if not _is_positive_decimal(grand):
            continue
        scale = max(len(_dec_parts(c["volume"])[2]) for c in coins)
        coins.sort(key=lambda c: (-_dec_int(c["volume"], scale), c["base"]))
        large = [c for c in coins if not _below_share(c["volume"], grand, num, den)]
        small = [c for c in coins if _below_share(c["volume"], grand, num, den)]
        if not large:
            large, small = coins, []
        slices = []
        for coin in large:
            slices.append({
                "base": coin["base"],
                "name": coin["name"],
                "volume": coin["volume"],
                "logo_path": coin["logo_path"],
                "other": False,
                "members": [coin["base"]],
            })
        if small:
            small_scale = max(len(_dec_parts(c["volume"])[2]) for c in small)
            small.sort(key=lambda c: (-_dec_int(c["volume"], small_scale), c["base"]))
            slices.append({
                "base": None,
                "name": None,
                "volume": sum_decimal([c["volume"] for c in small]),
                "logo_path": None,
                "other": True,
                "members": [c["base"] for c in small],
            })
        parts = [_tenths_division(sl["volume"], grand) for sl in slices]
        remain = 1000 - sum(p[0] for p in parts)
        order = list(range(len(parts)))

        def _rem_key(i, j):
            ri, di = parts[i][1], parts[i][2]
            rj, dj = parts[j][1], parts[j][2]
            left, right = ri * dj, rj * di
            if left != right:
                return -1 if left > right else 1
            return i - j

        from functools import cmp_to_key
        order.sort(key=cmp_to_key(_rem_key))
        tenths = [p[0] for p in parts]
        for n in range(max(0, remain)):
            tenths[order[n]] += 1
        for sl, tenth in zip(slices, tenths):
            sl["tenths"] = tenth
            sl["pct"] = f"{tenth // 10}.{tenth % 10}"
        fetched = [item for coin in coins for item in coin["fetched"]]
        sources = []
        seen = set()
        for coin in coins:
            for src in coin["sources"]:
                key = (src["id"], src["url"])
                if key in seen:
                    continue
                seen.add(key)
                sources.append(src)
        sources.sort(key=lambda src: (
            EXCHANGE_ORDER.index(src["id"]) if src["id"] in EXCHANGE_ORDER else len(EXCHANGE_ORDER),
            src["id"],
            src["url"],
        ))
        groups.append({
            "quote": quote,
            "window": "24h",
            "field": "volume_quote_24h",
            "total": grand,
            "updated_at": max(fetched) if fetched else None,
            "sources": sources,
            "threshold_pct": num,
            "slices": slices,
        })
    return groups


def aggregate_pairs(tickers, pages_base=PAGES_BASE, custom_base=CUSTOM_BASE):
    """One aggregate per base-quote pair. Quote currencies are not mixed."""
    groups = {}
    for row in tickers or []:
        if not row.get("base") or not row.get("quote"):
            continue
        groups.setdefault((row["base"], row["quote"]), []).append(row)
    pairs = []
    for base, quote in sorted(groups, key=lambda item: (_asset_key(item[0]), _quote_key(item[1]))):
        rows = _dedupe_exchange(groups[(base, quote)])
        contributors = [_contributor(row) for row in rows]
        lasts = [c["last"] for c in contributors if c["last"] is not None]
        mids = [c["mid"] for c in contributors if c["mid"] is not None]
        last = mean_decimal(lasts) if lasts else None
        mid = mean_decimal(mids) if mids else None
        if lasts:
            method, series = "mean_last", lasts
            price = last
            note = (
                "Arithmetic mean of last prices from exchanges that published a last for this pair. "
                "Exchanges without a last stay in contributors and are left out of last, min and max. "
                "Not weighted by volume."
            )
        elif mids:
            method, series = "mean_bid_ask_mid", mids
            price = mid
            note = (
                "No exchange published a last for this pair. "
                "price is the arithmetic mean of (bid+ask)/2 from exchanges that published both. "
                "It is not a last-trade average."
            )
        else:
            method, series, price = None, [], None
            note = "No last price, and no exchange published both a bid and an ask. No price is invented."
        if method == "mean_last" and mid is not None:
            note += " mid is the mean of bid/ask midpoints and is not mixed into last."
        fetched = [c["fetched_at"] for c in contributors if c.get("fetched_at")]
        logo = logo_for(base, pages_base, custom_base)
        for c in contributors:
            c["included_in_price"] = (c["last"] is not None) if method == "mean_last" else (c["mid"] is not None) if method == "mean_bid_ask_mid" else False
        name = ASSET_NAMES.get(base)
        pairs.append({
            "symbol": f"{base}-{quote}",
            "base": base,
            "name": name,
            "quote": quote,
            "currency": quote,
            "updated_at": max(fetched) if fetched else None,
            "oldest_fetched_at": min(fetched) if fetched else None,
            "exchange_count": len(contributors),
            "method": method,
            "method_note": note,
            "price": price,
            "min": _extreme(series, "min") if series else None,
            "max": _extreme(series, "max") if series else None,
            "last": last,
            "last_count": len(lasts),
            "last_min": _extreme(lasts, "min") if lasts else None,
            "last_max": _extreme(lasts, "max") if lasts else None,
            "mid": mid,
            "mid_count": len(mids),
            "mid_min": _extreme(mids, "min") if mids else None,
            "mid_max": _extreme(mids, "max") if mids else None,
            "vwap": None,
            "volume_used_for_price": False,
            "volume": _vol_block(contributors),
            "contributors": contributors,
            **logo,
        })
    return pairs


def public_document(body, *, generated_at, preview, base=PAGES_BASE, custom=CUSTOM_BASE):
    base = base if base.endswith("/") else base + "/"
    custom = custom if custom.endswith("/") else custom + "/"
    pairs = aggregate_pairs(body["tickers"], base, custom)
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
        "aggregation": AGGREGATION,
        "refresh": body["refresh"],
        "urls": {
            "github_pages": base + "api/v1/markets.json",
            "raw_githubusercontent": RAW_URL,
            "custom_domain": custom + "api/v1/markets.json",
            "aggregated_github_pages": base + "api/v1/markets/aggregated.json",
            "aggregated_custom_domain": custom + "api/v1/markets/aggregated.json",
            "logos": base + LOGO_API + "/",
        },
        "exchanges": body["exchanges"],
        "skipped": body["skipped"],
        "count": len(body["tickers"]),
        "aggregated_count": len(pairs),
        "tickers": body["tickers"],
        "aggregated": pairs,
    }
    return doc


def aggregated_document(doc):
    return {
        "api_version": doc["api_version"],
        "name": doc["name"],
        "generated_at": doc["generated_at"],
        "preview": doc["preview"],
        "kind": "markets-aggregated",
        "disclaimer": doc["disclaimer"],
        "sign_off": doc["sign_off"],
        "not_investment_advice": True,
        "quotes": doc.get("quotes"),
        "quote_note": doc.get("quote_note"),
        "aggregation": doc.get("aggregation"),
        "urls": {
            "github_pages": (doc.get("urls") or {}).get("aggregated_github_pages"),
            "custom_domain": (doc.get("urls") or {}).get("aggregated_custom_domain"),
            "logos": (doc.get("urls") or {}).get("logos"),
            "tickers": (doc.get("urls") or {}).get("github_pages"),
        },
        "count": len(doc.get("aggregated") or []),
        "pairs": doc.get("aggregated") or [],
    }


def documents(doc):
    """Relative path -> JSON object, including per-exchange, per-asset and aggregated files."""
    out = {
        "api/v1/markets.json": doc,
        "api/v1/markets/aggregated.json": aggregated_document(doc),
    }
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
    pages = ((doc.get("urls") or {}).get("github_pages") or PAGES_BASE).rsplit("api/v1/markets.json", 1)[0] or PAGES_BASE
    custom = ((doc.get("urls") or {}).get("custom_domain") or CUSTOM_BASE).rsplit("api/v1/markets.json", 1)[0] or CUSTOM_BASE
    for base, rows in by_asset.items():
        safe = re.sub(r"[^A-Za-z0-9._-]+", "", base) or "asset"
        pairs = [p for p in (doc.get("aggregated") or []) if p.get("base") == base]
        logo = logo_for(base, pages, custom)
        out[f"api/v1/markets/by-asset/{safe}.json"] = _slice(
            doc, symbol=base, name=ASSET_NAMES.get(base), count=len(rows), tickers=rows,
            aggregated=pairs, aggregation=doc.get("aggregation"), **logo,
        )
    return out


def write_logos(directory):
    """Copy vendored CC0 icons into api/v1/markets/logos/ so the markets files serve them."""
    src_dir = os.path.join(ROOT, "assets", "img", "coins")
    dest = os.path.join(directory, LOGO_API)
    os.makedirs(dest, exist_ok=True)
    n = 0
    for filename in (COINS.get("icons") or {}).values():
        src = os.path.join(src_dir, filename)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(dest, filename))
            n += 1
    lic = os.path.join(src_dir, "LICENSE")
    if os.path.isfile(lic):
        shutil.copyfile(lic, os.path.join(dest, "LICENSE"))
    return n


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
    write_logos(directory)
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
