"""Monthly hosting and domain costs for /budget/.

Figures live only in data/budget.json. This module adds those monthly amounts and
converts them with the rates in that file. It does not add labour or any other line.
"""
import datetime as dt
import json
import os
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "budget.json")
_KINDS = ("server", "volume", "workers", "domains", "pages", "dns")
_NEED = {
    "server": ("name", "type", "place", "runs"),
    "volume": ("gb", "unit_price", "unit_currency"),
    "workers": (),
    "domains": ("names", "vendor", "amount_year"),
    "pages": ("host",),
    "dns": (),
}


def load(path=None):
    with open(path or PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    _validate(doc)
    return doc


def _dec(text, where):
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{where}: amount must be a string, not {text!r}")
    try:
        value = Decimal(text)
    except Exception as ex:
        raise ValueError(f"{where}: {text!r} is not a decimal") from ex
    if value < 0:
        raise ValueError(f"{where}: negative amount")
    return value


def _validate(doc):
    if not isinstance(doc.get("lines"), list) or not doc["lines"]:
        raise ValueError("budget: lines missing")
    quote = doc.get("quote")
    if not isinstance(quote, str) or not quote:
        raise ValueError("budget: quote currency missing")
    if doc.get("rates_approximate") is not True:
        raise ValueError("budget: rates_approximate must be true (the page says the rates are approximate)")
    dt.date.fromisoformat(doc.get("as_of") or "")
    seen_rates = set()
    rates = {}
    for row in doc.get("rates") or []:
        cur = row.get("currency")
        if cur in seen_rates:
            raise ValueError(f"budget: duplicate rate for {cur}")
        if cur == quote:
            raise ValueError(f"budget: do not list {quote} in rates; it is already the quote currency")
        seen_rates.add(cur)
        per = _dec(row.get("per"), f"rate {cur} per")
        if per <= 0:
            raise ValueError(f"budget: rate per for {cur} must be positive")
        rates[cur] = (per, _dec(row.get("quote_amount"), f"rate {cur}"))
    ids = set()
    used = set()
    for line in doc["lines"]:
        ident = line.get("id")
        kind = line.get("kind")
        if not ident or ident in ids:
            raise ValueError(f"budget: bad or duplicate id {ident!r}")
        ids.add(ident)
        if kind not in _KINDS:
            raise ValueError(f"{ident}: unknown kind {kind!r}")
        for key in _NEED[kind]:
            if not isinstance(line.get(key), str) or not line[key].strip():
                raise ValueError(f"{ident}: missing {key}")
        if line.get("free"):
            if any(k in line for k in ("amount", "currency", "amount_year")):
                raise ValueError(f"{ident}: a free line has no amount")
            continue
        amount = _dec(line.get("amount"), ident)
        cur = line.get("currency")
        if not isinstance(cur, str) or not cur:
            raise ValueError(f"{ident}: currency missing")
        if line.get("period") != "month":
            raise ValueError(f"{ident}: amount is the monthly figure (period must be month)")
        if cur != quote and cur not in rates:
            raise ValueError(f"{ident}: no rate from {cur} to {quote}")
        used.add(cur)
        if kind == "volume":
            if line["unit_currency"] != cur:
                raise ValueError(f"{ident}: unit currency {line['unit_currency']} is not {cur}")
            expect = _dec(line["gb"], ident + " gb") * _dec(line["unit_price"], ident + " unit")
            if expect != amount:
                raise ValueError(f"{ident}: {line['gb']} × {line['unit_price']} is {expect}, not {amount}")
        if kind == "domains":
            vat = line.get("vat")
            if vat not in ("incl", "excl", None):
                raise ValueError(f"{ident}: vat must be incl, excl, or omitted")
            per_month = _dec(line["amount_year"], ident + " year") / Decimal(12)
            if per_month != amount:
                raise ValueError(f"{ident}: {line['amount_year']} / 12 is {per_month}, not {amount}")
    unused = [cur for cur in rates if cur not in used]
    if unused:
        raise ValueError("budget: unused rate for " + ", ".join(unused))


def group_amount(text):
    """Thousands grouped with a space. Fractional digits stay as written (28.60 stays 28.60)."""
    raw = str(text)
    neg = raw.startswith("-")
    body = raw[1:] if neg else raw
    whole, dot, frac = body.partition(".")
    whole = whole or "0"
    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    out = " ".join(reversed(groups))
    if dot:
        out += "." + frac
    return ("-" if neg else "") + out


_ORE = Decimal("0.01")
# Ordinary written numbers: (thousands separator, decimal separator, grouping).
# "3" groups by thousands. "indian" keeps the last three digits, then groups of two.
# Digits stay Western, the same digits as the source lines on the page.
_NUMBER = {
    "en": (",", ".", "3"),
    "zh": (",", ".", "3"),
    "ja": (",", ".", "3"),
    "hi": (",", ".", "indian"),
    "bn": (",", ".", "indian"),
    "mr": (",", ".", "indian"),
    "sw": (",", ".", "3"),
    "ar": (",", ".", "3"),
    "ur": (",", ".", "3"),
    "fa": (",", ".", "3"),
    "nn": (" ", ",", "3"),
    "nb": (" ", ",", "3"),
    "sv": (" ", ",", "3"),
    "fi": (" ", ",", "3"),
    "fr": (" ", ",", "3"),
    "ru": (" ", ",", "3"),
    "uk": (" ", ",", "3"),
    "pt": (" ", ",", "3"),
    "da": (".", ",", "3"),
    "is": (".", ",", "3"),
    "de": (".", ",", "3"),
    "es": (".", ",", "3"),
    "id": (".", ",", "3"),
}


def round_money(value):
    """Half-up to two decimal places (øre). 521.703 becomes 521.70."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_ORE, rounding=ROUND_HALF_UP)


def display_nok(subtotals):
    """Each quote-currency subtotal rounded for display, and the total readers see.

    The displayed total is the sum of the rounded parts, so the table adds up.
    """
    parts = [round_money(row["nok"]) for row in subtotals]
    return parts, sum(parts, Decimal(0))


def format_number(value, lang):
    """Two decimal places, grouped the way `lang` ordinarily writes a number."""
    value = round_money(value)
    sign = "-" if value < 0 else ""
    text = format(abs(value), "f")
    whole, frac = text.split(".")
    frac = (frac + "00")[:2]
    group, decimal, style = _NUMBER.get(lang, _NUMBER["en"])
    if style == "indian" and len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        chunks = [tail]
        while head:
            chunks.append(head[-2:])
            head = head[:-2]
        whole = group.join(reversed(chunks))
    else:
        chunks = []
        body = whole
        while body:
            chunks.append(body[-3:])
            body = body[:-3]
        whole = group.join(reversed(chunks)) or "0"
    return sign + whole + decimal + frac


def money_text(value):
    """A source-currency subtotal: at least two decimal places, further places kept."""
    if not isinstance(value, Decimal):
        value = Decimal(value)
    s = format(value, "f")
    if "." in s:
        whole, frac = s.split(".", 1)
        frac = frac.rstrip("0")
        if len(frac) < 2:
            frac = frac.ljust(2, "0")
        s = whole + "." + frac
    else:
        s = s + ".00"
    return group_amount(s)


def summary(path=None):
    """Lines, per-currency monthly subtotals, and the quote-currency total."""
    doc = load(path)
    quote = doc["quote"]
    rates = {row["currency"]: (_dec(row["per"], row["currency"]), _dec(row["quote_amount"], row["currency"])) for row in doc["rates"]}
    buckets = {}
    order = []
    for line in doc["lines"]:
        if line.get("free"):
            continue
        cur = line["currency"]
        if cur not in buckets:
            buckets[cur] = Decimal(0)
            order.append(cur)
        buckets[cur] += _dec(line["amount"], line["id"])
    subtotals = []
    total = Decimal(0)
    for cur in order:
        amount = buckets[cur]
        if cur == quote:
            nok = amount
            rate = None
            per = None
        else:
            per, rate = rates[cur]
            nok = amount * rate / per
        total += nok
        subtotals.append({"currency": cur, "amount": amount, "nok": nok, "rate": rate, "per": per})
    return {
        "as_of": dt.date.fromisoformat(doc["as_of"]),
        "quote": quote,
        "approximate": True,
        "rates": doc["rates"],
        "lines": doc["lines"],
        "subtotals": subtotals,
        "total": total,
    }


def rate_phrase(row, quote):
    """'EUR 1 = NOK 11.70' from one rate row. The caller labels the set approximate."""
    return f"{row['currency']} {group_amount(row['per'])} = {quote} {group_amount(row['quote_amount'])}"
