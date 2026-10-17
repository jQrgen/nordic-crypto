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
REJECTED = ("cx53", "29.49", "114.40", "2,000", "2 000", "2000 GB", "cx43", "15.99", "85.80", "1500 GB")


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    doc = bud.summary()
    eur = Decimal("8.99") + Decimal("28.60") + Decimal("8.99")
    check(eur == Decimal("46.58"), "EUR subtotal 46.58")
    check(Decimal("8.49") + Decimal("0.50") == Decimal("8.99"), "8.49 + 0.50 = 8.99")
    check(Decimal("500") * Decimal("0.0572") == Decimal("28.60"), "500 GB × 0.0572 = 28.60")
    check(Decimal("1578") / Decimal(12) == Decimal("131.50"), "1578 / 12 = 131.50")
    total = eur * Decimal("11.70") + Decimal("5") * Decimal("10.80") + Decimal("131.50")
    check(total == Decimal("730.486"), "exact NOK total 730.486")
    check(doc["total"] == total, "summary total matches the stated rates")
    parts, shown = bud.display_nok(doc["subtotals"])
    check(parts == [Decimal("544.99"), Decimal("54.00"), Decimal("131.50")], "display parts rounded half-up to øre")
    check(shown == Decimal("730.49") and shown == sum(parts, Decimal(0)), "displayed total is the sum of the rounded parts")
    check(bud.format_number(total, "en") == "730.49", "English number 730.49")
    check(bud.format_number(total, "nn") == "730,49", "Nynorsk number 730,49")
    check(bud.format_number(total, "nb") == "730,49", "Bokmål number 730,49")
    check(bud.format_number(Decimal("1234.5"), "nn") == "1 234,50", "Nynorsk groups thousands with a space")
    check(bud.format_number(Decimal("1234.5"), "da") == "1.234,50", "Danish groups thousands with a dot")
    check(bud.format_number(Decimal("1234.5"), "de") == "1.234,50", "German groups thousands with a dot")
    check(bud.format_number(Decimal("1234.5"), "fr") == "1 234,50", "French groups thousands with a space")
    check(bud.format_number(Decimal("1234.5"), "en") == "1,234.50", "English groups thousands with a comma")
    check(bud.format_number(Decimal("1234567.895"), "hi") == "12,34,567.90", "Hindi grouping, half-up")
    check(bud.format_number(Decimal("1.225"), "en") == "1.23", "half-up at the third decimal")
    check(bud.round_money(Decimal("521.703")) == Decimal("521.70"), "521.703 rounds to 521.70")
    check(set(bud._NUMBER) == set(i18n.ALL_LANGS), "a number format for every site language")
    check(doc["as_of"].isoformat() == "2026-10-17", "as of 2026-10-17")
    check(doc["approximate"] is True, "rates labelled approximate")
    by_id = {line["id"]: line for line in doc["lines"]}
    server = by_id["hetzner-electrum-1"]
    check(server["type"] == "cx33" and server["amount"] == "8.99" and server["currency"] == "EUR", "server cx33 at 8.99 EUR")
    check(server["amount_server"] == "8.49" and server["amount_ipv4"] == "0.50", "electrum-1 is 8.49 plus 0.50 for the primary IPv4")
    check("Bitcoin/" not in server["runs"], "electrum-1 no longer runs a Bitcoin node")
    check(server["name"] == "electrum-1" and server["place"] == "Falkenstein", "server name and place")
    pool = by_id["hetzner-nexa-pool-1"]
    check(pool["type"] == "cx33" and pool["amount"] == "8.99" and pool["currency"] == "EUR", "server cx33 at 8.99 EUR")
    check(pool["name"] == "nexa-pool-1" and pool["place"] == "Falkenstein", "nexa-pool-1 name and place")
    check(pool["runs"] == "a Nexa full node for the upcoming Nordic Crypto mining pool", "nexa-pool-1 runs a Nexa full node")
    check(pool["amount_server"] == "8.49" and pool["amount_ipv4"] == "0.50", "cx33 is 8.49 plus 0.50 for the primary IPv4")
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
        "cx33", "electrum-1", "Falkenstein",
        "Electrum servers, Lightning node, Nexa/BCH nodes, explorer",
        "cx33", "nexa-pool-1",
        "a Nexa full node for the upcoming Nordic Crypto mining pool",
        "EUR 8.99", "EUR 8.49", "EUR 0.50",
        "EUR 0.0572", "EUR 28.60",
        "USD 5", "nordiccrypto.no/.dk/.se/.fi/.is/.eu", "Domeneshop",
        "NOK 1 578", "NOK 131.50", "nordiccrypto.no",
        "EUR 46.58", "EUR 1 = NOK 11.70", "USD 1 = NOK 10.80",
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
                title = build.E(build.t("bud_server", name="nexa-pool-1", type="cx33", place="Falkenstein"))
                runs = build.E(build.t("bud_runs", what=pool["runs"]))
                split = build.E(build.t("bud_server_split", server="EUR 8.49", ipv4="EUR 0.50"))
                check(title in main, f"{lang}: translated server line")
                check(runs in main, f"{lang}: translated runs line")
                check(split in main, f"{lang}: translated price split")
                for value in list(parts) + [shown]:
                    label = i18n.budget_strings.S[lang]["bud_nok_amt"].format(n=bud.format_number(value, lang))
                    check(label in main, f"{lang}: shows {label}")
                check("730.486" not in main and "544.986" not in main, f"{lang}: no unrounded total")
                for bad in REJECTED:
                    check(bad not in main, f"{lang}: no {bad}")
                check(build.E(build.t("free")) in main, f"{lang}: free")
                check(main.count(build.E(build.t("free"))) == 2, f"{lang}: two free lines")
                check("budget/" in html[html.index("<footer>"):html.index("</footer>")], f"{lang}: footer link")
                if lang == "en":
                    check("as of 17 Oct 2026" in main, "English as of 17 Oct 2026")
                    check("exclude labour" in main and "updated manually" in main, "English labour note")
                    check("approximate" in main, "English approximate")
                    check(">USD 5<" in main, "USD 5 is not rewritten as 5.00 on the line")
                    check("About NOK 730.49 per month." in main, "English total line")
                    check("EUR 8.49 for the server plus EUR 0.50 for the primary IPv4." in main, "English price split")
                if lang == "nn":
                    check("Om lag 730,49 kr i månaden." in main, "Nynorsk total line")
                if lang == "nb":
                    check("Omtrent 730,49 kr i måneden." in main, "Bokmål total line")
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
