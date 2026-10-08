"""One page per event at /calendar/<id>/ in every site language.

The id is the existing 12-hex event id. Facts are only the ones already stored.
A map link is a search for the stored place or city. No coordinates are added.
Talk videos come from the event row or from data/talks.json when that file
names this event. This module does not write talks data.
"""
import datetime as dt
import json
import os
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TALKS_PATH = os.path.join(ROOT, "data", "talks.json")

# English names for a map search. The page still shows the translated country.
MAP_COUNTRY = {
    "NO": "Norway", "SE": "Sweden", "DK": "Denmark", "FI": "Finland", "IS": "Iceland",
    "FO": "Faroe Islands", "GL": "Greenland", "AX": "Åland",
}


def slug(event):
    """Site path under a language: calendar/<id>."""
    return "calendar/" + (event.get("id") or "")


def offset_label(iso):
    """UTC±HH:MM from the stored timestamp. Empty when the value has no offset."""
    if not iso:
        return ""
    try:
        d = dt.datetime.fromisoformat(str(iso))
    except ValueError:
        return ""
    if d.tzinfo is None or d.utcoffset() is None:
        return ""
    minutes = int(d.utcoffset().total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    return f"UTC{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def map_query(event):
    """Place and city as stored, plus the country name. Empty when neither place nor city is set."""
    if not isinstance(event, dict):
        return ""
    place = (event.get("place") or "").strip()
    city = (event.get("city") or "").strip()
    parts = []
    if place:
        parts.append(place)
    if city and city not in place:
        parts.append(city)
    if not parts:
        return ""
    country = MAP_COUNTRY.get(event.get("country") or "")
    if country and country not in " ".join(parts):
        parts.append(country)
    return ", ".join(parts)


def map_url(event):
    query = map_query(event)
    if not query or event.get("online") and not (event.get("place") or event.get("city")):
        return None
    if not query:
        return None
    return "https://www.openstreetmap.org/search?query=" + urllib.parse.quote(query)


def topics(event):
    """Topic labels only when the row credits them. No labels are guessed from the title."""
    if not isinstance(event, dict):
        return []
    credit = (event.get("credits") or {}).get("topics") or event.get("topics_source")
    if not isinstance(credit, dict) or not (credit.get("source_url") or credit.get("url")):
        return []
    raw = event.get("topics") or event.get("tags") or []
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()]


def _talk_url(row):
    if not isinstance(row, dict):
        return ""
    for key in ("video_url", "videos_url"):
        if isinstance(row.get(key), str) and row[key].startswith("http"):
            return row[key].strip()
    video = row.get("video")
    if isinstance(video, dict):
        url = video.get("url") or ""
        if isinstance(url, str) and url.startswith("http"):
            return url.strip()
    if isinstance(video, str) and video.startswith("http"):
        return video.strip()
    return ""


def _talk_event_id(row):
    if not isinstance(row, dict):
        return ""
    return str(row.get("event_id") or row.get("calendar_event_id") or row.get("event") or "").strip()


def related_talks(event_id, path=None):
    """Talk videos that name this event. Missing file means there are none."""
    path = path or TALKS_PATH
    if not event_id or not os.path.exists(path):
        return []
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("talks") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if _talk_event_id(row) != event_id:
            continue
        url = _talk_url(row)
        if not url:
            continue
        item = {"title": (row.get("title") or "").strip(), "url": url}
        source = (row.get("source_url") or row.get("source") or "").strip()
        if isinstance(row.get("source_url"), str) and row["source_url"].startswith("http"):
            item["source_url"] = row["source_url"].strip()
        elif source.startswith("http"):
            item["source_url"] = source
        name = row.get("source_name") or row.get("credit")
        if isinstance(name, str) and name.strip():
            item["source_name"] = name.strip()
        when = row.get("retrieved_at") or row.get("retrieved")
        if when:
            item["retrieved"] = when
        speakers = [s.strip() for s in (row.get("speakers") or []) if isinstance(s, str) and s.strip()]
        if speakers:
            item["speakers"] = speakers
        speaker_ids = [s.strip() for s in (row.get("speaker_ids") or []) if isinstance(s, str) and s.strip()]
        if speaker_ids:
            item["speaker_ids"] = speaker_ids
        out.append(item)
    return out


def jsonld(event, page_url, description=None):
    """schema.org Event from stored fields. Unsourced extras are left out."""
    name = event.get("title") or ""
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": name,
        "startDate": event.get("start"),
        "url": page_url,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode" if event.get("online") else "https://schema.org/OfflineEventAttendanceMode",
    }
    if event.get("end"):
        data["endDate"] = event["end"]
    if description:
        data["description"] = description
    if event.get("url"):
        data["sameAs"] = event["url"]
    if event.get("organiser"):
        data["organizer"] = {"@type": "Organization", "name": event["organiser"]}
    place = (event.get("place") or "").strip()
    city = (event.get("city") or "").strip()
    if event.get("online") and not place and not city and event.get("url"):
        data["location"] = {"@type": "VirtualLocation", "url": event["url"]}
    elif place or city:
        loc = {"@type": "Place", "name": place or city}
        address = {}
        if city:
            address["addressLocality"] = city
        if event.get("country"):
            address["addressCountry"] = event["country"]
        if address:
            address["@type"] = "PostalAddress"
            loc["address"] = address
        data["location"] = loc
    if event.get("paid") is False:
        data["isAccessibleForFree"] = True
    elif event.get("paid") is True:
        data["isAccessibleForFree"] = False
    if event.get("language"):
        data["inLanguage"] = event["language"]
    return data
