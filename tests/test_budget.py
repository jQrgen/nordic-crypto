#!/usr/bin/env python3
"""Infrastructure budget page (/budget/): one data file, every site language, footer link.
No network. python3 tests/test_budget.py
"""
import os
import sys
import tempfile
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build  # noqa: E402
import i18n  # noqa: E402
import i18n.budget_strings  # noqa: E402
from tools import budget as bud  # noqa: E402
from tools.privacy_gate import RULES  # noqa: E402

fails = []
REVERSED = "Crypto " + "Nordic"
# The bill that was not taken. These must not appear as costs.
REJECTED = ("cx53", "29.49", "114.40", "2,000", "2 000", "2000 GB")


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    doc = bud.summary()
    eur = Decimal("15.99") + Decimal("28.60")
    check(eur == Decimal("44.59"), "EUR subtotal 44.59")
    check(Decimal("500") * Decimal("0.0572") == Decimal("28.60"), "500 GB × 0.0572 = 28.60")
    check(Decimal("1578") / Decimal(12) == Decimal("131.50"), "1578 / 12 = 131.50")
    total = eur * Decimal("11.70") + Decimal("5") * Decimal("10.80") + Decimal("131.50")
    check(total == Decimal("707.203"), "NOK total 707.203")
    check(doc["total"] == total, "summary total matches the stated rates")
    check(doc["as_of"].isoformat() == "2026-10-13", "as of 2026-10-13")
    check(doc["approximate"] is True, "rates labelled approximate")
    by_id = {line["id"]: line for line in doc["lines"]}
    server = by_id["hetzner-electrum-1"]
    check(server["type"] == "cx43" and server["amount"] == "15.99" and server["currency"] == "EUR", "server cx43 at 15.99 EUR")
    check(server["name"] == "electrum-1" and server["place"] == "Falkenstein", "server name and place")
    vol = by_id["hetzner-volume"]
    check(vol["gb"] == "500" and vol["unit_price"] == "0.0572" and vol["amount"] == "28.60", "volume 500 GB")
    check(by_id["cloudflare-workers"]["amount"] == "5" and by_id["cloudflare-workers"]["currency"] == "USD", "workers USD 5")
    domains = by_id["domains"]
    check(domains["amount_year"] == "1578" and domains["vat"] == "incl" and domains["amount"] == "131.50", "domains incl. VAT")
    check(domains["names"] == "nordiccrypto.no/.dk/.se/.fi/.is/.eu" and domains["vendor"] == "Domeneshop", "domain names")
    check(by_id["github-pages"].get("free") is True and by_id["cloudflare-dns"].get("free") is True, "free lines")
    rates = {r["currency"]: r["quote_amount"] for r in doc["rates"]}
    check(rates == {"EUR": "11.70", "USD": "10.80"}, "fixed rates")
    raw = open(bud.PATH, encoding="utf-8").read()
    for bad in REJECTED:
        check(bad not in raw, "data file has no " + bad)
    subs = {row["currency"]: row["amount"] for row in doc["subtotals"]}
    check(subs == {"EUR": eur, "USD": Decimal("5"), "NOK": Decimal("131.50")}, "per-currency subtotals")

    phrases = (
        "cx43", "electrum-1", "Falkenstein",
        "Electrum servers, Lightning node, Bitcoin/Nexa/BCH nodes, explorer",
        "EUR 15.99", "500", "EUR 0.0572", "EUR 28.60",
        "USD 5", "nordiccrypto.no/.dk/.se/.fi/.is/.eu", "Domeneshop",
        "NOK 1 578", "NOK 131.50", "nordiccrypto.no",
        "EUR 44.59", "EUR 1 = NOK 11.70", "USD 1 = NOK 10.80",
        "NOK 521.703", "NOK 54.00", "NOK 707.203",
    )
    old = (build.SITE, build.LANG)
    with tempfile.TemporaryDirectory() as tmp:
        build.SITE = tmp
        try:
            for lang in i18n.ALL_LANGS:
                for key in i18n.budget_strings.KEYS:
                    check(i18n.has(lang, key), f"{lang}: {key}")
                i18n.MISSING.clear()
                build.LANG = lang
                build.build_budget()
                check(not i18n.MISSING, f"{lang} no missing strings {sorted(i18n.MISSING)}")
                path = os.path.join(tmp, *([] if lang == "en" else [lang]), "budget", "index.html")
                check(os.path.exists(path), f"{lang}: budget/index.html")
                if not os.path.exists(path):
                    continue
                html = open(path, encoding="utf-8").read()
                check("{{" not in html, f"{lang}: no placeholder left")
                check(REVERSED not in html, f"{lang}: brand")
                check("Nordic Crypto" in html, f"{lang}: brand name")
                main = html.split("<main", 1)[1].split("</main>", 1)[0]
                for phrase in phrases:
                    check(phrase in main, f"{lang}: shows {phrase}")
                for bad in REJECTED:
                    check(bad not in main, f"{lang}: no {bad}")
                check(build.E(build.t("free")) in main, f"{lang}: free")
                check(main.count(build.E(build.t("free"))) == 2, f"{lang}: two free lines")
                check("budget/" in html[html.index("<footer>"):html.index("</footer>")], f"{lang}: footer link")
                if lang == "en":
                    check("as of 13 Oct 2026" in main, "English as of 13 Oct 2026")
                    check("exclude labour" in main and "updated manually" in main, "English labour note")
                    check("approximate" in main, "English approximate")
                    check(">USD 5<" in main, "USD 5 is not rewritten as 5.00 on the line")
                if lang == "ar":
                    check('dir="rtl"' in html.split("<main", 1)[0], "Arabic page is right to left")
                for name, rx in RULES.items():
                    # The built-in rules, without the private term list. URLs are not in this page's figures.
                    hit = rx.search(main)
                    check(hit is None, f"{lang}: privacy rule {name}" + (f" {hit.group(0)!r}" if hit else ""))
        finally:
            build.SITE, build.LANG = old
    print(f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
