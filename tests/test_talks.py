#!/usr/bin/env python3
"""Talks archive: data, backfill state, API and the /talks/ page.
  python3 tests/test_talks.py
Renders the talks page into a temp directory. Does not publish."""
import datetime as dt
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import api_feed
import build
import i18n
import markets
import talks as talks_mod

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
KEYS = (
    "nav_talks", "talks_title", "talks_desc", "talks_h1", "talks_lead", "talks_n",
    "talks_none", "talks_year", "talks_year_all", "talks_language", "talks_lang_unknown",
    "talks_play", "talks_watch", "talks_speakers", "talks_event", "talks_channel",
    "talks_published", "talks_duration", "talks_held", "talks_source", "talks_calendar",
    "talks_embed_note", "talks_not_embed", "past_talks", "c_FO", "c_GL", "c_AX",
)
COUNTRIES = {"NO", "SE", "DK", "FI", "IS", "FO", "GL", "AX"}
EARLIEST = dt.date(2008, 10, 31)
TODAY = dt.date(2026, 10, 7)


def check(ok, msg, fails):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    fails = []
    raw = json.load(open(os.path.join(ROOT, "data", "talks.json"), encoding="utf-8"))
    rows = raw["talks"]
    check(len(rows) >= 40, f"seed has {len(rows)} talks", fails)
    ids = [r["id"] for r in rows]
    check(len(ids) == len(set(ids)), "unique ids", fails)
    for r in rows:
        for key in api_feed.TALK_FIELDS:
            check(key in r, f"{r.get('id')} has {key}", fails)
        check(r["platform"] in ("youtube", "vimeo", "university", "other"), r["id"] + " platform", fails)
        check(r["video_url"].startswith("https://"), r["id"] + " video url", fails)
        check(bool(r["title"] and r["source_url"] and r["retrieved_at"] and r["added_at"]), r["id"] + " required text", fails)
        check(isinstance(r["speakers"], list), r["id"] + " speakers", fails)
        check(r.get("country") in COUNTRIES or r.get("country") is None, r["id"] + " country", fails)
        if r.get("duration"):
            check(bool(re.fullmatch(r"PT(?:\d+H)?(?:\d+M)?(?:\d+S)?", r["duration"])), r["id"] + " duration", fails)
        for key in ("date", "published"):
            if r.get(key):
                day = dt.date.fromisoformat(r[key])
                check(EARLIEST <= day <= TODAY, f"{r['id']} {key} {r[key]}", fails)
        check(len(r.get("description") or "") <= 400, r["id"] + " description length", fails)
        blob = json.dumps(r, ensure_ascii=False)
        check(not EMAIL.search(blob), r["id"] + " email", fails)
        check(not talks_mod.PREDATORY.search(blob), r["id"] + " predatory source", fails)
        if r.get("embed"):
            check(r["platform"] in ("youtube", "vimeo"), r["id"] + " embed platform", fails)
        check("gstatic.com" not in blob and "ytimg.com" not in blob, r["id"] + " no copied thumbnail host", fails)

    state = json.load(open(os.path.join(ROOT, "data", "talks-backfill-state.json"), encoding="utf-8"))
    run = state["runs"][0]
    check(run["date"] == "2026-10-07", "backfill run date", fails)
    check(run["new_talks"] == len(rows), "backfill new_talks matches the file", fails)
    check(run["candidates_checked"] >= run["new_talks"], "candidates checked", fails)
    check(any(q["status"] == "exhausted" for q in state["coverage"]["queries"]), "some queries exhausted", fails)
    check(any(q["status"] == "sampled" for q in state["coverage"]["queries"]), "some queries sampled", fails)
    check(state["coverage"]["years"]["2008"]["status"] == "not_searched", "2008 not claimed exhausted", fails)
    check(state["coverage"]["countries"]["FO"]["status"] == "sampled", "Faroe not claimed exhausted", fails)

    for lang in i18n.ALL_LANGS:
        table = i18n.strings(lang)
        for key in KEYS:
            check(bool(table.get(key)), f"{lang} has {key}", fails)
        check("talks/" in i18n.t(lang, "footer"), f"{lang} footer link", fails)
        check("{href}" not in i18n.t(lang, "past_talks", href="../talks/"), f"{lang} past_talks formats", fails)
        # Brand stays Nordic Crypto. The reversed name is built so this file does not contain it.
        reversed_name = "Crypto" + " Nordic"
        check(reversed_name not in table["talks_lead"] and reversed_name not in table["nav_talks"], f"{lang} brand order", fails)

    public = api_feed.public_talks()
    check(len(public) == len(rows), "api row count", fails)
    check(public[0]["published"] >= public[-1]["published"], "newest first", fails)
    check(all(item["embed"] in (True, False) for item in public), "embed bool", fails)

    with tempfile.TemporaryDirectory() as tmp:
        ctx = api_feed.repo_context(False)
        ctx["markets"] = markets.empty_failure("fixture")
        info = api_feed.write(
            tmp, preview=False, base=build.BASE,
            items=ctx["items"], events=ctx["events"][0], entities=ctx["ents"], relations=ctx["rels"],
            org_updated=ctx["org"].get("updated"), regulation=ctx["org"].get("regulation") or [],
            caveats=ctx["org"].get("caveats") or [], sources_cfg=ctx["cfg"],
            news_updated=ctx["news"].get("updated"),
            markets=ctx["markets"],
        )
        body = json.load(open(os.path.join(tmp, "api/v1/talks.json"), encoding="utf-8"))
        check(body["count"] == len(rows), "talks.json count", fails)
        linked = [item for item in body["talks"] if item.get("event_id")]
        check(linked, "api lists a linked talk", fails)
        check(all(item["calendar_event_id"] == item["event_id"] and not item.get("unlink_reason") for item in linked), "api event ids agree", fails)
        unlinked = [item for item in body["talks"] if not item.get("event_id")]
        check(unlinked and all(item.get("unlink_reason") for item in unlinked), "api keeps unlink reasons", fails)
        previous = json.load(open(os.path.join(tmp, "api/v1/events/previous.json"), encoding="utf-8"))
        sample = linked[0]
        host = next(event for event in previous["events"] if event["id"] == sample["event_id"])
        check(sample["id"] in host.get("talk_ids", []), "previous.json lists the talk", fails)
        one_event = json.load(open(os.path.join(tmp, "api/v1/events", sample["event_id"] + ".json"), encoding="utf-8"))
        check(sample["id"] in (one_event.get("item") or {}).get("talk_ids", []), "event document lists the talk", fails)
        check(body["talks"][0]["api_url"].endswith("/talks/" + body["talks"][0]["id"] + ".json"), "per-id url", fails)
        one = json.load(open(os.path.join(tmp, "api/v1/talks", body["talks"][0]["id"] + ".json"), encoding="utf-8"))
        check(one["item"]["id"] == body["talks"][0]["id"], "per-id file", fails)
        no = json.load(open(os.path.join(tmp, "api/v1/talks/by-country/NO.json"), encoding="utf-8"))
        check(no["count"] == sum(r.get("country") == "NO" for r in rows), "NO count", fails)
        fo = json.load(open(os.path.join(tmp, "api/v1/talks/by-country/FO.json"), encoding="utf-8"))
        check(fo["count"] == 0, "FO empty file still exists", fails)
        spec = json.load(open(os.path.join(tmp, "api/v1/openapi.json"), encoding="utf-8"))
        check("Talk" in spec["components"]["schemas"], "openapi Talk", fails)
        spec_talk = spec["components"]["schemas"]["Talk"]["properties"]
        check("event_id" in spec_talk and "unlink_reason" in spec_talk and "talk_ids" in spec["components"]["schemas"]["Event"]["properties"], "openapi link fields", fails)
        check("/api/v1/talks.json" in spec["paths"], "openapi path", fails)
        country_param = None
        for param in spec["paths"]["/api/v1/talks/by-country/{country}.json"]["get"]["parameters"]:
            if param.get("name") == "country":
                country_param = param
        enum = (country_param or {}).get("schema", {}).get("enum") or []
        check(set(enum) == COUNTRIES, "talks country enum " + ",".join(enum), fails)
        docs = open(os.path.join(tmp, "api/index.html"), encoding="utf-8").read()
        check("/api/v1/talks.json" in docs, "human api docs", fails)
        llms = open(os.path.join(tmp, "llms.txt"), encoding="utf-8").read()
        check("talks.json" in llms, "llms.txt", fails)
        check(info["counts"]["talks"] == len(rows), "write() count", fails)

        build.SITE = tmp
        build.PREVIEW = False
        for lang in ("en", "nn"):
            build.LANG = lang
            i18n.MISSING.clear()
            build.build_talks()
            rel = "talks/index.html" if lang == "en" else "nn/talks/index.html"
            html = open(os.path.join(tmp, rel), encoding="utf-8").read()
            check("<iframe" not in html, f"{lang} no iframe before click", fails)
            check("youtube-nocookie.com/embed/" in html, f"{lang} nocookie embed url", fails)
            check('class="talk-play"' in html, f"{lang} play button", fails)
            check("ytimg.com" not in html and "<img" not in html.split('id="talk-list"')[-1].split("</div>")[0], f"{lang} no thumbnail image", fails)
            check('id="talk-year"' in html, f"{lang} year filter", fails)
            check("tcountry" in html and "tlang" in html, f"{lang} country and language filters", fails)
            check("text-align:center" not in html.split(".talks,")[1].split("iframe")[0], f"{lang} talks css not centered", fails)
            check(i18n.t(lang, "nav_talks") in html, f"{lang} nav label", fails)
            check('href="../talks/"' in html or 'href="talks/"' in html or "/talks/" in html, f"{lang} talks href", fails)
            check("Nordic Crypto" in html, f"{lang} brand", fails)
            check('href="../calendar/' in html and "#e-" not in html, f"{lang} talk links to the event page", fails)
            check('href="../org-chart/#' in html, f"{lang} talk links to the speaker", fails)
        # Calendar previous-events link, English and Norwegian.
        now = dt.datetime(2026, 10, 7, tzinfo=dt.timezone.utc)
        for lang in ("en", "nn"):
            build.LANG = lang
            build.build_calendar({"events": ([], now)})
            rel = "calendar/index.html" if lang == "en" else "nn/calendar/index.html"
            html = open(os.path.join(tmp, rel), encoding="utf-8").read()
            check('href="../talks/"' in html, f"{lang} calendar talks link", fails)
            check(i18n.t(lang, "past_talks", href="../talks/") in html, f"{lang} calendar sentence", fails)

    import site_css
    css = site_css.bundle()
    check(".talks,.talks h1" in css and "text-align:start" in css, "talks css is left aligned", fails)
    if fails:
        print(f"\n{len(fails)} failed")
        return 1
    print("talks ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
