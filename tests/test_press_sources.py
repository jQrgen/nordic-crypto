#!/usr/bin/env python3
"""Press and justice registry. No network and no fetch run.
python3 tests/test_press_sources.py
"""
import json, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import api_feed
import build

def main():
    fails = []
    def check(cond, msg):
        if not cond:
            fails.append(msg)
    cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    sources = cfg["sources"]
    ids = [s["id"] for s in sources]
    check(len(ids) == len(set(ids)), "duplicate source ids")
    check(cfg.get("fetch_workers", 0) >= 2, "fetch workers")
    check(cfg.get("event_sources"), "event sources kept")
    by = {s["id"]: s for s in sources}
    for s in sources:
        if s.get("coverage") not in ("national", "regional", "local", "justice"):
            fails.append("bad coverage " + s["id"])
            break
        feed = s.get("feed")
        if feed is not None and not str(feed).startswith("http"):
            fails.append("bad feed " + s["id"])
            break
        if "also_covered_by" in s:
            fails.append("story field on a source " + s["id"])
            break
    for place in ("FO", "GL", "AX"):
        check(any(s.get("country") == place for s in sources), place + " missing")
    for needle in ("Politiet", "Riksadvokaten", "Økokrim", "polisen.se", "Ekobrottsmyndigheten",
                   "Sveriges Domstolar", "Politi", "Anklagemyndigheden", "Hvidvasksekretariatet",
                   "Poliisi", "Syyttäjälaitos", "Tuomioistuinlaitos", "Lögreglan", "Ríkissaksóknari",
                   "Skatteetaten", "Tolletaten"):
        check(any(needle.lower() in (s.get("name") or "").lower() for s in sources), "missing " + needle)
    check(by["vb"]["enabled"] is False and not by["vb"].get("feed") and by["vb"].get("method") == "manual", "vb stays blocked")
    check(by["finansavisen"].get("method") == "sitemap" and by["finansavisen"].get("enabled") is True, "finansavisen no-rss fallback")
    bb = by["barebitcoin"]
    check(bb.get("enabled") is True and bb.get("method") == "sitemap" and str(bb.get("feed") or "").endswith("/sitemap.xml"), "bare bitcoin sitemap")
    check(by["e24"].get("method") == "rss" and by["kaupr-no"].get("method") == "html", "rss and html methods")
    check(by["politiet"].get("method") == "manual" and not by["politiet"].get("feed"), "politiet stays manual")
    check(by["aftenposten"]["coverage"] == "national", "aftenposten national")
    check(by["politiet"]["coverage"] == "justice" and by["politiet"].get("feed") in (None, ""), "politiet listed, robots-blocked feed not stored")
    outlets, _, _ = api_feed._sources(cfg)
    krow = next(o for o in outlets if o["id"] == "kaupr-no")
    check("news source" in (krow.get("source_note") or ""), "kaupr api note")
    prow = next(o for o in outlets if o["id"] == "politiet")
    check(prow.get("coverage") == "justice" and prow.get("feed") is None, "politiet api")
    arow = next(o for o in outlets if o["id"] == "aftenposten")
    check(arow.get("coverage") == "national", "aftenposten api coverage")
    # logo provenance is either absent or an https URL, never a local path
    for o in outlets:
        if o.get("logo_source") and not str(o["logo_source"]).startswith("https://"):
            fails.append("logo_source " + o["id"])
            break

    build.LANG = "en"
    build.PREVIEW = False
    with tempfile.TemporaryDirectory() as tmp:
        build.SITE = tmp
        build.build_sources({"cfg": cfg, "status": {}})
        html = open(os.path.join(tmp, "sources", "index.html"), encoding="utf-8").read()
    check('style="justify-content:flex-start;text-align:left"' in html, "filters are left aligned")
    check('table class="list" style="text-align:left"' in html, "table is left aligned")
    check("Reach" in html and "Justice" in html, "coverage columns")
    check(">Method<" in html and ">Sitemap<" in html and ">RSS<" in html, "method column")
    check("barebitcoin.no/sitemap.xml" in html, "bare bitcoin sitemap link")
    check("Faroe Islands" in html and "Greenland" in html, "territories named")
    check('id="kaupr"' in html, "kaupr notice")
    # the sources table itself is not a centered layout
    table = html.split('id="srclist"', 1)[0]
    check("text-align:center" not in table.split("<table", 1)[-1][:400], "sources table header is not centered")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("press sources ok", len(sources))

if __name__ == "__main__":
    main()
