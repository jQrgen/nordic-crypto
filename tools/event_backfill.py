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

Talks are linked on every run. Each talk in data/talks.json is matched to an
existing calendar or backfill event on series, date span, city, country and
organiser. When none matches, a previous event is created from facts the
talk's own page stated (name, day, city, country, venue, organiser, official
URL). A talk that cannot be dated or placed stays unlinked with unlink_reason.
The link is stored both ways: talk.event_id and event.talk_ids.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import event_block  # noqa: E402
import event_description  # noqa: E402
import event_select  # noqa: E402

DATA_PATH = os.path.join(ROOT, "data", "events_backfill.json")
STATE_PATH = os.path.join(ROOT, "data", "events_backfill_state.json")
TALKS_PATH = os.path.join(ROOT, "data", "talks.json")
CALENDAR_PATH = os.path.join(ROOT, "data", "events.json")
SINCE = dt.date(2008, 10, 31)
# Date-only rows use midnight to 23:59 in the event country's offset.
COUNTRY_TZ = {
    "NO": "Europe/Oslo",
    "SE": "Europe/Stockholm",
    "DK": "Europe/Copenhagen",
    "FI": "Europe/Helsinki",
    "IS": "Atlantic/Reykjavik",
    "FO": "Atlantic/Faroe",
    "GL": "America/Nuuk",
    "AX": "Europe/Mariehamn",
}
# Uploaders that are a person or a channel, not the event organiser.
_PERSONAL_CHANNELS = {
    "aantonop",
    "jørgen svennevik notland",
    "vinay gupta",
    "vedran maslic",
    "sheikki hassan",
    "daavern",
    "concordium",
    "thinklair",
    "bitspace",
    "bitcoin magazine",
    "incitement",
    "bitjoin studios",
    "the cryptoverse",
}
_ORG_MARKERS = (
    "association", "foundation", "university", "universitet", "bank", "pankki",
    "forening", "society", "forum", "meetup", "conference", "riksbank",
    "polyteknisk", "institute", "institutt", "museum", "museo", "summit",
    "festival", "school", "laboratory", "house of",
)
REASON_DAY = "the video page did not state the day"
REASON_CITY = "the video page did not state the city"
REASON_COUNTRY = "the video page did not state the country"
REASON_NAME = "the video page did not name the event"
REASON_TYPE = "the video page did not state the event type"
REASON_ORGANISER = "the video page did not name the organiser"
REASON_PREDATORY = "the official link is a predatory conference listing"
REASON_AMBIGUOUS = "more than one event matches"
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


def series_key(name):
    """Event series: lowercased, year numbers removed, punctuation folded to spaces."""
    text = (name or "").casefold()
    text = re.sub(r"\b(?:19|20)\d{2}\b", " ", text)
    text = re.sub(r"[^0-9a-zæøåäöéíýþð]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def event_type_of(name):
    """Type word the event name itself uses. None when the name does not say."""
    text = (name or "").casefold()
    if "hackathon" in text:
        return "hackathon"
    if "meetup" in text:
        return "meetup"
    if any(word in text for word in ("seminar", "summer school", "lecture", "fyrirlestur")):
        return "seminar"
    if any(word in text for word in ("conference", "summit", "forum", "festival", "slush", "internetdagarna", "blockchain day")):
        return "conference"
    return None


def _http(url):
    text = (url or "").strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return ""


def _usable_url(url):
    """An http(s) URL that is not a predatory conference listing."""
    text = _http(url)
    if not text:
        return ""
    if event_block.host_blocked(event_block.host_of(text)):
        return ""
    return text


def meetup_organiser(url):
    """Organiser named by a meetup.com group slug. None for other hosts."""
    match = re.search(r"(?i)meetup\.com/([^/?#]+)", url or "")
    if not match:
        return None
    slug = match.group(1)
    if slug.casefold() in {"events", "find", "cities"}:
        return None
    parts = [part for part in re.split(r"[-_]+", slug) if part]
    if not parts:
        return None
    return " ".join(part[:1].upper() + part[1:] for part in parts)


def channel_organiser(channel):
    """Channel name when it is an organisation. A person or a bare handle is not."""
    if not isinstance(channel, str):
        return None
    name = channel.split("*", 1)[0].strip()
    if not name or name.casefold() in _PERSONAL_CHANNELS:
        return None
    if event_block._name_blocked(name):
        return None
    folded = name.casefold()
    if any(marker in folded for marker in _ORG_MARKERS):
        return name
    words = name.split()
    if len(words) == 1 and not name.islower() and not name.isupper():
        return name
    return None


def talk_organiser(talk):
    """Organiser the talk page states: the meetup group, else an organisational channel."""
    named = meetup_organiser(_usable_url(talk.get("event_url")))
    if named and not event_block._name_blocked(named):
        return named
    return channel_organiser(talk.get("channel"))


def _day(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _retrieved(value):
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt.datetime.fromisoformat(text)
    except ValueError:
        return ""
    return text


def _covers(event, day):
    start = event_select.start_of(event)
    if start is None or day is None:
        return False
    end = event_select.end_of(event) or start
    return start.date() <= day <= end.date()


def _org_agree(talk_org, event_org):
    left = (talk_org or "").casefold().strip()
    right = (event_org or "").casefold().strip()
    if not left or not right:
        return True
    return left == right or left in right or right in left


def _match_event(talk, events):
    """Existing event with the same series, day inside its span, city, country and organiser."""
    name = series_key(talk.get("event_name"))
    day = _day(talk.get("date"))
    city = (talk.get("city") or "").casefold().strip()
    country = (talk.get("country") or "").strip()
    if not name or day is None or not city or country not in COUNTRIES:
        return None, []
    hits = []
    for event in events:
        if series_key(event.get("title")) != name:
            continue
        if not _covers(event, day):
            continue
        if (event.get("country") or "").strip() != country:
            continue
        event_city = (event.get("city") or "").casefold().strip()
        if not event_city or event_city != city:
            continue
        if not _org_agree(talk_organiser(talk), event.get("organiser")):
            continue
        hits.append(event)
    if len(hits) == 1:
        return hits[0], hits
    return None, hits


def _gap_reason(talk):
    """Why this talk cannot become an event. None when the page stated enough."""
    if _day(talk.get("date")) is None:
        return REASON_DAY
    if not (talk.get("city") or "").strip():
        return REASON_CITY
    if (talk.get("country") or "").strip() not in COUNTRIES:
        return REASON_COUNTRY
    if not (talk.get("event_name") or "").strip():
        return REASON_NAME
    if event_type_of(talk.get("event_name")) is None:
        return REASON_TYPE
    if not talk_organiser(talk):
        return REASON_ORGANISER
    official = _usable_url(talk.get("event_url")) or _usable_url(talk.get("video_url"))
    credit = _usable_url(talk.get("source_url")) or official
    if not official or not credit:
        if _http(talk.get("event_url")) or _http(talk.get("video_url")) or _http(talk.get("source_url")):
            return REASON_PREDATORY
        return REASON_ORGANISER
    return None


def _local_bounds(day, country):
    zone = ZoneInfo(COUNTRY_TZ[country])
    start = dt.datetime(day.year, day.month, day.day, 0, 0, tzinfo=zone)
    end = dt.datetime(day.year, day.month, day.day, 23, 59, tzinfo=zone)
    return start.isoformat(), end.isoformat()


def _credit(name, url, when):
    return {"source_name": name, "source_url": url, "retrieved_at": when}


def _build_event(talks):
    """One previous event from talks that share a series, day and place. None when a fact is missing."""
    if any(_gap_reason(talk) for talk in talks):
        return None
    title = sorted({(talk.get("event_name") or "").strip() for talk in talks}, key=lambda n: (len(n), n))[0]
    day = _day(talks[0].get("date"))
    country = talks[0].get("country")
    city = (talks[0].get("city") or "").strip()
    kind = event_type_of(title)
    organiser = talk_organiser(talks[0])
    ranked = sorted(talks, key=lambda talk: (_retrieved(talk.get("retrieved_at")) or "9999", talk.get("id") or ""))
    source = ranked[0]
    credit_url = _usable_url(source.get("source_url")) or _usable_url(source.get("video_url"))
    official = ""
    for talk in ranked:
        official = _usable_url(talk.get("event_url"))
        if official:
            break
    if not official:
        official = _usable_url(source.get("video_url")) or credit_url
    when = _retrieved(source.get("retrieved_at"))
    source_name = (source.get("channel") or organiser or "").split("*", 1)[0].strip()
    if not (title and day and city and kind and organiser and official and credit_url and when and source_name):
        return None
    if event_block.host_blocked(event_block.host_of(official)) or event_block.host_blocked(event_block.host_of(credit_url)):
        return None
    if event_block._name_blocked(organiser) or event_block._name_blocked(source_name):
        return None
    start, end = _local_bounds(day, country)
    credit = _credit(source_name, credit_url, when)
    fields = ("title", "start", "end", "city", "country", "organiser", "url", "event_type")
    row = {
        "title": title,
        "start": start,
        "end": end,
        "place": None,
        "city": city,
        "country": country,
        "online": False,
        "organiser": organiser,
        "url": official,
        "source": "backfill",
        "source_url": credit_url,
        "found": when,
        "event_type": kind,
        "language": None,
        "status": "published",
        "backfill": True,
        "attendees": None,
        "speakers_count": None,
        "videos_url": None,
        "talk_ids": sorted(talk.get("id") for talk in talks if talk.get("id")),
        "credits": {field: dict(credit) for field in fields},
        "id": stable_id(official, start, title),
    }
    if row_problems(row):
        return None
    return row


def _stamp(talk, event_id, reason):
    """event_id and calendar_event_id stay equal. unlink_reason is set only when unlinked."""
    ordered = {}
    for key, value in talk.items():
        if key in ("event_id", "unlink_reason"):
            continue
        if key == "calendar_event_id":
            ordered["calendar_event_id"] = event_id
            ordered["event_id"] = event_id
            ordered["unlink_reason"] = reason
            continue
        ordered[key] = value
    if "event_id" not in ordered:
        ordered["calendar_event_id"] = event_id
        ordered["event_id"] = event_id
        ordered["unlink_reason"] = reason
    return ordered


def link_talks(talks, calendar, backfill):
    """Match talks onto events, creating a previous event when the page stated enough.

    Returns new lists. Does not write files. Existing events are copied. talk_ids
    is set only when at least one talk links.
    """
    talks = [dict(talk) for talk in talks or [] if isinstance(talk, dict)]
    calendar = [dict(event) for event in calendar or [] if isinstance(event, dict)]
    backfill = [dict(event) for event in backfill or [] if isinstance(event, dict)]
    for event in calendar + backfill:
        event.pop("talk_ids", None)
    original_ids = {event.get("id") for event in calendar + backfill if event.get("id")}
    pending = []
    ambiguous = []
    for talk in talks:
        hit, hits = _match_event(talk, calendar + backfill)
        if hit is not None:
            talk["_link"] = hit.get("id")
        elif len(hits) > 1:
            ambiguous.append(talk)
        else:
            pending.append(talk)
    groups = {}
    skipped = []
    for talk in pending:
        reason = _gap_reason(talk)
        if reason:
            skipped.append((talk, reason))
            continue
        key = (
            series_key(talk.get("event_name")),
            talk.get("date"),
            (talk.get("country") or "").strip(),
            (talk.get("city") or "").casefold().strip(),
            (talk_organiser(talk) or "").casefold(),
        )
        groups.setdefault(key, []).append(talk)
    created = []
    for key in sorted(groups):
        bunch = sorted(groups[key], key=lambda talk: talk.get("id") or "")
        row = _build_event(bunch)
        if row is None:
            for talk in bunch:
                skipped.append((talk, _gap_reason(talk) or REASON_TYPE))
            continue
        existing = next((event for event in calendar + backfill if event.get("id") == row["id"]), None)
        if existing is None:
            backfill.append(row)
            created.append(row)
            target = row["id"]
        else:
            target = existing["id"]
        for talk in bunch:
            talk["_link"] = target
    by_id = {}
    for event in calendar + backfill:
        if event.get("id"):
            by_id[event["id"]] = event
    reason_for = {id(talk): reason for talk, reason in skipped}
    for talk in ambiguous:
        reason_for[id(talk)] = REASON_AMBIGUOUS
    stamped = []
    reasons = {}
    for talk in talks:
        reason = reason_for.get(id(talk))
        event_id = talk.pop("_link", None)
        if reason or not event_id or event_id not in by_id:
            reason = reason or REASON_DAY
            reasons.setdefault(reason, []).append(talk.get("id"))
            stamped.append(_stamp(talk, None, reason))
            continue
        bucket = by_id[event_id].setdefault("talk_ids", [])
        if talk.get("id") and talk["id"] not in bucket:
            bucket.append(talk["id"])
        stamped.append(_stamp(talk, event_id, None))
    for event in calendar + backfill:
        if event.get("talk_ids"):
            event["talk_ids"] = sorted(set(event["talk_ids"]))
    linked_existing = [talk.get("id") for talk in stamped if talk.get("event_id") in original_ids]
    on_new = [talk.get("id") for talk in stamped if talk.get("event_id") and talk.get("event_id") not in original_ids]
    report = {
        "linked_existing": len(linked_existing),
        "created_events": len(created),
        "talks_on_new": len(on_new),
        "unlinked": sum(len(ids) for ids in reasons.values()),
        "reasons": {reason: ids for reason, ids in reasons.items()},
    }
    return stamped, calendar, backfill, report


def _indent_run(run):
    blob = json.dumps(run, ensure_ascii=False, indent=1)
    return "\n".join("  " + line for line in blob.split("\n"))


def _write_state(run):
    """Append or replace the talk-link run without reformatting earlier runs."""
    raw = open(STATE_PATH, encoding="utf-8").read()
    blob = _indent_run(run)
    marker = '\n  {\n   "kind": "talk-links"'
    if marker in raw:
        head = raw[:raw.rfind(marker)].rstrip().rstrip(",")
    else:
        stripped = raw.rstrip()
        suffix = "\n ]\n}"
        if not stripped.endswith(suffix):
            raise ValueError("events_backfill_state.json: runs list is not at the end of the file")
        head = stripped[:-len(suffix)].rstrip()
    text = head + ",\n" + blob + "\n ]\n}\n"
    loaded = json.loads(text)
    if loaded["runs"][-1].get("kind") != "talk-links":
        raise ValueError("events_backfill_state.json: talk-link run was not appended")
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        handle.write(text)


def _dump(path, data, newline=True):
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if newline:
        text += "\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def apply_links():
    """Write talk.event_id and event.talk_ids. Creates missing previous events."""
    talks_doc = json.load(open(TALKS_PATH, encoding="utf-8"))
    calendar_doc = json.load(open(CALENDAR_PATH, encoding="utf-8"))
    back_doc = json.load(open(DATA_PATH, encoding="utf-8"))
    state = json.load(open(STATE_PATH, encoding="utf-8"))
    stamped, calendar, backfill, report = link_talks(
        talks_doc.get("talks") or [],
        calendar_doc.get("events") or [],
        back_doc.get("events") or [],
    )
    talks_doc["talks"] = stamped
    _dump(TALKS_PATH, talks_doc, newline=True)
    back_doc["events"] = backfill
    raw_back = open(DATA_PATH, encoding="utf-8").read()
    _dump(DATA_PATH, back_doc, newline=raw_back.endswith("\n"))
    before = json.dumps(json.load(open(CALENDAR_PATH, encoding="utf-8")).get("events"), ensure_ascii=False, sort_keys=True)
    after = json.dumps(calendar, ensure_ascii=False, sort_keys=True)
    if before != after:
        calendar_doc["events"] = calendar
        raw_cal = open(CALENDAR_PATH, encoding="utf-8").read()
        _dump(CALENDAR_PATH, calendar_doc, newline=raw_cal.endswith("\n"))
    totals = counts(backfill)
    previous = next((item for item in state.get("runs") or [] if item.get("rejected")), {})
    rejected = previous.get("rejected") or [
        {"host": "waset.org", "reason": "Predatory conference listing. Not a source."},
        {"host": "internationalconferencealerts.com", "reason": "Predatory conference listing. Not a source."},
    ]
    created_rows = [row for row in backfill if row.get("id") not in {
        item.get("id") for item in (json.loads(raw_back).get("events") or [])
    }]
    run = {
        "kind": "talk-links",
        "retrieved_at": "2026-10-07T22:40:00+00:00",
        "included": totals["events"],
        "by_country": totals["by_country"],
        "by_year": totals["by_year"],
        "by_country_year": totals["by_country_year"],
        "years_with_events": sorted(int(year) for year in totals["by_year"]),
        "note": (
            "Talks are matched to an existing calendar or backfill event first "
            "(series, date span, city, country and organiser). When none matches, "
            "a previous event is created from facts the video page stated: name, day, "
            "city, country, venue, organiser and official URL. A talk with no day or "
            "no place stays unlinked with unlink_reason. Predatory conference listings are not sources."
        ),
        "talks": {
            "linked_existing": report["linked_existing"],
            "created_events": report["created_events"],
            "talks_on_new": report["talks_on_new"],
            "unlinked": report["unlinked"],
            "unlinked_reasons": {reason: len(ids) for reason, ids in report["reasons"].items()},
        },
        "queries": sorted({row.get("source_url") for row in created_rows if row.get("source_url")}),
        "sources_used": sorted({(row.get("credits") or {}).get("title", {}).get("source_name") for row in created_rows if (row.get("credits") or {}).get("title", {}).get("source_name")}),
        "rejected": rejected,
    }
    _write_state(run)
    report["counts"] = {"events": totals["events"], "by_country": totals["by_country"], "by_year": totals["by_year"]}
    return report


def main():
    report = apply_links()
    public = {
        "linked_existing": report["linked_existing"],
        "created_events": report["created_events"],
        "talks_on_new": report["talks_on_new"],
        "unlinked": report["unlinked"],
        "reasons": {reason: ids for reason, ids in report["reasons"].items()},
        "counts": report["counts"],
    }
    print(json.dumps(public, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
