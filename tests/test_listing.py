#!/usr/bin/env python3
"""Sitemap and HTML listing reader. No network. python3 tests/test_listing.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import listing

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset>
  <url><loc>https://barebitcoin.no/logg-inn</loc></url>
  <url><loc>https://barebitcoin.no/innsikt/nyheter/2026-08-27-hva-er-bitcoin</loc><lastmod>2026-08-27</lastmod></url>
  <url><loc>https://barebitcoin.no/produkt/app</loc></url>
</urlset>
"""

JSONLD = """<html><head>
<script type="application/ld+json">
{"@type":"NewsArticle","headline":"Bitcoin i Norge","url":"https://example.no/nyheter/2026/01/02/bitcoin","datePublished":"2026-01-02","description":"Kort om bitcoin."}
</script></head></html>"""

NEXT = """<html><script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"posts":[{"title":"Kryptovaluta og hvitvasking","url":"/blogg/2026-03-01-krypto","date":"2026-03-01"}]}}}
</script></html>"""

WP = '[{"title":{"rendered":"Rafmynt"},"link":"https://example.is/frettir/2026/04/01/rafmynt","date":"2026-04-01","excerpt":{"rendered":"<p>Stutt</p>"}}]'


def main():
    fails = []
    def check(cond, msg):
        if not cond:
            fails.append(msg)

    _, entries = listing.parse_sitemap(SITEMAP, "https://barebitcoin.no/sitemap.xml")
    picked = listing.choose(entries)
    check(len(picked) == 1 and "/innsikt/nyheter/" in picked[0]["url"], "sitemap keeps the blog post")
    check(all("/logg-inn" not in e["url"] for e in picked), "login url dropped")
    check(picked[0]["published"].date().isoformat() == "2026-08-27", "lastmod date")

    ld = listing.parse_jsonld(JSONLD, "https://example.no/")
    check(ld and ld[0]["title"] == "Bitcoin i Norge" and ld[0]["summary"].startswith("Kort"), "json-ld article")

    nxt = listing.parse_next_data(NEXT, "https://example.no/")
    check(nxt and nxt[0]["url"].endswith("/blogg/2026-03-01-krypto"), "next data post")

    wp = listing.parse_wp_posts(WP, "https://example.is/")
    check(wp and "Rafmynt" in wp[0]["title"] and "Stutt" in wp[0]["summary"], "wp posts")

    pages = {
        "https://barebitcoin.no/sitemap.xml": (200, """<sitemapindex><sitemap><loc>https://barebitcoin.no/sitemap-0.xml</loc></sitemap></sitemapindex>"""),
        "https://barebitcoin.no/sitemap-0.xml": (200, SITEMAP),
    }
    def get(url):
        return pages.get(url, (404, ""))
    rows, method, err = listing.collect("https://barebitcoin.no", get, lambda url: True)
    check(method == "sitemap" and rows and "/innsikt/" in rows[0]["url"] and err is None, "collect follows the sitemap index")

    titled = {
        "https://example.no/sitemap.xml": (200, """<urlset><url><loc>https://example.no/nyheter/2026-01-02-bitcoin</loc></url></urlset>"""),
        "https://example.no/": (200, JSONLD.replace("https://example.no/nyheter/2026/01/02/bitcoin", "https://example.no/nyheter/2026-01-02-bitcoin")),
    }
    rows, method, err = listing.collect("https://example.no/", lambda u: titled.get(u, (404, "")), lambda url: True)
    check(method == "sitemap" and rows and rows[0]["title"] == "Bitcoin i Norge" and rows[0]["summary"].startswith("Kort"), "index page fills a sitemap title")

    blocked = {"https://barebitcoin.no/sitemap.xml": (200, SITEMAP)}
    rows, method, err = listing.collect("https://barebitcoin.no", lambda u: blocked.get(u, (404, "")), lambda url: False)
    check(rows == [] and method == "", "robots stop the reader")

    sources = [
        {"id": "barebitcoin", "type": "rss", "enabled": False, "feed": None, "url": "https://barebitcoin.no",
         "status": "no RSS found (/feed returns 404)"},
        {"id": "e24", "type": "rss", "enabled": True, "feed": "https://e24.no/rss2/", "url": "https://e24.no", "status": "ok"},
        {"id": "kaupr-no", "type": "html", "enabled": True, "feed": "https://www.kaupr.io/norge", "link_pattern": "/norge/",
         "url": "https://www.kaupr.io", "status": "ok (no RSS; we read the link list)"},
        {"id": "politiet", "type": "search", "enabled": False, "feed": None, "url": "https://www.politiet.no",
         "status": "No working RSS; robots.txt disallows the feed"},
        {"id": "vb", "type": "rss", "enabled": False, "feed": None, "url": "https://www.vb.no", "status": "blocked: HTTP 403"},
    ]
    changed = listing.apply_listing_sources(sources)
    by = {s["id"]: s for s in sources}
    check(changed == ["barebitcoin"], "only the no-rss source is switched on")
    check(by["barebitcoin"]["enabled"] is True and by["barebitcoin"]["method"] == "sitemap", "bare bitcoin sitemap")
    check(by["barebitcoin"]["feed"] == "https://barebitcoin.no/sitemap.xml", "bare bitcoin feed")
    check(by["barebitcoin"]["type"] == "sitemap", "bare bitcoin type")
    check(by["e24"]["method"] == "rss" and by["e24"]["feed"] == "https://e24.no/rss2/", "working rss stays rss")
    check(by["kaupr-no"]["method"] == "html" and by["kaupr-no"]["type"] == "html", "kaupr stays an html list")
    check(by["politiet"]["enabled"] is False and by["politiet"]["feed"] is None and by["politiet"]["method"] == "manual", "robots source stays manual")
    check(by["vb"]["enabled"] is False and by["vb"]["method"] == "manual", "blocked source stays off")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("listing ok")

if __name__ == "__main__":
    main()
