#!/usr/bin/env python3
"""Keyword filter and dead-feed isolation. Does not import a live news run.
python3 tests/test_fetch_filter.py
"""
import os, sys, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch

def main():
    fails = []
    def check(cond, msg):
        if not cond:
            fails.append(msg)
    samples = [
        "Ny rapport om kryptovaluta",
        "Kryptovaluutta ja lohkoketju",
        "Rafmyntir og peningaþvætti",
        "Hvidvask via darknet",
        "Penningtvätt på mörka nätet",
        "Hvitvasking og bitcoin",
        "Rahanpesu ja virtuaalivaluutta",
    ]
    for text in samples:
        if not fetch.matches(text):
            fails.append("no keyword hit: " + text)
    check(not fetch.matches("Værmelding for Bergen i morgen"), "weather is not crypto")
    for text in (
        "Politiet etterforsker hvitvasking i Oslo",
        "Penningtvätt i stor skala i Stockholm",
        "Hvidvask sag i København",
        "Rahanpesu ja järjestäytynyt rikollisuus",
        "Rannsókn á peningaþvætti",
        "Penningtvatt i Stockholm",
    ):
        check(not fetch.matches(text), "aml alone is not crypto: " + text)
    check(fetch.matches("CASP og hvitvasking"), "casp unlocks hvitvasking")
    check(fetch.matches("Ny CASP-tillatelse"), "casp alone")
    check(fetch.matches("Hvitvasking og kryptoeiendel", ("kryptoeiendel",)), "crypto extra unlocks aml")
    check(not fetch.matches("Hvitvasking i banken", ("hvitvasking",)), "aml extra does not unlock itself")
    check(fetch.matches("En sak om darknet"), "darknet still counts alone")

    url = "https://www.finansavisen.no/valuta/2026/10/05/8385368/smasparere-hamstret-krypto-under-renteuro"
    check(fetch.iid(url) == "fb9e8ca4fb40", "finansavisen id stays fb9e8ca4fb40")
    stored = "https://finansavisen.no/valuta/2026/10/05/8385368/smasparere-hamstret-krypto-under-renteuro"
    items = [{"id": "fb9e8ca4fb40", "url": stored, "title": "Småsparere"}]
    wrapped = "https://www.bing.com/news/apiclick.aspx?url=" + urllib.parse.quote(url + "?utm_source=bing&fbclid=abc")
    check(fetch.is_duplicate(wrapped, items), "bing wrapper is the stored story")
    check(fetch.is_duplicate(url + "?utm_campaign=nightly", items), "tracking query is the stored story")
    check(not fetch.is_duplicate(url.replace("8385368", "9999999"), items), "another article is not a duplicate")

    oid, name = fetch.outlet_for("https://www.tv2kosmopol.dk/nyheder/krypto")
    check(oid == "tv2-lorry" and name == "TV 2 Kosmopol", "tv2 kosmopol name")
    oid, name = fetch.outlet_for("https://www.aamuposti.fi/uutiset/rahanpesu")
    check(oid == "aamuposti" and name == "Aamuposti", "aamuposti host")
    oid, name = fetch.outlet_for("https://www.aamuposti.fi/aihe/Nurmij%C3%A4rvi/juttu")
    check(oid == "aamuposti" and name == "Aamuposti", "nurmijarvi section stays aamuposti")

    oa = """<html><head>
<meta property="og:description" content="Politiet i Innlandet har tatt beslag i bitcoin etter en aksjon.">
</head><body><article>
<p class="ingress">Politiet i Innlandet har tatt beslag i bitcoin etter en aksjon.</p>
<p>Vær Varsom-plakaten. Pressens Faglige Utvalg (PFU) behandler klager.</p>
<p>Denne nettsiden bruker informasjonskapsler.</p>
</article></body></html>"""
    lead = fetch.teaser_from_html(oa)
    check("bitcoin" in lead and "Vær Varsom" not in lead and "PFU" not in lead and "informasjonskapsler" not in lead, "og:description is the lead")
    footer = "Vær Varsom-plakaten er utarbeidet av Pressens Faglige Utvalg."
    check(fetch.choose_teaser(footer, oa).startswith("Politiet"), "page lead beats the footer")
    check(fetch.strip_boilerplate(footer) == "", "footer alone is dropped")
    mixed = "Politiet i Innlandet har tatt beslag i bitcoin etter en aksjon i går kveld. Vær Varsom-plakaten gjelder."
    kept = fetch.strip_boilerplate(mixed)
    check("bitcoin" in kept and "Vær Varsom" not in kept, "footer is cut off the lead")

    hops = {"n": 0}
    def always(target):
        hops["n"] += 1
        return 302, target + "x", ""
    _body, err = fetch.follow_redirects("https://finansavisen.no/a", always, limit=fetch.PAGE_REDIRECTS)
    check(err == "too many redirects" and hops["n"] == fetch.PAGE_REDIRECTS == 6, "redirect limit is 6")
    def loop(target):
        return 302, "https://finansavisen.no/a", "<html>stuck</html>"
    body, err = fetch.follow_redirects("https://finansavisen.no/a", loop)
    check(err == "redirect loop" and "stuck" in (body or ""), "redirect loop keeps the last html")
    names = {c.name for c in fetch._html_session("finansavisen.no", consent=True).cookies}
    check({"cookieconsent_status", "CookieConsent", "consent"} <= names, "consent cookies on retry")

    bing = fetch.pubtime.bing_instant({"published": "2026-10-05T06:06:00Z"})
    chosen, unverified = fetch.pick_published(None, None, bing, bing=True)
    check(unverified and fetch.pubtime.utc_iso(chosen) == "2026-10-05T13:06:00+00:00", "bing-only time is unverified")
    outlet = fetch.pubtime.from_feed_entry({"published": "2026-10-05T13:06:17+00:00"})
    chosen, unverified = fetch.pick_published(None, outlet, bing, bing=True)
    check((not unverified) and fetch.pubtime.utc_iso(chosen) == "2026-10-05T13:06:17+00:00", "outlet feed beats bing")
    err = fetch.guarded_call(lambda: (_ for _ in ()).throw(RuntimeError("dead feed")))
    check(err and err.startswith("RuntimeError"), "dead feed becomes an error string")
    check(fetch.guarded_call(lambda: None) is None, "success is none")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("fetch filter ok")

if __name__ == "__main__":
    main()
