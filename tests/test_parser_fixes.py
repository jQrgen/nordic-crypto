#!/usr/bin/env python3
"""Fetcher fixes from the 2026-10-13 source check: nav titles, tag pages, Nordic wire filter,
language detection, date-only times, cross-language duplicates, sitemap/RSS discovery."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
import coverage, listing  # noqa: E402
import fetch  # noqa: E402

fails = []
def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)

FEBER = "Teknik Motor Samhälle Spel Popkultur Fritid Tjock Tester Dagens fråga Tipsa! Skaffa Feber+ Mitt konto Logga ut"
check(fetch.looks_like_nav(FEBER), "Feber side menu is not a headline")
check(not fetch.looks_like_nav("Moddade kryptoplånböcker tros ha lett till miljonstölder"), "real headline kept")
check(not fetch.looks_like_nav("Hot om GTA 6-läcka: CyberLeek kräver miljoner i krypto"), "headline with names kept")
html = '<html><head><meta property="og:title" content="Moddade kryptoplånböcker tros ha lett till miljonstölder"></head><body><h1>x</h1></body></html>'
check(fetch.title_from_html(html) == "Moddade kryptoplånböcker tros ha lett till miljonstölder", "og:title replaces the menu")

check(fetch.is_listing_url("https://dagensps.se/tag/kryptovaluta/"), "Dagens PS tag page is not an article")
check(not fetch.is_listing_url("https://dagensps.se/bors-finans/manipulation-kryptoplanbocker-tomdes-pa-860-miljoner"), "article URL kept")
check(not fetch.is_listing_url("https://www.aamuposti.fi/aihe/Nurmijärvi/uutinen-123"), "section path article kept")

check(not fetch.NORDIC_TERMS.search("Crypto Weekly: EU investigates Binance, Greece could tax crypto gains. Sam Altman on AI"), "Reuters video has no Nordic angle")
check(bool(fetch.NORDIC_TERMS.search("Norway's wealth fund raises bitcoin exposure")), "Nordic wire story passes")

check(fetch.detect_language("Ten Movements Where Old and New Finance Collide. Bitcoin has become a mainstream portfolio asset, exchanges on both sides are tokenising each other's turf", "Norwegian") == "English", "Kaupr English write-up is English")
check(fetch.detect_language("Spillpioner og kapitalforvalter satser sammen på tokenisering. NUVA er en markedsplass for tokeniserte eiendeler", "Norwegian") == "Norwegian", "Norwegian stays Norwegian")

def story(**kw):
    base = {"id": "a", "status": "pending", "url": "https://gamereactor.dk/gta-6-laek", "title": "GTA 6 i fare: Hackere truer med at lække hele spillet",
            "published": "2026-10-12T20:24:52+00:00", "country": "DK", "language": "Danish"}
    base.update(kw); return base
se = {"url": "https://gamereactor.se/hot-om-gta-6-lacka", "title": "Hot om GTA 6-läcka: CyberLeek kräver miljoner i krypto",
      "published": "2026-10-12T20:24:02+00:00", "text": "Hot om GTA 6-läcka: CyberLeek kräver miljoner i krypto. CyberLeek hotar att läcka hela Grand Theft Auto 6 om deras kryptovaluta når 30 miljoner dollar."}
hit, why = coverage.find_match(se, [story()])
check(hit is not None and "network" in why, "Gamereactor language editions attach")
fi_other = {"url": "https://www.is.fi/x", "title": "GTA 6 -vuotaja uhkaa julkaista koko pelin",
            "published": "2026-10-12T20:00:00+00:00", "text": "CyberLeek uhkaa julkaista GTA 6 -pelin täyden version, jos sen kryptovaluutta saavuttaa 30 miljoonan dollarin arvon."}
dk = story(url="https://www.bt.dk/x", title="GTA 6 i fare", )
hit, why = coverage.find_match(fi_other, [dict(dk, summary="CyberLeek truer med at lække GTA 6, hvis kryptovaluta når 30 mio. dollars.")])
check(hit is not None and why == "same names and figures", "names and figures across languages")
diff = {"url": "https://x.no/b", "title": "Kvarn avviser at Goobit-avtalen er agentforhold", "published": "2026-10-12T10:00:00+00:00",
        "text": "Kvarn avviser at Goobit-avtalen er agentforhold. MiCA"}
check(coverage.find_match(diff, [story(url="https://y.no/a", title="Finske Kvarn leier ut MiCA-tillatelsen sin", summary="Kvarn MiCA", country="NO")])[0] is None, "related but different story is not attached")

imf_old = story(id="inv", url="https://investornytt.no/nyheter/aksjer/1", title="Aksjer på blokkjeden kan forsterke børsuro",
                published="2026-10-09T09:28:58+00:00", country="NO", language="Norwegian",
                summary="Døgnet rundt-handel frister, men IMF finner svakere likviditet")
imf_new = {"url": "https://finanswatch.no/nyheter/fintech/article1.ece", "title": "IMF ser stort potensial i tokenisering",
           "published": "2026-10-09T08:08:31+00:00", "country": "NO", "language": "Norwegian", "text": "IMF ser stort potensial i tokenisering"}
hit, why = coverage.suggest_match(imf_new, [imf_old])
check(hit is not None and hit["id"] == "inv", "IMF pair suggested to the editor")
ledger_old = story(id="dps", url="https://dagensps.se/a", title="Manipulation: Kryptoplånböcker tömdes på 860 miljoner",
                   published="2026-10-11T07:23:27+00:00", country="SE", language="Swedish")
ledger_new = {"url": "https://feber.se/b", "title": "Moddade kryptoplånböcker tros ha lett till miljonstölder",
              "published": "2026-10-12T07:42:00+00:00", "country": "SE", "language": "Swedish", "text": "x"}
hit, why = coverage.suggest_match(ledger_new, [ledger_old])
check(hit is not None and hit["id"] == "dps", "Ledger pair suggested to the editor")

robots = "User-agent: *\nSitemap: https://a.fi/sitemap/html/al/sitemapindex.xml\nSitemap: https://a.fi/rss/custom/news-sitemap.xml\n"
check(listing.robots_sitemaps(robots)[0].endswith("news-sitemap.xml"), "robots.txt news sitemap first")
page = '<link rel="alternate" type="application/rss+xml" href="/feed/?a=1&amp;b=2"><link rel="alternate" type="application/rss+xml" href="/comments/feed/">'
check(listing.feed_links(page, "https://b.dk/") == ["https://b.dk/feed/?a=1&b=2"], "RSS discovery from the homepage")
rss = '<rss><channel><item><title>Krypto i Kautokeino</title><link>https://b.dk/n/1</link><pubDate>Mon, 12 Oct 2026 09:38:00 GMT</pubDate></item></channel></rss>'
calls = []
def get(u):
    calls.append(u)
    if u == "https://b.dk/": return 200, page
    if u.startswith("https://b.dk/feed/"): return 200, rss
    return 404, ""
entries, method, err = listing.collect("https://b.dk/", get, lambda u: True, limit=5)
check(method == "rss" and entries and entries[0]["title"] == "Krypto i Kautokeino", "listing falls back to the discovered feed")

if fails:
    print(f"{len(fails)} failed"); sys.exit(1)
