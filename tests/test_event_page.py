#!/usr/bin/env python3
"""Event pages under /calendar/<id>/. No invented facts. No network."""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build
import event_page
import i18n

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def sample():
    return {
        "id": "ccc2eea6b213",
        "title": "Göteborg Bitcoin Meetup #49",
        "start": "2026-10-08T18:00:00+02:00",
        "end": "2026-10-08T21:00:00+02:00",
        "place": "Ölrepubliken, Kronhusgatan 2B, Göteborg",
        "city": "Göteborg",
        "country": "SE",
        "online": False,
        "organiser": "Swedish Bitcoin Meetups",
        "url": "https://www.meetup.com/swedish-bitcoin-meetups/events/316047111/",
        "source": "Swedish Bitcoin Meetups (Meetup.com)",
        "source_url": "https://www.meetup.com/swedish-bitcoin-meetups/events/316047111/",
        "found": "2026-10-01T12:00:00+00:00",
        "status": "published",
        "past": False,
    }


def main():
    ev = sample()
    check(event_page.slug(ev) == "calendar/ccc2eea6b213", "slug uses the 12-hex id")
    check(event_page.offset_label(ev["start"]) == "UTC+02:00", "offset from the stored timestamp")
    check(event_page.offset_label("2018-04-18T16:45:00+00:00") == "UTC+00:00", "zero offset kept")
    check(event_page.map_url({"country": "NO", "online": False}) is None, "no map without a place or city")
    murl = event_page.map_url(ev)
    check(murl and "Kronhusgatan" in murl and "Sweden" in murl, "map searches the stored place")
    check(not event_page.topics(ev), "topics are not guessed")
    credited = dict(ev, topics=["bitcoin"], credits={"topics": {"source_name": "Listing", "source_url": "https://example.test/t", "retrieved_at": "2026-10-01T12:00:00+00:00"}})
    check(event_page.topics(credited) == ["bitcoin"], "credited topics are kept")
    data = event_page.jsonld(ev, "https://nordiccrypto.no/calendar/ccc2eea6b213/", None)
    check(data["@type"] == "Event" and data["startDate"] == ev["start"] and data["endDate"] == ev["end"], "json-ld dates")
    check("maximumAttendeeCapacity" not in data and "attendeeCount" not in json.dumps(data), "json-ld has no invented count")
    check(data["location"]["address"]["addressLocality"] == "Göteborg", "json-ld city")
    check(data["sameAs"] == ev["url"] and data.get("isAccessibleForFree") is None, "official url, unpaid flag omitted")
    bare = dict(ev)
    bare.pop("place")
    bare.pop("city")
    check(event_page.map_url(bare) is None, "city and venue both required for a map when absent")
    check(event_page.related_talks("ccc2eea6b213", path=os.path.join(ROOT, "data", "no-talks.json")) == [], "missing talks file")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "talks.json")
        json.dump({"talks": [
            {"event_id": "ccc2eea6b213", "title": "Opening", "video_url": "https://example.test/v", "source_name": "Archive", "source_url": "https://example.test/src", "retrieved_at": "2026-10-07T21:00:00+00:00"},
            {"event_id": "other", "title": "Nope", "video_url": "https://example.test/no"},
            {"event_id": "ccc2eea6b213", "title": "No video"},
        ]}, open(path, "w", encoding="utf-8"))
        talks = event_page.related_talks("ccc2eea6b213", path)
        check(len(talks) == 1 and talks[0]["url"] == "https://example.test/v" and talks[0]["retrieved"], "talk video matched by event id")
    build.LANG = "en"
    check("calendar/ccc2eea6b213/" == build.event_link(ev), "front-page link")
    check(build.event_link(ev, "../../") == "../../calendar/ccc2eea6b213/", "previous-page link")
    card = build.event_card(ev)
    check('href="calendar/ccc2eea6b213/"' in card and "text-align:center" not in card, "card links to the event page")
    check("Registered participants" not in card, "card omits an unsourced count")
    keys = ("ev_official", "ev_map", "ev_tz", "ev_about", "ev_topics", "ev_talks", "ev_cal_link", "ev_orig_below")
    missing = [f"{lang}.{key}" for lang in i18n.ALL_LANGS for key in keys if key not in i18n.strings(lang)]
    check(not missing, "event page strings in every language")
    with tempfile.TemporaryDirectory() as site:
        build.SITE = site
        build.PREVIEW = False
        build.LANG = "en"
        build.build_one_event(ev)
        html = open(os.path.join(site, "calendar", ev["id"], "index.html"), encoding="utf-8").read()
        check('rel="canonical" href="https://nordiccrypto.no/calendar/ccc2eea6b213/"' in html, "canonical")
        check('hreflang="nn" href="https://nordiccrypto.no/nn/calendar/ccc2eea6b213/"' in html, "hreflang")
        check('hreflang="x-default"' in html, "x-default")
        check("application/ld+json" in html and '"@type": "Event"' in html, "json-ld")
        check("Official event page" in html and "https://www.meetup.com/swedish-bitcoin-meetups/events/316047111/" in html, "official link")
        check("UTC+02:00" in html and "Map" in html and "openstreetmap.org" in html, "timezone and map")
        check("Registered participants" not in html, "page omits an unsourced count")
        check(".evpage,.evpage h1,.evpage h2,.evpage p,.evpage li{text-align:left}" in html, "event page is left-aligned")
        check("evofficial" in html and "margin:0 auto" not in html.split("evofficial{")[1].split("}")[0], "official link is not centred")
        build.LANG = "nn"
        build.build_one_event(ev)
        nn = open(os.path.join(site, "nn", "calendar", ev["id"], "index.html"), encoding="utf-8").read()
        check("Offisiell side for arrangementet" in nn, "nynorsk official link")
        check('rel="canonical" href="https://nordiccrypto.no/nn/calendar/ccc2eea6b213/"' in nn, "nynorsk canonical")
    if fails:
        print(f"{len(fails)} failed")
        return 1
    print("all ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
