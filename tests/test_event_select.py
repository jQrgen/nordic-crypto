#!/usr/bin/env python3
"""Front-page event window. Same inputs and the same now always give the same lists.
The upcoming list changes when an event starts, not when it ends. No network."""
import html
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import api_feed
import event_select
import i18n

fails = []
REVERSED = "Crypto" + " Nordic"


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def ev(i, start, end=None, **kw):
    row = {
        "id": i, "title": i, "start": start, "place": "Venue", "city": "Oslo", "country": "NO",
        "source": "Luma", "source_url": "https://example.test/" + i, "found": "2026-08-01T12:00:00+02:00",
        "organiser": "Nordic Crypto", "url": "https://example.test/" + i,
    }
    if end:
        row["end"] = end
    row.update(kw)
    return row


def ids(rows):
    return [e["id"] for e in rows]


def window():
    rows = [
        ev("multi", "2026-08-25T08:30:00+02:00", "2026-08-26T12:30:00+02:00"),
        ev("n1", "2026-08-27T18:00:00+02:00", "2026-08-27T21:00:00+02:00"),
        ev("n2", "2026-08-28T18:00:00+02:00", "2026-08-28T21:00:00+02:00"),
        ev("n3", "2026-08-29T18:00:00+02:00", "2026-08-29T21:00:00+02:00"),
        ev("n4", "2026-08-30T18:00:00+02:00", "2026-08-30T21:00:00+02:00"),
        ev("n5", "2026-08-31T18:00:00+02:00", "2026-08-31T21:00:00+02:00"),
        ev("n6", "2026-09-01T18:00:00+02:00", "2026-09-01T21:00:00+02:00"),
        ev("n7", "2026-09-02T18:00:00+02:00", "2026-09-02T21:00:00+02:00"),
    ]
    before = event_select.partition(rows, "2026-08-25T08:00:00+02:00")
    during = event_select.partition(list(reversed(rows)), "2026-08-25T15:00:00+02:00")
    again = event_select.partition(rows, "2026-08-25T15:00:00+02:00")
    after = event_select.partition(rows, "2026-08-26T12:31:00+02:00")
    started = event_select.partition(rows, "2026-08-27T18:00:00+02:00")
    check(ids(before["ongoing"]) == [], "before: no ongoing card")
    check(ids(before["upcoming"]) == ["multi", "n1", "n2", "n3", "n4", "n5"], "before: next six, soonest first")
    check(ids(during["ongoing"]) == ["multi"] and "multi" not in ids(during["upcoming"]), "during: multi-day is the hero, not in the list")
    check(ids(during["upcoming"]) == ["n1", "n2", "n3", "n4", "n5", "n6"], "during: the next event has moved in")
    check(ids(during["upcoming"]) == ids(again["upcoming"]) and ids(during["ongoing"]) == ids(again["ongoing"]),
          "same now, reversed input, same lists")
    check(ids(after["ongoing"]) == [], "just after the end: hero is gone")
    check(ids(after["upcoming"]) == ids(during["upcoming"]), "the list changes when an event starts, not when it ends")
    check(ids(after["previous"])[0] == "multi", "a finished event is kept, newest first")
    check(ids(started["ongoing"]) == ["n1"] and "n1" not in ids(started["upcoming"]), "at the next start that event is ongoing")
    check(ids(started["upcoming"]) == ["n2", "n3", "n4", "n5", "n6", "n7"], "at the next start the upcoming list changes")
    check(len(started["upcoming"]) == event_select.FRONT_LIMIT, "front list is six")


def edges():
    day = ev("day", "2026-09-10T00:00:00+02:00", "2026-09-10T23:59:00+02:00")
    check(event_select.classify(day, "2026-09-10T00:00:00+02:00") == "ongoing", "all-day is ongoing at local midnight")
    check(event_select.classify(day, "2026-09-10T23:59:00+02:00") == "ongoing", "all-day stays ongoing through 23:59")
    check(event_select.classify(day, "2026-09-11T00:00:00+02:00") == "previous", "all-day is previous the next local day")
    open_end = ev("open", "2026-09-12T18:00:00+02:00")
    check(event_select.classify(open_end, "2026-09-12T17:59:00+02:00") == "upcoming", "no end is upcoming before it starts")
    check(event_select.classify(open_end, "2026-09-12T18:01:00+02:00") == "ongoing", "no end stays ongoing after it starts")
    check(event_select.classify(open_end, "2026-09-12T21:00:00+02:00") == "ongoing", "no end is ongoing at start plus 3 hours")
    check(event_select.classify(open_end, "2026-09-12T21:00:01+02:00") == "previous", "no end is previous one second after start plus 3 hours")
    check(event_select.phase(open_end, "2026-09-12T18:01:00+02:00") == "ongoing", "phase is ongoing while the assumed window runs")
    check(event_select.phase(open_end, "2026-09-12T21:00:01+02:00") == "past", "phase is past after the assumed end")
    ann = event_select.annotate(open_end, "2026-09-12T18:01:00+02:00")
    check(ann["phase"] == "ongoing" and ann["phase_end"] == "2026-09-12T21:00:00+02:00" and ann["past"] is False and ann["ongoing"] is True,
          "annotate writes phase and phase_end")
    check(event_select.end_of(open_end) is None and "end" not in open_end, "stored end stays empty")
    midnight = ev("mid", "2026-09-10T00:00:00+02:00")
    check(event_select.classify(midnight, "2026-09-10T23:59:00+02:00") == "ongoing", "midnight with no end stays ongoing through 23:59")
    check(event_select.classify(midnight, "2026-09-11T00:00:00+02:00") == "previous", "midnight with no end is previous the next local day")
    check(event_select.effective_end(midnight).isoformat() == "2026-09-10T23:59:00+02:00", "midnight assumed end is 23:59")
    # 18:00+03 is 15:00 UTC; 17:30+02 is 15:30 UTC. String order would put the later one first.
    hel = ev("hel", "2026-10-01T18:00:00+03:00", "2026-10-01T20:00:00+03:00")
    oslo = ev("oslo", "2026-10-01T17:30:00+02:00", "2026-10-01T19:00:00+02:00")
    part = event_select.partition([oslo, hel], "2026-10-01T12:00:00+02:00")
    check(ids(part["upcoming"]) == ["hel", "oslo"], "sort is by instant, not by the offset text")
    older = ev("older", "2026-01-01T18:00:00+01:00", "2026-01-01T20:00:00+01:00")
    newer = ev("newer", "2026-06-01T18:00:00+02:00", "2026-06-02T12:00:00+02:00")
    prev = event_select.partition([older, newer], "2026-08-01T12:00:00+02:00")["previous"]
    check(ids(prev) == ["newer", "older"], "previous events are newest finish first")


def facts():
    bare = ev("bare", "2026-10-08T18:00:00+02:00", "2026-10-08T21:00:00+02:00", source="", source_url="", url="")
    check(event_select.location_fact(bare) is None, "location without a source is omitted")
    credited = ev("ok", "2026-10-08T18:00:00+02:00", "2026-10-08T21:00:00+02:00")
    loc = event_select.location_fact(credited)
    check(loc and loc["text"] == "Venue, Oslo" and loc["credit"]["url"].endswith("/ok"), "credited location")
    check(event_select.attendees_fact(credited) is None, "no invented participant count")
    check(event_select.attendees_fact({"attendees": {"count": 40}, "id": "x", "start": "2026-10-08T18:00:00+02:00"}) is None,
          "a count without its own source is omitted")
    check(event_select.explicit_attendee_count({"maximumAttendeeCapacity": 100, "remainingAttendeeCapacity": 3}) is None,
          "capacity is ignored")
    credited["attendees"] = {"count": 42, "source_name": "Luma", "source_url": "https://lu.ma/ok", "retrieved": "2026-08-01T12:00:00+02:00"}
    att = event_select.attendees_fact(credited)
    check(att and att["count"] == 42 and att["credit"]["name"] == "Luma", "credited participant count")
    feed = api_feed.Feed("/tmp", False, "https://nordiccrypto.no/", now="2026-08-25T15:00:00+02:00")
    item = feed.event_item(ev("multi", "2026-08-25T08:30:00+02:00", "2026-08-26T12:30:00+02:00"))
    check(item["ongoing"] is True and item["phase"] == "ongoing" and item["phase_end"] == "2026-08-26T12:30:00+02:00"
          and item["end"] == "2026-08-26T12:30:00+02:00" and "attendees" not in item and item["place_source"]["name"] == "Luma",
          "api ongoing and place credit")
    later = api_feed.Feed("/tmp", False, "https://nordiccrypto.no/", now="2026-08-26T12:31:00+02:00")
    ended = later.event_item(ev("multi", "2026-08-25T08:30:00+02:00", "2026-08-26T12:30:00+02:00"))
    check(ended["ongoing"] is False and ended["phase"] == "past", "api ongoing is false once the event has ended")
    during = api_feed.Feed("/tmp", False, "https://nordiccrypto.no/", now="2026-10-14T18:00:00+02:00")
    killer = ev("killer", "2026-10-14T17:30:00+02:00", "2026-10-14T18:30:00+02:00")
    nxt = ev("nxt", "2026-10-15T17:30:00+02:00", "2026-10-15T18:30:00+02:00")
    done = ev("done", "2026-10-01T17:30:00+02:00", "2026-10-01T18:30:00+02:00")
    open3 = ev("open3", "2026-10-14T17:00:00+02:00")
    items = [during.event_item(row) for row in (killer, nxt, done, open3)]
    up, ong, past_rows = api_feed.event_lists(items)
    check([row["id"] for row in ong] == ["killer", "open3"], "api ongoing list is the started events")
    check("killer" not in ids(up) and "open3" not in ids(up), "ongoing is not in the upcoming list")
    check("killer" not in ids(past_rows) and "open3" not in ids(past_rows), "ongoing is not in past")
    check(items[3]["end"] is None and items[3]["phase_end"] == "2026-10-14T20:00:00+02:00", "missing end is exposed as phase_end only")
    check(all(row["phase"] in ("upcoming", "ongoing", "past") for row in items), "phase is upcoming, ongoing or past")


def apple_tv():
    screen = open(os.path.join(ROOT, "templates", "screen.html"), encoding="utf-8").read()
    check("EV_LIMIT=__EV_LIMIT__" in screen and "s>now" in screen and "slice(0,4)" not in screen,
          "office screen uses the start-based window")
    import build
    for lang in i18n.ALL_LANGS:
        sentence = i18n.t(lang, "ios_tv")
        build.LANG = lang
        footer = build.site_footer("", "")   # the Follow column links the app and carries the Apple TV note
        check("Apple TV" in sentence and REVERSED not in sentence, "sentence " + lang)
        check("https://testflight.apple.com/join/nQ2fpjZn" in footer and html.escape(sentence, quote=False) in footer, "footer " + lang)
        check(REVERSED not in footer, "brand " + lang)
    build.LANG = "en"
    check(i18n.t("nn", "ios_tv") == "Støtter særleg Apple TV.", "nynorsk wording")
    check(i18n.t("en", "ios_tv") == "Especially supports Apple TV.", "english wording")


def main():
    window()
    edges()
    facts()
    apple_tv()
    if fails:
        print(len(fails), "failed")
        sys.exit(1)
    print("ok")


if __name__ == "__main__":
    main()
