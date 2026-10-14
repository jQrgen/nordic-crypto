#!/usr/bin/env python3
"""Event pages under /calendar/<id>/. No invented facts. No network."""
import datetime as dt
import json
import os
import subprocess
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
    check(event_page.apple_map_url({"country": "NO", "online": False}) is None, "no apple map without a place or city")
    murl = event_page.map_url(ev)
    apple = event_page.apple_map_url(ev)
    check(murl and murl.startswith("https://www.google.com/maps/search/?api=1&query=") and "Kronhusgatan" in murl and "Sweden" in murl, "map searches the stored place on Google Maps")
    check(apple and apple.startswith("https://maps.apple.com/?q=") and "Kronhusgatan" in apple and "Sweden" in apple, "apple map searches the same address")
    check("openstreetmap.org" not in (murl or "") and "openstreetmap.org" not in (apple or ""), "map links are not OpenStreetMap")
    pinned = dict(ev, lat=59.5, lng=10.25)
    check(event_page.map_url(pinned) == "https://www.google.com/maps/search/?api=1&query=59.5%2C10.25", "coordinates use lat,lng on Google Maps")
    check(event_page.apple_map_url(pinned) == "https://maps.apple.com/?ll=59.5,10.25", "coordinates use ll= on Apple Maps")
    check(event_page.apple_map_url({"geo": {"latitude": "59,5", "longitude": "10,25"}}) == "https://maps.apple.com/?ll=59.5,10.25", "geo coordinates are accepted")
    check("Kronhusgatan" in event_page.map_url(dict(ev, lat=999, lng=10)), "an impossible latitude falls back to the address")
    check(event_page.map_url({"online": True, "country": "NO"}) is None, "online with no venue has no map")
    check(event_page.map_url({"online": True, "lat": 59.5, "lng": 10.25}) == "https://www.google.com/maps/search/?api=1&query=59.5%2C10.25", "stored coordinates still map an online row")
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
            {"event_id": "ccc2eea6b213", "title": "Opening", "video_url": "https://example.test/v", "speakers": ["Ada Lovelace"], "source_name": "Archive", "source_url": "https://example.test/src", "retrieved_at": "2026-10-07T21:00:00+00:00"},
            {"event_id": "other", "title": "Nope", "video_url": "https://example.test/no"},
            {"event_id": "ccc2eea6b213", "title": "No video"},
        ]}, open(path, "w", encoding="utf-8"))
        talks = event_page.related_talks("ccc2eea6b213", path)
        check(len(talks) == 1 and talks[0]["url"] == "https://example.test/v" and talks[0]["retrieved"], "talk video matched by event id")
        check(talks[0].get("speakers") == ["Ada Lovelace"], "talk speakers are returned")
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
        check("UTC+02:00" in html and ">Map</a>" in html and "https://www.google.com/maps/search/?api=1&amp;query=" in html, "timezone and google map link")
        check("data-apple-map=\"https://maps.apple.com/?q=" in html and "openstreetmap.org" not in html, "apple map is the swap target")
        check(html.count(event_page.APPLE_MAP_SCRIPT) == 1 and "navigator.userAgent" in html and "navigator.platform" in html, "one inline script checks the user agent and platform")
        check("Mac|iPhone|iPad|iPod" in html, "script treats iOS, iPadOS and macOS as Apple")
        check("Registered participants" not in html, "page omits an unsourced count")
        # start, not left: the page mirrors in Arabic and Urdu
        check(".evpage,.evpage h1,.evpage h2,.evpage p,.evpage li{text-align:start}" in html, "event page is start-aligned")
        check("evofficial" in html and "margin:0 auto" not in html.split("evofficial{")[1].split("}")[0], "official link is not centred")
        build.LANG = "nn"
        build.build_one_event(ev)
        nn = open(os.path.join(site, "nn", "calendar", ev["id"], "index.html"), encoding="utf-8").read()
        check("Offisiell side for arrangementet" in nn, "nynorsk official link")
        check(">Kart</a>" in nn and "https://www.google.com/maps/search/?api=1&amp;query=" in nn and "navigator.userAgent" in nn, "nynorsk map link and script")
        check('rel="canonical" href="https://nordiccrypto.no/nn/calendar/ccc2eea6b213/"' in nn, "nynorsk canonical")
        check("About this event" not in html, "no description section without a sourced description")
        described = dict(ev, description={
            "text": "Vi møtes for å snakke om bitcoin og lynnettet.",
            "lang": "nb",
            "source_url": ev["url"],
            "source_name": "Swedish Bitcoin Meetups (Meetup.com)",
            "retrieved": "2026-10-07T23:50:00+00:00",
            "i18n": {"en": "We meet to talk about bitcoin and the Lightning Network."},
            "i18n_source": "Vi møtes for å snakke om bitcoin og lynnettet.",
        })
        build.LANG = "en"
        build.build_one_event(described)
        en_html = open(os.path.join(site, "calendar", ev["id"], "index.html"), encoding="utf-8").read()
        check("About this event" in en_html and "We meet to talk about bitcoin and the Lightning Network." in en_html, "english description")
        check("Vi møtes for å snakke om bitcoin og lynnettet." in en_html, "original under the translation")
        about = en_html.split("About this event", 1)[1][:500]
        check("text-align:center" not in about and 'class="evdesc"' in en_html, "description is left aligned")
        # when, where and who come first, in one block with the official link; the description follows that block
        check(en_html.index("Date and time") < en_html.index("Location") < en_html.index("Official event page") < en_html.index("About this event"), "description sits under the when/where block")
        build.LANG = "nb"
        build.build_one_event(described)
        nb_html = open(os.path.join(site, "nb", "calendar", ev["id"], "index.html"), encoding="utf-8").read()
        check("Vi møtes for å snakke om bitcoin og lynnettet." in nb_html, "bokmål page shows the original")
        check("Originaltekst" not in nb_html, "same language has no original line")
        bare = dict(ev, description={
            "text": "A meetup about bitcoin in Gothenburg.",
            "lang": "en",
            "source_url": ev["url"],
            "source_name": "Meetup",
            "retrieved": "2026-10-07T23:50:00+00:00",
        })
        build.LANG = "sv"
        build.build_one_event(bare)
        sv_html = open(os.path.join(site, "sv", "calendar", ev["id"], "index.html"), encoding="utf-8").read()
        check("A meetup about bitcoin in Gothenburg." in sv_html and "Originaltext" not in sv_html, "missing translation shows the original only")
        talk_path = os.path.join(site, "fixture-talks.json")
        json.dump({"talks": [{
            "event_id": ev["id"], "title": "Opening", "video_url": "https://example.test/v",
            "speakers": ["Ada Lovelace"], "speaker_ids": ["spk-ada-lovelace"], "source_name": "Archive",
            "source_url": "https://example.test/src", "retrieved_at": "2026-10-07T21:00:00+00:00",
        }]}, open(talk_path, "w", encoding="utf-8"))
        old_talks = build.event_page.TALKS_PATH
        build.event_page.TALKS_PATH = talk_path
        try:
            build.LANG = "en"
            build.build_one_event(ev)
        finally:
            build.event_page.TALKS_PATH = old_talks
        listed = open(os.path.join(site, "calendar", ev["id"], "index.html"), encoding="utf-8").read()
        check("Opening" in listed and "Ada Lovelace" in listed and "Speakers" in listed, "event page lists the talk, speaker and video")
        check('href="https://example.test/v"' in listed, "event page links the video")
        check('href="../../org-chart/#spk-ada-lovelace"' in listed, "event page links the speaker")
        check("text-align:center" not in listed.split(".evpage,.evpage h1")[1].split("}")[0], "talk list stays left aligned")
        row = build.cal_row(ev)
        check("https://www.google.com/maps/search/?api=1&amp;query=" in row and "data-apple-map=\"https://maps.apple.com/?q=" in row and ">Map</a>" in row, "calendar row links the place to a map")
        check("openstreetmap.org" not in row, "calendar row is not OpenStreetMap")
        build.LANG = "nb"
        listed_ev = dict(ev, past=False, status="published")
        build.build_calendar({"events": ([listed_ev], dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc))})
        cal = open(os.path.join(site, "nb", "calendar", "index.html"), encoding="utf-8").read()
        check(">Kart</a>" in cal and "https://www.google.com/maps/search/?api=1&amp;query=" in cal and cal.count(event_page.APPLE_MAP_SCRIPT) == 1, "bokmål calendar list has one map script")
        check("data-apple-map=\"https://maps.apple.com/?q=" in cal and "navigator.platform" in cal, "calendar list can swap to Apple Maps")
        probe = r"""
const vm = require("vm");
const script = process.argv[1];
function run(ua, platform) {
  const el = {href: "https://www.google.com/maps/search/?api=1&query=Oslo", getAttribute(){return "https://maps.apple.com/?q=Oslo"}};
  const ctx = {navigator: {userAgent: ua, platform: platform}, document: {querySelectorAll(){return [el]}}};
  vm.createContext(ctx);
  vm.runInContext(script, ctx);
  return el.href;
}
const out = [
  run(process.argv[2], process.argv[3]),
  run(process.argv[4], process.argv[5]),
  run(process.argv[6], process.argv[7]),
];
process.stdout.write(out.join("\n"));
"""
        swapped = subprocess.run(
            ["node", "-e", probe,
             event_page.APPLE_MAP_SCRIPT.replace("<script>", "").replace("</script>", ""),
             "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "iPhone",
             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "MacIntel",
             "Mozilla/5.0 (Linux; Android 14)", "Linux armv8l"],
            capture_output=True, text=True, check=True)
        iphone, mac, android = swapped.stdout.split("\n")
        check(iphone == "https://maps.apple.com/?q=Oslo", "iphone user agent swaps to Apple Maps")
        check(mac == "https://maps.apple.com/?q=Oslo", "mac platform swaps to Apple Maps")
        check(android == "https://www.google.com/maps/search/?api=1&query=Oslo", "other devices keep Google Maps")
    if fails:
        print(f"{len(fails)} failed")
        return 1
    print("all ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
