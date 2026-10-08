"""Previous-events backfill: public Nordic crypto events since 31 Oct 2008.

Rows live in data/events_backfill.json. They are marked source "backfill" and
are not calendar events. The previous-events page and api/v1/events/previous.json
merge them in. The upcoming list, the calendar page and api/v1/events/past.json
do not.

data/events_backfill_state.json records each run (countries, queries, rejected
listings, counts) so a later run can extend the file and then taper off.
Ids are the same 12-hex sha1 as events.eid, so a talks archive can link to an
event without this file being rewritten.

Every stored fact needs a credit (source name, source URL, retrieved_at).
Counts are exact integers only. Capacity and estimates are not counts.
Predatory conference listings are refused with event_block.
"""
import datetime as dt
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import event_block  # noqa: E402
import event_description  # noqa: E402
import event_select  # noqa: E402

DATA_PATH = os.path.join(ROOT, "data", "events_backfill.json")
STATE_PATH = os.path.join(ROOT, "data", "events_backfill_state.json")
SINCE = dt.date(2008, 10, 31)
COUNTRIES = ("NO", "SE", "DK", "FI", "IS", "FO", "GL", "AX")
TYPES = ("conference", "meetup", "hackathon", "seminar")
# Facts that need their own credit when the field is non-empty.
FACT_FIELDS = (
    "title", "start", "end", "place", "city", "country", "organiser", "url",
    "event_type", "language", "videos_url", "speakers_count",
)


def stable_id(url, start, title):
    """Same recipe as events.eid: url without query, start date, lowercased title."""
    bare = (url or "").split("?")[0]
    day = ""
    if isinstance(start, dt.datetime):
        day = start.date().isoformat()
    elif isinstance(start, dt.date):
        day = start.isoformat()
    elif start:
        day = str(start)[:10]
    text = f"{bare}|{day}|{(title or '').lower()}"
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def _empty(value):
    return value is None or value == "" or value == [] or value == {}


def _credit_problems(credit, label):
    if not isinstance(credit, dict):
        return [f"{label} credit missing"]
    url = (credit.get("source_url") or credit.get("url") or "").strip()
    name = (credit.get("source_name") or credit.get("name") or "").strip()
    when = credit.get("retrieved_at") or credit.get("retrieved")
    out = []
    if not name:
        out.append(f"{label} credit has no source name")
    if not url.startswith("http://") and not url.startswith("https://"):
        out.append(f"{label} credit has no source URL")
    elif event_block.host_blocked(event_block.host_of(url)):
        out.append(f"{label} credit is a predatory listing")
    if not when:
        out.append(f"{label} credit has no retrieved_at")
    else:
        try:
            dt.datetime.fromisoformat(str(when))
        except ValueError:
            out.append(f"{label} retrieved_at is not a time")
    return out


def row_problems(row):
    """Reasons this row must not be published. Empty means it can be shown."""
    if not isinstance(row, dict):
        return ["row is not an object"]
    out = []
    if row.get("source") != "backfill" or row.get("backfill") is not True:
        out.append("not marked backfill")
    if event_block.blocked_event(row):
        out.append("predatory listing")
    title = row.get("title") or ""
    url = row.get("url") or ""
    start_raw = row.get("start")
    if not title.strip():
        out.append("title missing")
    if not url.startswith("http://") and not url.startswith("https://"):
        out.append("official link missing")
    if row.get("country") not in COUNTRIES:
        out.append("country is not a Nordic code")
    if row.get("event_type") not in TYPES:
        out.append("event type missing")
    if not (row.get("organiser") or "").strip():
        out.append("organiser missing")
    if row.get("status") != "published":
        out.append("status is not published")
    start = event_select.start_of(row) if start_raw else None
    if start is None:
        out.append("start missing")
    else:
        if start.date() < SINCE:
            out.append("before 31 Oct 2008")
        expect = stable_id(url, start, title)
        if row.get("id") != expect:
            out.append(f"id is not stable ({expect})")
    end = event_select.end_of(row)
    if start and end and end < start:
        out.append("end before start")
    if row.get("online") not in (True, False):
        out.append("online flag missing")
    attendees = row.get("attendees")
    if not _empty(attendees):
        if event_select.attendees_fact({"attendees": attendees}) is None:
            out.append("attendee count is not an exact credited integer")
        else:
            out.extend(_credit_problems((row.get("credits") or {}).get("attendees"), "attendees"))
    speakers = row.get("speakers_count")
    if not _empty(speakers) and event_select.as_count(speakers) is None:
        out.append("speaker count is not an exact integer")
    credits = row.get("credits") or {}
    if not isinstance(credits, dict):
        return out + ["credits missing"]
    for field in FACT_FIELDS:
        if _empty(row.get(field)):
            continue
        out.extend(_credit_problems(credits.get(field), field))
    if row.get("online") is True:
        out.extend(_credit_problems(credits.get("online"), "online"))
    out.extend(event_description.problems(row))
    return out


def load_events(path=None):
    """Load and refuse the file when a row breaks the rules."""
    path = path or DATA_PATH
    if not os.path.exists(path):
        return []
    data = json.load(open(path, encoding="utf-8"))
    rows = data.get("events") or []
    problems = []
    seen = set()
    for i, row in enumerate(rows):
        ident = row.get("id") or f"row {i}"
        for problem in row_problems(row):
            problems.append(f"{ident}: {problem}")
        if row.get("id") in seen:
            problems.append(f"{ident}: duplicate id")
        seen.add(row.get("id"))
    if problems:
        raise ValueError("events_backfill.json: " + "; ".join(problems[:20]))
    return rows


def previous_events(now=None):
    """Backfill rows that have already finished. Upcoming and ongoing stay out."""
    now = event_select.clock(now)
    out = []
    for raw in load_events():
        if event_select.classify(raw, now) != "previous":
            continue
        row = dict(raw)
        row["past"] = True
        row["status"] = "published"
        out.append(row)
    return out


def merge_previous(calendar_previous, now=None):
    """Calendar finished events plus backfill, newest finish first. No duplicates."""
    skip = {e.get("id") for e in calendar_previous or [] if e.get("id")}
    extra = [e for e in previous_events(now) if e.get("id") not in skip]
    rows = list(calendar_previous or []) + extra
    rows.sort(
        key=lambda e: (
            event_select.end_of(e) or event_select.start_of(e) or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
            e.get("id") or "",
        ),
        reverse=True,
    )
    return rows


def display_credit(event, field):
    raw = (event.get("credits") or {}).get(field) or {}
    return event_select.credit_block(
        raw.get("source_name") or raw.get("name"),
        raw.get("source_url") or raw.get("url"),
        raw.get("retrieved_at") or raw.get("retrieved"),
    )


def speakers_fact(event):
    count = event_select.as_count(event.get("speakers_count")) if isinstance(event, dict) else None
    if count is None:
        return None
    credit = display_credit(event, "speakers_count")
    if not credit:
        return None
    return {"count": count, "credit": credit}


def videos_fact(event):
    if not isinstance(event, dict):
        return None
    url = (event.get("videos_url") or "").strip()
    if not url:
        return None
    credit = display_credit(event, "videos_url")
    if not credit:
        return None
    return {"url": url, "credit": credit}


def counts(rows=None):
    """Counts by country and by year for the run report."""
    rows = load_events() if rows is None else rows
    by_country = {c: 0 for c in COUNTRIES}
    by_year = {}
    by_country_year = {c: {} for c in COUNTRIES}
    for row in rows:
        country = row.get("country")
        year = str(row.get("start") or "")[:4]
        if country in by_country:
            by_country[country] += 1
            by_country_year[country][year] = by_country_year[country].get(year, 0) + 1
        by_year[year] = by_year.get(year, 0) + 1
    return {"events": len(rows), "by_country": by_country, "by_year": by_year, "by_country_year": by_country_year}


def main():
    rows = load_events()
    report = counts(rows)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
