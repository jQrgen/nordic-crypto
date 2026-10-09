#!/usr/bin/env python3
"""Event NFT prototype: public facts only, placeholder treasury, flag off by default.
   python3 tests/test_event_nft.py"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)

import event_nft
import i18n

os.environ.pop("NC_EVENT_NFT", None)


def fail(msg):
    print("FAIL", msg, file=sys.stderr)
    sys.exit(1)


def main():
    if event_nft.enabled():
        fail("flag must be off when NC_EVENT_NFT is unset and approved.json has no features.event_nft")
    if event_nft.mint_blocks({"id": "x"}, "upcoming", "./", "./", lambda k, **kw: k, lambda s: s):
        fail("mint block must be empty while the flag is off")

    if event_nft.judge(25000, 5000, 8000, 1020) != "ok":
        fail("funded treasury")
    if event_nft.judge(6000, 5000, 8000, 1020) != "low":
        fail("low treasury")
    if event_nft.judge(4000, 5000, 8000, 1020) != "empty":
        fail("under the floor")
    if event_nft.judge(100, 5000, 8000, 1020) != "empty":
        fail("cannot pay a mint")

    doc = event_nft.treasury_document("https://nordiccrypto.no/treasury/")
    if doc["nexa"]["address"] != event_nft.PLACEHOLDER_NEXA or not doc["nexa"]["address_placeholder"]:
        fail("nexa address must stay a placeholder")
    if doc["bch"]["address"] != event_nft.PLACEHOLDER_BCH:
        fail("bch address must stay a placeholder")
    if doc["needs_funding"] or doc["app_prompt"]["show"]:
        fail("sample fixture is funded, so the app prompt stays off")
    if doc["nexa"]["hot_balance_target"]["amount"] != 50000 or doc["bch"]["hot_balance_target"]["amount"] != 200000:
        fail("hot balance targets must come from mintworker/caps.json")
    if doc["nexa"]["per_event"] != 20 or doc["nexa"]["per_day"] != 15:
        fail("nexa mint caps")
    if doc["bch"]["per_event"] != 8 or doc["bch"]["per_day"] != 6:
        fail("bch mint caps")
    if not doc["intentionally_small"] or doc["nexa"]["refill_address"] != doc["nexa"]["address"]:
        fail("refill address is the hot wallet, and the wallet is intentionally small")
    if doc["nexa"]["above_target"] or doc["bch"]["above_target"]:
        fail("sample balances sit under the hot target")
    blob_doc = json.dumps(doc).lower()
    if "private" in blob_doc or "nexaid" in blob_doc or "secret" in blob_doc:
        fail("treasury document leaked an identity field")
    if "do-not-publish" in blob_doc or any(row.get("from") or row.get("name") for row in doc["history"]):
        fail("history leaked a sender")
    if doc["nexa"]["balance"]["amount"] != doc["balance_series"]["nexa"][-1]["amount"]:
        fail("nexa series must end at the sample balance")
    if doc["bch"]["balance"]["amount"] != doc["balance_series"]["bch"][-1]["amount"]:
        fail("bch series must end at the sample balance")
    kinds = {row["kind"] for row in doc["history"]}
    if kinds != {"refill", "mint"}:
        fail("history must list refills and mints")
    if not all(str(row["explorer_url"]).startswith("https://") for row in doc["history"]):
        fail("each history row needs an explorer link")
    hist = event_nft.history_document()
    if hist["history"] != doc["history"] or "nexa" not in hist["balance_series"]:
        fail("history endpoint")
    page = event_nft.treasury_body(doc, "./", lambda k, **kw: i18n.t("en", k, **kw), lambda s: str(s))
    if "<table" not in page or "<svg" not in page or 'class="trehist"' not in page:
        fail("treasury page needs the history table and the chart")
    if "do-not-publish" in page or "text-align:start" not in event_nft.style():
        fail("history layout or a sender on the page")

    ev = next(e for e in json.load(open("data/events.json", encoding="utf-8"))["events"] if e["id"] == "89ced460e4ca")
    urls = event_nft.media_urls("https://nordiccrypto.no", ev["id"], "ongoing", "nexa")
    meta = event_nft.nexa_metadata(ev, "ongoing", urls)
    blob = json.dumps(meta).lower()
    for banned in ("nexaid", "email", "@", "attendee", "handle"):
        if banned in blob:
            fail("public metadata contains " + banned)
    for key in ("niftyVer", "title", "series", "author", "info", "license"):
        if key not in meta:
            fail("missing Wally field " + key)
    if "I was there" not in meta["series"] or "not stated" not in meta["info"]:
        fail("ongoing card should describe the event and an absent count")
    pre = event_nft.nexa_metadata(ev, "pre", urls)
    if "I'm going" not in pre["series"]:
        fail("pre-event series")
    bch = event_nft.bch_metadata(ev, "pre", urls)
    if len(bch["commitment_hex"]) != 64:
        fail("commitment should be a sha256 hex string")
    if "address" in bch["data"]:
        fail("bch facts must not carry an address")

    os.environ["NC_EVENT_NFT"] = "1"
    raw = event_nft.load_fixture()
    raw["nexa"]["balance_nex"] = 10
    real_load = event_nft.load_fixture
    event_nft.load_fixture = lambda: raw
    try:
        def tr(key, **kw):
            return i18n.t("en", key, **kw)
        html = event_nft.mint_blocks(ev, "ongoing", "./", "./", tr, lambda s: str(s))
    finally:
        event_nft.load_fixture = real_load
        os.environ.pop("NC_EVENT_NFT", None)
    if "Treasury empty, fund it" not in html:
        fail("empty nexa treasury should replace the mint button")
    if "Mint event NFT on Bitcoin Cash" not in html:
        fail("funded bch chain should keep its mint button")
    if "placeholder" in html and "nqtsq5" in html:
        fail("a real-looking nexa address leaked into the card")

    img = event_nft.render_card(ev, "ongoing", "nexa", "front")
    if img.size != (640, 640):
        fail("card size")
    print("event nft: OK")


if __name__ == "__main__":
    main()
