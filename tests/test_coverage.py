#!/usr/bin/env python3
"""Same-event coverage: extra outlets, the matcher, and the breakdown. No network."""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import coverage

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def story(**kw):
    base = {
        "id": "s1",
        "url": "https://www.aftenposten.no/norge/i/vlQARB/tiltalt",
        "title": "Tiltalt for dopsalg mot kryptovaluta på det mørke nettet",
        "source": "aftenposten",
        "source_name": "Aftenposten",
        "country": "NO",
        "language": "Norwegian",
        "published": "2026-10-02T11:07:26+00:00",
        "status": "published",
        "summary": "Three Norwegians and a Swede charged. Finanstilsynet and Økokrim were not named.",
    }
    base.update(kw)
    return base


def main():
    news = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8"))
    item = next(i for i in news["items"] if i["id"] == "1a95167a3af8")
    rows = coverage.all_outlets(item)
    check(len(rows) == 2, "aftenposten story has two outlets")
    check(rows[0]["primary"] and rows[0]["outlet"] == "aftenposten", "primary stays Aftenposten")
    check(rows[1]["outlet"] == "nettavisen" and rows[1]["primary"] is False, "Nettavisen is the extra")
    check(rows[1]["lang"] == "Norwegian" and rows[1]["source_type"] == "national", "extra fields")
    check("nettavisen.no" in rows[1]["url"], "nettavisen url")
    br = coverage.breakdown(rows)
    check(br["count"] == 2, "count 2")
    check(br["by_country"] == [{"country": "NO", "count": 2, "share": 1.0}], "country bar")
    types = {r["type"]: r["count"] for r in br["by_source_type"]}
    check(types == {"national": 2, "regional": 0, "official": 0, "international": 0}, "all four source types")
    bare = coverage.all_outlets(story())
    check(len(bare) == 1 and "also_covered_by" not in story(), "missing list is one outlet")
    check(coverage.reach_of({"kind": "Police/prosecution"}, "NO") == "official", "police is official")
    check(coverage.reach_of({"kind": "Wire"}, None) == "international", "wire is international")
    check(coverage.reach_of({"kind": "Newspaper", "reach": "regional"}, "NO") == "regional", "reach override")
    check(coverage.reach_of({"kind": "Newspaper", "country": "NO"}, "NO") == "national", "newspaper is national")

    same = story(id="s2", url="https://www.vg.no/a/1", title="Tiltalt for dopsalg mot kryptovaluta på det mørke nettet",
                 source="vg", source_name="VG", published="2026-10-02T12:00:00+00:00")
    hit, why = coverage.find_match(
        {"url": same["url"], "title": same["title"], "published": same["published"], "text": same["title"]},
        [story()],
    )
    check(hit and hit["id"] == "s1" and why == "same title", "same headline attaches")

    near = {
        "url": "https://www.dagbladet.no/nyheter/tiltalt-dopsalg-kryptovaluta-morke-nettet",
        "title": "Tiltalt for dopsalg av kryptovaluta på det mørke nettet",
        "published": "2026-10-03T08:00:00+00:00",
        "text": "Tiltalt for dopsalg av kryptovaluta på det mørke nettet i stor sak",
    }
    hit, why = coverage.find_match(near, [story()])
    check(hit and why == "title similarity", "close title inside the window")

    other = {
        "url": "https://www.example.no/annen-sak",
        "title": "Firi senker gebyret for bitcoin-handel",
        "published": "2026-10-02T12:00:00+00:00",
        "text": "Firi senker gebyret for bitcoin-handel i Norge",
    }
    hit, why = coverage.find_match(other, [story()])
    check(hit is None and why is None, "different event stays separate")

    late = {
        "url": "https://www.vg.no/a/2",
        "title": story()["title"],
        "published": "2026-11-01T12:00:00+00:00",
        "text": story()["title"],
    }
    check(coverage.find_match(late, [story()])[0] is None, "same headline weeks later is not folded")

    orgs = story(summary="Finanstilsynet and Økokrim both commented on the exchange.")
    cand = {
        "url": "https://www.nrk.no/nyheter/annet",
        "title": "Nytt tilsyn med børsen",
        "published": "2026-10-02T15:00:00+00:00",
        "text": "Finanstilsynet og Økokrim ser på saken",
    }
    hit, why = coverage.find_match(cand, [orgs])
    check(hit and why == "same entities", "two shared organisations")

    host = story()
    check(coverage.attach(host, coverage.record_from_item(same)), "attach once")
    check(not coverage.attach(host, coverage.record_from_item(same)), "attach is idempotent")
    check(not coverage.attach(host, coverage.record_from_item(story())), "primary url is not an extra")
    dup = story(id="dup", url="https://www.nettavisen.no/s/1", source="nettavisen", source_name="Nettavisen", status="pending")
    folded = coverage.fold_into([host, dup], dup, "s1")
    check(folded and folded["id"] == "s1" and dup["status"] == "merged", "editor duplicate_of folds")
    check(any(ex["outlet"] == "nettavisen" for ex in host["also_covered_by"]), "folded outlet stored")
    check(coverage.fold_into([host, dup], dup, "missing") is None, "unknown target is left alone")

    rejected = story(id="rej", status="rejected", url="https://www.example.no/rej")
    check(coverage.find_match(
        {"url": "https://www.vg.no/x", "title": rejected["title"], "published": rejected["published"], "text": rejected["title"]},
        [rejected],
    )[0] is None, "rejected story is not a target")

    idx = coverage.index_urls([host])
    check(coverage.canon(same["url"]) in idx and idx[coverage.canon(same["url"])] is host, "extra url indexed")

    if fails:
        print(f"{len(fails)} failed")
        sys.exit(1)
    print("coverage: all checks passed")


if __name__ == "__main__":
    main()
