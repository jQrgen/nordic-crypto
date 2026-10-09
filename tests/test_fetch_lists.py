#!/usr/bin/env python3
"""Kaupr list fetching and Storting dok8 matching. No network.
python3 tests/test_fetch_lists.py
"""
import datetime as dt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


DOK8_XML = """<Innstilling>
  <Startseksjon>
    <Dato>5. oktober 2026</Dato>
    <Ingress>Representantforslag fra stortingsrepresentantene Lars Haltbrekken og Kirsti Bergstø om konsesjonssystem for etablering av datasentre</Ingress>
  </Startseksjon>
  <Hovedseksjon>
    <A>Andre sentre bidrar kun til produksjon av meningsløs kryptovaluta.</A>
  </Hovedseksjon>
</Innstilling>"""

LIST_JSON = """{"publikasjoner_liste":[
  {"id":"dok8-202627-009s","tittel":"Dokument 8:9 S (2026-2027)","dato":"/Date(-62135596800000)/","tilgjengelig_dato":"/Date(1791378178000+0200)/"},
  {"id":"dok8-202425-001s","tittel":"old","dato":"/Date(-62135596800000)/","tilgjengelig_dato":"/Date(1600000000000+0200)/"}
]}"""

PAGE = """<html><body>
<a href="/nyheter/00-old">Old</a>
<a href="/nyheter/ace-digital-tjente-6-3-millioner-kroner-i-tredje-kvartal">Ace</a>
<a href="/nyheter/zzz-ny">New</a>
<a href="/om-oss">About</a>
</body></html>"""


def test_keywords_and_outlet():
    check(any("Ace Digital" in pat for _c, pat in fetch.KW), "Ace Digital is a company keyword")
    check(any("treasury" in pat for _c, pat in fetch.KW), "bitcoin treasury is a company keyword")
    check(bool(fetch.matches("Ace Digital tjente 6,3 millioner kroner")), "Ace Digital matches")
    check(bool(fetch.matches("Et bitcoin-treasury selskap")), "hyphenated bitcoin treasury matches")
    check("companies" in fetch.topics_of("Ace Digital er et bitcoin treasury"), "company topic")
    title = "Representantforslag om konsesjonssystem for etablering av datasentre"
    check(not fetch.matches(title + ". Representantforslag 9 S (2026–2027)"), "title and blurb are not a global crypto hit")
    oid, name = fetch.outlet_for("https://www.kaupr.io/nyheter/ace-digital-tjente-6-3-millioner-kroner-i-tredje-kvartal")
    check(oid == "kaupr" and name == "Kaupr", "root Kaupr source recognises a story URL")
    st = next(s for s in fetch.CFG["sources"] if s["id"] == "stortinget")
    check(st.get("enabled") and st.get("feed") and st.get("type") == "dok8", "Stortinget is fetched as dok8")
    sections = {s["id"]: s.get("feed") for s in fetch.CFG["sources"] if s.get("outlet") == "kaupr" or s.get("id") == "kaupr"}
    check(sections.get("kaupr", "").rstrip("/").endswith("kaupr.io"), "front page is a Kaupr source")
    check("kryptoaksjer" in (sections.get("kaupr-kryptoaksjer") or ""), "kryptoaksjer section is a source")
    check("sponsor" not in (sections.get("kaupr") or "").lower(), "Kaupr feed is not described as a sponsor")


def test_dok8():
    rows = fetch.parse_dok8_list(LIST_JSON)
    check(len(rows) == 2 and rows[0]["listed_date"] is None, "list dato sentinel is not a date")
    check(rows[0]["available"] and rows[0]["available"].date().isoformat() == "2026-10-07", "availability stamp is 7 Oct")
    cutoff = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)
    due = fetch.dok8_due(rows, cutoff)
    check([r["id"] for r in due] == ["dok8-202627-009s"], "old export files stay outside the window")
    doc = fetch.parse_dok8_publication(DOK8_XML)
    check(doc["title"] == "Representantforslag om konsesjonssystem for etablering av datasentre", "short title from the ingress")
    check(doc["published"] and doc["published"].date().isoformat() == "2026-10-05", "printed date is 5 October")
    check(doc["relevant"] and "datasenter" in doc["hits"], "data centre proposal is relevant")
    check(any("krypto" in h for h in doc["hits"]), "body crypto term is a hit")
    check("kryptovaluta" not in doc["teaser"] and "meningsløs" not in doc["teaser"], "body is not stored in the teaser")
    check(not fetch.dok8_hits("CO2-avgift på mineralske produkter for 2026"), "mineralske is not mining")
    check(not fetch.dok8_hits("Representantforslag om å forby jakt på ekorn"), "unrelated proposal is dropped")
    check("mining" in fetch.dok8_hits("et midlertidig forbud mot crypto mining"), "mining is kept")
    url = fetch.dok8_url("2026-2027", "dok8-202627-009s")
    check(url == "https://www.stortinget.no/no/Saker-og-publikasjoner/Publikasjoner/Representantforslag/2026-2027/dok8-202627-009s/", "public proposal URL")
    now = dt.datetime(2026, 10, 8, tzinfo=dt.timezone.utc)
    check(fetch.storting_sessions(now, 7) == ["2026-2027"], "October look-back stays in this session")
    check(fetch.storting_sessions(dt.datetime(2026, 10, 3, tzinfo=dt.timezone.utc), 7) == ["2026-2027", "2025-2026"], "early October also reads the previous session")
    listed = fetch.dok8_list_url(fetch.SRC["stortinget"]["feed"], "2026-2027")
    check("sesjonid=2026-2027" in listed and "publikasjontype=dok8" in listed, "session is added to the export URL")


def test_link_order_and_cap():
    base = "https://www.kaupr.io/kryptoaksjer"
    links = fetch.html_story_links(PAGE, base, r"^/nyheter/")
    check(links[0].endswith("/00-old") and links[1].endswith("/ace-digital-tjente-6-3-millioner-kroner-i-tredje-kvartal"), "links stay in page order")
    check(all("/om-oss" not in u for u in links), "non-story links dropped")
    seen = set(links[:1])
    # Alphabetical cap of 1 would keep 00-old (already seen) and never reach ace.
    alpha_cap = sorted(links)[:1]
    check(not any("ace-digital" in u for u in alpha_cap), "alphabetical cap hides the new story")
    fresh = fetch.fresh_html_links(links, seen, 1)
    check(fresh == [links[1]], "cap runs after already-seen links are removed")
    many = [f"https://www.kaupr.io/nyheter/{i:02d}-old" for i in range(30)]
    many.append("https://www.kaupr.io/nyheter/ace-digital-tjente-6-3-millioner-kroner-i-tredje-kvartal")
    check("ace-digital" not in "".join(sorted(many)[:30]), "ace sits past an alphabetical 30")
    got = fetch.fresh_html_links(many, set(many[:30]), 30)
    check(any("ace-digital" in u for u in got), "unseen story past the alphabetical window is kept")


class Resp:
    def __init__(self, status, text, headers):
        self.status_code = status
        self.text = text
        self.content = (text or "").encode()
        self.headers = headers


def test_304_does_not_wipe_links():
    """Regression: a parse crash must not cache Last-Modified, and a 304 must not become zero links."""
    url = "https://www.kaupr.io/kryptoaksjer"
    html = '<html><body><a href="/nyheter/ace-digital-tjente">Ace</a><a href="/nyheter/nbx-kjoper-mer-bitcoin">NBX</a></body></html>'
    lm = "Wed, 07 Oct 2026 08:56:15 GMT"
    fetch.DELAY = 0
    fetch.http_cache.pop(url, None)
    calls = []

    def fake_get(u, headers=None, timeout=None):
        calls.append(dict(headers or {}))
        if headers and (headers.get("If-Modified-Since") or headers.get("If-None-Match")):
            return Resp(304, "", {"Last-Modified": lm})
        return Resp(200, html, {"Last-Modified": lm, "ETag": "abc"})

    orig_get = fetch.requests.get
    orig_links = fetch.html_story_links
    try:
        fetch.requests.get = fake_get

        def boom(*_a, **_k):
            raise RuntimeError("FeatureNotFound: lxml parser not found")

        fetch.html_story_links = boom
        raised = False
        try:
            fetch.read_html_links(url, r"^/nyheter/", [])
        except RuntimeError as ex:
            raised = "lxml" in str(ex)
        check(raised, "missing lxml still fails the parse")
        check(not (fetch.http_cache.get(url) or {}).get("parsed"), "failed parse does not cache Last-Modified")

        # The 7 Oct cache was written before the crash and has no parsed flag.
        fetch.http_cache[url] = {"etag": "abc", "lm": lm}
        fetch.html_story_links = orig_links
        links, err = fetch.read_html_links(url, r"^/nyheter/", [])
        check(err is None and any("ace-digital" in u for u in links), "poisoned cache is fetched again")
        check("If-Modified-Since" not in calls[-1] and "If-None-Match" not in calls[-1], "unparsed cache does not send validators")
        check(fetch.http_cache[url].get("parsed") is True, "cache is stored after a successful parse")

        saved = list(links)
        again, err2 = fetch.read_html_links(url, r"^/nyheter/", saved)
        check(err2 is None and again == saved and again != [], "304 keeps the last parsed links")
        check("If-Modified-Since" in calls[-1], "a parsed cache may send If-Modified-Since")

        # 304 with nothing saved must not be reported as an empty page.
        fetch.http_cache[url]["parsed"] = True
        calls.clear()
        recovered, err3 = fetch.read_html_links(url, r"^/nyheter/", [])
        check(err3 is None and any("ace-digital" in u for u in recovered), "304 with no saved list is refetched")
        check(len(calls) == 2 and "If-Modified-Since" not in calls[-1], "refetch omits validators")
    finally:
        fetch.requests.get = orig_get
        fetch.html_story_links = orig_links
        fetch.http_cache.pop(url, None)


def main():
    test_keywords_and_outlet()
    test_dok8()
    test_link_order_and_cap()
    test_304_does_not_wipe_links()
    if fails:
        print(f"{len(fails)} failed")
        sys.exit(1)
    print("fetch lists ok")


if __name__ == "__main__":
    main()
