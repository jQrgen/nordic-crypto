#!/usr/bin/env python3
"""Previous-events backfill. Stable ids, credited facts, calendar stays clear. No network."""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import event_backfill
import event_select
import i18n

fails = []
REVERSED = "Crypto" + " Nordic"


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    rows = event_backfill.load_events()
    check(len(rows) >= 10, f"first pass has rows ({len(rows)})")
    report = event_backfill.counts(rows)
    check(report["by_country"]["FO"] == 0 and report["by_country"]["GL"] == 0 and report["by_country"]["AX"] == 0, "no Faroe, Greenland or Åland row this pass")
    check(sum(report["by_country"].values()) == len(rows), "country counts add up")
    blob = json.dumps(rows, ensure_ascii=False)
    check(REVERSED not in blob, "brand stays Nordic Crypto")
    check("approximately" not in blob.lower() and "estimated" not in blob.lower(), "estimates are not stored as facts")
    check(all(r.get("attendees") in (None, {}) and r.get("speakers_count") in (None, "") and not r.get("videos_url") for r in rows), "this pass leaves unknown counts empty")
    ids = [r["id"] for r in rows]
    check(len(ids) == len(set(ids)), "ids are unique")
    for row in rows:
        check(not event_backfill.row_problems(row), f"row ok {row['id']}")
        check(row["source"] == "backfill" and row.get("backfill") is True, f"marked backfill {row['id']}")
        check(event_backfill.stable_id(row["url"], row["start"], row["title"]) == row["id"], f"stable id {row['id']}")
        check(row["start"][:10] >= "2008-10-31", f"since white paper {row['id']}")
    state = json.load(open(event_backfill.STATE_PATH, encoding="utf-8"))
    run = state["runs"][-1]
    check(run["by_country"] == report["by_country"] and run["by_year"] == report["by_year"], "state counts match the file")
    check(set(state["countries"]) == set(event_backfill.COUNTRIES), "state lists every Nordic country code")
    check(any("waset.org" in (x.get("host") or "") for x in run["rejected"]), "predatory hosts recorded")

    sample = dict(rows[0])
    sample["url"] = "https://waset.org/conference"
    sample["id"] = event_backfill.stable_id(sample["url"], sample["start"], sample["title"])
    check(any("predatory" in p for p in event_backfill.row_problems(sample)), "predatory URL refused")

    guess = dict(rows[0])
    guess["attendees"] = {"count": "approximately 50", "source_name": "X", "source_url": "https://example.test/a", "retrieved": "2026-10-07T21:00:00+00:00"}
    check(any("attendee" in p for p in event_backfill.row_problems(guess)), "approximate count refused")
    capacity = dict(rows[0])
    capacity["attendees"] = {"count": 30, "source_name": "X", "source_url": "https://conferenceindex.org/e", "retrieved": "2026-10-07T21:00:00+00:00"}
    capacity["credits"] = dict(capacity["credits"])
    capacity["credits"]["attendees"] = {"source_name": "Conference Index", "source_url": "https://conferenceindex.org/e", "retrieved_at": "2026-10-07T21:00:00+00:00"}
    check(any("predatory" in p or "credit" in p for p in event_backfill.row_problems(capacity)), "listing-site count refused")

    early = dict(rows[0])
    early["start"] = "2008-10-30T00:00:00+01:00"
    early["end"] = "2008-10-30T23:59:00+01:00"
    early["id"] = event_backfill.stable_id(early["url"], early["start"], early["title"])
    early["credits"] = dict(early["credits"])
    early["credits"]["start"] = dict(early["credits"]["start"])
    early["credits"]["end"] = dict(early["credits"].get("end") or early["credits"]["start"])
    check(any("2008" in p for p in event_backfill.row_problems(early)), "before 31 Oct 2008 refused")

    now = dt.datetime(2026, 10, 7, 12, tzinfo=event_select.OSLO)
    upcoming = {
        "id": "soon", "title": "Soon", "start": "2026-10-08T18:00:00+02:00", "end": "2026-10-08T21:00:00+02:00",
        "status": "published", "past": False, "country": "SE",
    }
    finished = {
        "id": "done", "title": "Done", "start": "2026-01-02T18:00:00+01:00", "end": "2026-01-02T21:00:00+01:00",
        "status": "published", "past": True, "country": "NO",
    }
    merged = event_backfill.merge_previous([finished], now)
    merged_ids = {e["id"] for e in merged}
    check("done" in merged_ids and "soon" not in merged_ids, "merge keeps finished calendar events")
    check(all(e["id"] in merged_ids for e in rows), "merge includes the backfill")
    check(all(e.get("source") != "backfill" for e in event_select.partition([upcoming, finished], now)["upcoming"]), "calendar upcoming has no backfill")
    front = event_select.partition([upcoming, finished], now)
    check(all(not e.get("backfill") for e in front["upcoming"] + front["ongoing"] + front["previous"]), "front window is calendar data only")
    keys = ("prev_extra", "ev_type", "ev_type_conference", "ev_type_meetup", "ev_type_hackathon", "ev_type_seminar", "ev_language", "ev_lang_en", "ev_lang_is", "ev_speakers", "ev_videos")
    missing = [f"{lang}.{key}" for lang in i18n.ALL_LANGS for key in keys if key not in i18n.strings(lang)]
    check(not missing, "event labels in every site language" + (": " + ", ".join(missing[:6]) if missing else ""))
    if fails:
        print(f"{len(fails)} failed")
        return 1
    print("all ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
