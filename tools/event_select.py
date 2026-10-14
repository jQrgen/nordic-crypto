"""Stable event windows for the front page and the previous-events page.

The clock is Europe/Oslo. Each event keeps the offset it was stored with, so a
Helsinki or Reykjavík time is the same instant the organiser published.
Comparisons use those instants, not a sliding window or a shuffled sample.

Upcoming on the front page means "has not started". The list is the next
FRONT_LIMIT events by start, then id. It changes only when an event's start
passes: that event leaves, and the next one moves in. While it is running
(start <= now <= end) it is ongoing, not upcoming and not past. When it ends
it is previous. The public name for previous is the phase "past".

An event with no stored end is still ongoing until an assumed end: a midnight
start (hour, minute and second all 0) runs until 23:59 that local day, and
every other start runs for DEFAULT_HOURS hours. The stored end is never
rewritten; the assumed instant is phase_end. All-day rows stored as
00:00–23:59 local stay ongoing for that whole local day. Multi-day rows stay
ongoing until their end instant.

The same inputs and the same now always produce the same lists.
"""
import datetime as dt
from zoneinfo import ZoneInfo

OSLO = ZoneInfo("Europe/Oslo")
FRONT_LIMIT = 6
# When the organiser did not publish an end. Midnight starts run until 23:59 instead.
DEFAULT_HOURS = 3

# Explicit registered-count fields. Capacity and "spots left" are not a count
# of people who registered, so they are never used and never subtracted.
COUNT_KEYS = (
    "attendeeCount", "attendeesCount", "registeredAttendeeCount",
    "rsvpCount", "yesRsvpCount", "yes_rsvp_count",
    "guestCount", "guest_count", "num_attendees", "numAttendees",
    "ticketsSold", "quantity_sold", "quantitySold",
)
ICS_COUNT_KEYS = (
    "X-GUEST-COUNT", "X-LUMA-GUEST-COUNT", "X-ATTENDEE-COUNT",
    "X-NUM-GUESTS", "X-NUM-ATTENDEES",
)


def aware(value):
    """ISO string or datetime -> aware datetime. Naive values are read as Oslo local."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        d = value
    else:
        d = dt.datetime.fromisoformat(str(value))
    if d.tzinfo is None:
        d = d.replace(tzinfo=OSLO)
    return d


def clock(now=None):
    """Aware instant in Europe/Oslo. `now` may be aware, naive (Oslo), or None (the clock)."""
    if now is None:
        now = dt.datetime.now(OSLO)
    return aware(now).astimezone(OSLO)


def start_of(event):
    return aware(event.get("start")) if event else None


def end_of(event):
    """Stored end instant, or None. Never invented from the start."""
    if not event or not event.get("end"):
        return None
    return aware(event.get("end"))


def effective_end(event):
    """End of the ongoing window: the stored end, or an assumed end when it is missing.

    A midnight start runs until 23:59 that local day. Any other start runs for
    DEFAULT_HOURS. The stored end field is not changed.
    """
    stored = end_of(event)
    if stored is not None:
        return stored
    start = start_of(event)
    if start is None:
        return None
    if start.hour == 0 and start.minute == 0 and start.second == 0:
        return start.replace(hour=23, minute=59, second=0, microsecond=0)
    return start + dt.timedelta(hours=DEFAULT_HOURS)


def sort_key(event):
    start = start_of(event) or dt.datetime.max.replace(tzinfo=dt.timezone.utc)
    return (start, event.get("id") or "")


def as_count(value):
    """A non-negative integer count, or None. Booleans and estimates are refused."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0 and value == int(value):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def explicit_attendee_count(obj):
    """Registered participants only when the object states a count. Capacity is ignored."""
    if not isinstance(obj, dict):
        return None
    for key in COUNT_KEYS:
        n = as_count(obj.get(key))
        if n is not None:
            return n
    return None


def explicit_ics_count(fields):
    if not isinstance(fields, dict):
        return None
    for key in ICS_COUNT_KEYS:
        n = as_count(fields.get(key))
        if n is not None:
            return n
    return None


def phase(event, now=None):
    """'upcoming', 'ongoing', 'past', or None when the row has no start.

    Ongoing is start <= now <= the effective end, including the start and end instants.
    """
    now = clock(now)
    start = start_of(event)
    if start is None:
        return None
    if start > now:
        return "upcoming"
    end = effective_end(event)
    if end is not None and start <= now <= end:
        return "ongoing"
    return "past"


def classify(event, now=None):
    """'upcoming', 'ongoing', 'previous', or 'skip' (no start).

    'previous' is the internal name for the public phase 'past'.
    """
    kind = phase(event, now)
    if kind is None:
        return "skip"
    if kind == "past":
        return "previous"
    return kind


def annotate(event, now=None):
    """Clock fields for one row: phase, phase_end, past, ongoing. Does not copy the event."""
    kind = phase(event, now)
    end = effective_end(event)
    return {
        "phase": kind,
        "phase_end": end.isoformat() if end else None,
        "past": kind == "past",
        "ongoing": kind == "ongoing",
    }


def partition(events, now=None, limit=FRONT_LIMIT):
    """Split events. Upcoming is capped at `limit` but `upcoming_rest` keeps the overflow, in order."""
    now = clock(now)
    rows = sorted((e for e in events or [] if e.get("start")), key=sort_key)
    ongoing, upcoming, previous = [], [], []
    for event in rows:
        kind = classify(event, now)
        if kind == "ongoing":
            ongoing.append(event)
        elif kind == "upcoming":
            upcoming.append(event)
        elif kind == "previous":
            previous.append(event)
    previous.sort(key=lambda e: ((effective_end(e) or start_of(e)), e.get("id") or ""), reverse=True)
    return {
        "now": now,
        "ongoing": ongoing,
        "upcoming": upcoming[:limit],
        "upcoming_rest": upcoming[limit:],
        "previous": previous,
    }


def credit_block(name, url, retrieved):
    name = (name or "").strip()
    url = (url or "").strip()
    if not name or not url:
        return None
    block = {"name": name, "url": url}
    if retrieved:
        block["retrieved"] = retrieved
    return block


def place_credit(event):
    """Credit for the venue/online fact. Existing source, source_url, url and found are enough."""
    if not isinstance(event, dict):
        return None
    stored = event.get("place_source")
    if isinstance(stored, dict):
        block = credit_block(stored.get("name") or stored.get("source_name"), stored.get("url") or stored.get("source_url"), stored.get("retrieved"))
        if block:
            return block
    return credit_block(event.get("source"), event.get("source_url") or event.get("url"), event.get("found"))


def location_fact(event):
    """Venue, city and online flag, only when a source can be named. No guessed address."""
    if not isinstance(event, dict):
        return None
    credit = place_credit(event)
    if not credit:
        return None
    place = (event.get("place") or "").strip()
    city = (event.get("city") or "").strip()
    parts = []
    if place:
        parts.append(place)
    if city and city not in place:
        parts.append(city)
    online = bool(event.get("online"))
    if not parts and not online:
        return None
    return {"text": ", ".join(parts), "online": online, "credit": credit}


def attendees_fact(event):
    """Registered count plus its own source. Missing or uncredited counts are omitted."""
    if not isinstance(event, dict):
        return None
    raw = event.get("attendees")
    if not isinstance(raw, dict):
        return None
    count = as_count(raw.get("count"))
    if count is None:
        return None
    credit = credit_block(
        raw.get("source_name") or raw.get("name"),
        raw.get("source_url") or raw.get("url"),
        raw.get("retrieved"),
    )
    if not credit:
        return None
    return {"count": count, "credit": credit}
