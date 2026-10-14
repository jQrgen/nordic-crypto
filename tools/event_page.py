"""One page per event at /calendar/<id>/ in every site language.

The id is the existing 12-hex event id. Facts are only the ones already stored.
A map link searches the stored place or city, or stored coordinates when the
row has them. Nothing is geocoded. The page href is Google Maps so the link
works without JavaScript; Apple devices are sent to Apple Maps by a small
inline script. Talk videos come from the event row or from data/talks.json
when that file names this event. This module does not write talks data.
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

# Copied onto the built event when the row stores them. Empty values are left out.
COORD_KEYS = ("lat", "lng", "lon", "latitude", "longitude", "geo", "coordinates")

# Swaps map links to Apple Maps on iOS, iPadOS and macOS. The href stays Google Maps
# when this does not run. iPadOS reports a Mac user agent and platform, so both are checked.
APPLE_MAP_SCRIPT = (
    "<script>(function(){var ua=navigator.userAgent||\"\",p=navigator.platform||\"\";"
    "if(!/Mac|iPhone|iPad|iPod/.test(ua)&&!/Mac|iPhone|iPad|iPod/.test(p))return;"
    "var as=document.querySelectorAll(\"a[data-apple-map]\");"
    "for(var i=0;i<as.length;i++){var u=as[i].getAttribute(\"data-apple-map\");if(u)as[i].href=u}"
    "})();</script>"
)


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


def _num(value):
    """A finite float from a stored number or numeric string. None when it is not a number."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        n = float(value)
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        try:
            n = float(s)
        except ValueError:
            return None
    else:
        return None
    if n != n or abs(n) == float("inf"):
        return None
    return n


def _pair(value):
    """(lat, lng) fields from a dict, a two-item list, or a 'lat,lng' string."""
    if isinstance(value, dict):
        return value.get("lat", value.get("latitude")), value.get("lng", value.get("lon", value.get("longitude")))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return value[0], value[1]
    if isinstance(value, str) and "," in value:
        lat, lng = value.split(",", 1)
        return lat, lng
    return None, None


def map_coords(event):
    """Stored latitude and longitude, or None. No coordinates are looked up."""
    if not isinstance(event, dict):
        return None
    lat = event.get("lat", event.get("latitude"))
    lng = event.get("lng", event.get("lon", event.get("longitude")))
    if lat is None or lng is None:
        for key in ("geo", "coordinates"):
            la, lo = _pair(event.get(key))
            if lat is None:
                lat = la
            if lng is None:
                lng = lo
    la, lo = _num(lat), _num(lng)
    if la is None or lo is None:
        return None
    if not (-90 <= la <= 90 and -180 <= lo <= 180):
        return None
    return la, lo


def _fmt_coord(n):
    s = f"{n:.7f}".rstrip("0").rstrip(".")
    if s in ("", "-", "-0"):
        return "0"
    return s


def map_point(event):
    """('coords', 'lat,lng') or ('query', address). Coordinates win when stored. None when there is nothing to map."""
    if not isinstance(event, dict):
        return None
    coords = map_coords(event)
    if coords:
        return "coords", f"{_fmt_coord(coords[0])},{_fmt_coord(coords[1])}"
    place = (event.get("place") or "").strip()
    city = (event.get("city") or "").strip()
    if event.get("online") and not place and not city:
        return None
    query = map_query(event)
    if not query:
        return None
    return "query", query


def map_url(event):
    """Google Maps search. Written as the href so the link works with JavaScript off."""
    point = map_point(event)
    if not point:
        return None
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(point[1], safe="")


def apple_map_url(event):
    """Apple Maps. ll= when coordinates are stored, otherwise q= for the address."""
    point = map_point(event)
    if not point:
        return None
    kind, value = point
    if kind == "coords":
        return "https://maps.apple.com/?ll=" + value
    return "https://maps.apple.com/?q=" + urllib.parse.quote(value, safe="")


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
