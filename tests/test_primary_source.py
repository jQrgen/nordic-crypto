#!/usr/bin/env python3
"""Editor primary-source link on the card, the story page, the public JSON and the API."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import api_feed
import build
import coverage
import i18n

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


ITEM = {
    "id": "cite12345678",
    "url": "https://www.aftenposten.no/okonomi/i/krypto",
    "title": "Finanstilsynet om krypto",
    "source": "aftenposten",
    "source_name": "Aftenposten",
    "country": "NO",
    "language": "Norwegian",
    "published": "2026-10-05T13:06:17+00:00",
    "summary": "The regulator published a notice about crypto service providers.",
    "status": "published",
    "topics": ["regulation"],
    "primary_source": {
        "name": "Finanstilsynet",
        "url": "https://www.finanstilsynet.no/nyheter/2026/krypto-casp",
    },
}


def main():
    doc = coverage.editor_primary_source(ITEM["primary_source"])
    check(doc == {"name": "Finanstilsynet", "url": ITEM["primary_source"]["url"]}, "document kept")
    check(coverage.editor_primary_source({"outlet": "aftenposten", "outlet_name": "Aftenposten"}) is None,
          "a coverage row without a document url is not a citation")
    bare = coverage.editor_primary_source("https://www.finanstilsynet.no/nyheter/2026/krypto-casp")
    check(bare and bare["name"] == "finanstilsynet.no", "a bare url uses the host")

    extra = build.public_extra(ITEM)
    check(extra.get("primary_source") == doc, "public json keeps the document")
    check("published_unverified" not in extra, "verified story has no flag")
    flagged = dict(ITEM, published_unverified=True)
    check(build.public_extra(flagged).get("published_unverified") is True, "unverified flag is public")

    for lang in i18n.ALL_LANGS:
        check(i18n.has(lang, "primary_source") and i18n.t(lang, "primary_source"), "label " + lang)

    rule = build.CSS.split(".primary-src{")[1].split("}")[0]
    check("text-align:start" in rule and "text-align:center" not in rule and "justify-content:center" not in rule,
          "primary source line is start aligned")

    build.PREVIEW = False
    with tempfile.TemporaryDirectory() as tmp:
        build.SITE = tmp
        build.LANG = "en"
        card = build.front_card(ITEM, {}, "", lead=False)
        check('class="primary-src"' in card and "Primary source" in card, "english card label")
        check("https://www.finanstilsynet.no/nyheter/2026/krypto-casp" in card, "card links the document")
        check("text-align:center" not in card, "card is not centered")
        build.LANG = "nn"
        card_nn = build.front_card(ITEM, {}, "", lead=False)
        check("Primærkjelde" in card_nn, "nynorsk card label")
        build.LANG = "sv"
        check("Primärkälla" in build.front_card(ITEM, {}, "", lead=False), "swedish card label")
        build.LANG = "en"
        build.build_coverage_pages([ITEM], {})
        page = open(os.path.join(tmp, "stories", ITEM["id"], "index.html"), encoding="utf-8").read()
        check("Primary source" in page and "finanstilsynet.no/nyheter/2026/krypto-casp" in page, "story page link")
        article = page.split("<article", 1)[1].split("</article>", 1)[0]
        check("text-align:center" not in article and 'class="primary-src"' in article, "story link is not centered")

    feed = api_feed.Feed(tempfile.gettempdir(), False, "https://nordiccrypto.example/")
    out = feed.news_item(ITEM)
    check((out.get("primary_source") or {}).get("outlet") == "aftenposten", "api outlet stays the lead")
    check((out.get("primary_source_document") or {}).get("url") == ITEM["primary_source"]["url"], "api document")
    check((out.get("primary_source_document") or {}).get("name") == "Finanstilsynet", "api document name")

    if fails:
        print(f"{len(fails)} failed")
        sys.exit(1)
    print("primary source ok")


if __name__ == "__main__":
    main()
