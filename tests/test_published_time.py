#!/usr/bin/env python3
"""Publish-time order and Nordic timezone parsing. No network."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import published_time as pub

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


PAGE = """
<html><head>
<meta property="article:modified_time" content="2026-10-06T01:49:36+00:00">
<meta property="article:published_time" content="2026-10-05T15:06:17+02:00">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"NewsArticle",
 "datePublished":"2026-10-04T08:35:00+00:00",
 "dateModified":"2026-10-06T01:49:36+00:00"}
</script>
</head><body>
<time itemprop="dateModified" datetime="2026-10-06T01:49:36+00:00"></time>
<time datetime="2026-10-03T12:00:00+00:00"></time>
</body></html>
"""

JSONLD_ONLY = """
<html><head>
<script type="application/ld+json">
{"@type":"NewsArticle","dateModified":"2026-10-06T01:00:00Z","datePublished":"2026-10-05T03:35:00+00:00"}
</script>
<script type="application/ld+json">
{"@type":"Comment","datePublished":"2026-10-01T00:00:00Z"}
</script>
</head><body>
<time datetime="2026-10-03T12:00:00Z"></time>
</body></html>
"""

TIME_ONLY = """
<html><body>
<time itemprop="dateModified" datetime="2026-10-06T01:00:00Z"></time>
<time itemprop="datePublished" datetime="2026-10-02T12:00:00Z">2 oktober 2026 14:00</time>
</body></html>
"""

MODIFIED_ONLY = """
<html><head>
<meta property="article:modified_time" content="2026-10-06T01:00:00Z">
<script type="application/ld+json">{"@type":"NewsArticle","dateModified":"2026-10-06T01:00:00Z"}</script>
</head><body>
<time itemprop="dateModified" datetime="2026-10-06T01:00:00Z"></time>
</body></html>
"""

DN = """
<html><head>
<meta name="article:modified_time" content="2026-10-01T10:10:05Z">
<meta name="article:published_time" content="2026-09-30T17:52:24Z">
<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-09-29T00:00:00Z"}</script>
</head></html>
"""


def main():
    page = pub.published_from_html(PAGE, "Europe/Oslo")
    feed = pub.from_feed_entry({
        "published": "2026-10-05T06:06:00Z",
        "updated": "2026-10-06T01:49:36Z",
        "updated_parsed": (2026, 10, 6, 1, 49, 36, 0, 0, 0),
    })
    chosen = pub.choose_published(page, feed)
    check(page and page.source == "article:published_time", "article:published_time is first")
    check(pub.utc_iso(chosen) == "2026-10-05T13:06:17+00:00", "page offset wins over JSON-LD, time and feed")

    page = pub.published_from_html(JSONLD_ONLY, "Europe/Oslo")
    check(page and page.source == "jsonld", "JSON-LD datePublished is second")
    check(pub.utc_iso(page) == "2026-10-05T03:35:00+00:00", "dateModified and comments are ignored")
    check(pub.utc_iso(pub.choose_published(page, feed)) == "2026-10-05T03:35:00+00:00", "JSON-LD wins over the feed")

    page = pub.published_from_html(TIME_ONLY, "Europe/Stockholm")
    check(page and page.source == "time", "<time datetime> is third")
    check(pub.utc_iso(page) == "2026-10-02T12:00:00+00:00", "dateModified time element is skipped")
    check(pub.utc_iso(pub.choose_published(page, feed)) == "2026-10-02T12:00:00+00:00", "time element wins over the feed")

    check(pub.published_from_html(MODIFIED_ONLY, "Europe/Oslo") is None, "modified/updated alone is not a publish time")
    check(pub.from_feed_entry({"updated": "2026-10-06T01:00:00Z", "updated_parsed": (2026, 10, 6, 1, 0, 0, 0, 0, 0)}) is None,
          "feed updated time is not used")
    check(pub.utc_iso(pub.choose_published(None, feed)) == "2026-10-05T06:06:00+00:00", "feed published is the last resort")

    dn = pub.published_from_html(DN, "Europe/Oslo")
    check(dn and dn.source == "article:published_time" and pub.utc_iso(dn) == "2026-09-30T17:52:24+00:00",
          "name=article:published_time counts and beats JSON-LD")

    check(pub.utc_iso(pub.parse_instant("2026-07-01T15:06:00", "Europe/Oslo")) == "2026-07-01T13:06:00+00:00",
          "Oslo summer time is UTC+2")
    check(pub.utc_iso(pub.parse_instant("2026-01-15T15:06:00", "Europe/Oslo")) == "2026-01-15T14:06:00+00:00",
          "Oslo winter time is UTC+1")
    check(pub.utc_iso(pub.parse_instant("2026-10-05T15:06:17", "Europe/Oslo")) == "2026-10-05T13:06:17+00:00",
          "5 October is still Oslo daylight time")
    check(pub.utc_iso(pub.parse_instant("2026-10-26T15:06:00", "Europe/Oslo")) == "2026-10-26T14:06:00+00:00",
          "26 October is Oslo standard time")
    check(pub.utc_iso(pub.parse_instant("2026-07-01T15:06:00", "Europe/Stockholm")) == "2026-07-01T13:06:00+00:00",
          "Stockholm summer time is UTC+2")
    check(pub.utc_iso(pub.parse_instant("2026-01-15T15:06:00", "Europe/Stockholm")) == "2026-01-15T14:06:00+00:00",
          "Stockholm winter time is UTC+1")
    check(pub.utc_iso(pub.parse_instant("2026-10-26T15:06:00", "Europe/Stockholm")) == "2026-10-26T14:06:00+00:00",
          "26 October is Stockholm standard time")
    check(pub.utc_iso(pub.parse_instant("2026-10-05T15:06:17+02:00", "Europe/Stockholm")) == "2026-10-05T13:06:17+00:00",
          "an explicit offset is converted, not reinterpreted")
    check(pub.utc_iso(pub.parse_instant("2026-07-01T15:06:00", "Europe/Helsinki")) == "2026-07-01T12:06:00+00:00",
          "Helsinki summer time is UTC+3")

    day = pub.parse_instant("2026-10-01", "Europe/Stockholm")
    same_day = pub.from_feed_entry({"published": "2026-10-01T06:00:11Z"})
    check(pub.utc_iso(pub.choose_published(day, same_day)) == "2026-10-01T06:00:11+00:00",
          "a date-only page keeps the feed clock time on that day")
    other = pub.from_feed_entry({"published": "2026-10-04T08:35:00Z"})
    check(pub.utc_iso(pub.choose_published(pub.parse_instant("2026-10-05", "Europe/Oslo"), other)) == "2026-10-05T12:00:00+00:00",
          "a date-only page replaces a feed time on another day")

    check(pub.zone_for(country="NO", url="https://www.sydsvenskan.se/lund/x") == "Europe/Stockholm",
          "the article host picks the zone")
    check(pub.zone_for(country="SE", url="https://www.finansavisen.no/valuta/x") == "Europe/Oslo",
          "a Norwegian host is Europe/Oslo")

    if fails:
        print(f"{len(fails)} failed")
        sys.exit(1)
    print("all ok")


if __name__ == "__main__":
    main()
