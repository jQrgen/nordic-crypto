"""Nordic crypto podcasts: data/podcasts.json, the /podcasts/ page and /api/v1/podcasts.json.

Metadata and links only. Audio and cover art are never stored or proxied.
refresh() is called by fetch.py with its polite get() and robots_ok().
"""
import datetime as dt
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "podcasts.json")
ACTIVE_DAYS = 90
KEEP = 5
COUNTRY_ORDER = ("NO", "SE", "DK", "FI", "IS")
FLAGS = ("exchange-owned", "exchange-sponsored", "exchange-partner", "advertiser-paid",
         "affiliate-links", "shop-owned", "altcoin-promotion", "advocacy-group")
# anchor.fm/robots.txt redirects to an HTML page on creators.spotify.com; it has no rules for the
# feed host, so the feeds are allowed. Podcast RSS is published for machine readers.


def raw():
    with open(PATH, encoding="utf-8") as fh:
        return json.load(fh)


def updated():
    return raw().get("updated")


def _sort_key(s):
    last = (s.get("episodes") or [{}])[0].get("date") or ""
    return (not s.get("active"), "".join(chr(0x10FFFF - ord(c)) for c in last), s["name"].lower())


def rows():
    """Active shows first, then newest episode first."""
    return sorted(raw().get("podcasts") or [], key=_sort_key)


def problems():
    bad, seen = [], set()
    for s in raw().get("podcasts") or []:
        sid = s.get("id") or "?"
        for k in ("id", "name", "country", "language", "feed", "site", "added_at"):
            if not s.get(k):
                bad.append(f"{sid}: missing {k}")
        if sid in seen:
            bad.append(f"{sid}: duplicate id")
        seen.add(sid)
        if s.get("country") not in COUNTRY_ORDER:
            bad.append(f"{sid}: country {s.get('country')}")
        for f in s.get("flags") or []:
            if f not in FLAGS:
                bad.append(f"{sid}: flag {f}")
        if len(s.get("episodes") or []) > KEEP:
            bad.append(f"{sid}: more than {KEEP} episodes")
    return bad


def _episodes(body, fallback):
    import feedparser
    d = feedparser.parse(body)
    out = []
    for e in d.entries:
        tm = e.get("published_parsed") or e.get("updated_parsed")
        if not tm or not e.get("title"):
            continue
        link = e.get("link") or ""
        if not link.startswith("http"):
            link = fallback
        out.append({"title": e.title.strip()[:200], "date": time.strftime("%Y-%m-%d", tm), "link": link})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:KEEP]


def refresh(get, robots_ok, log=print, now=None):
    """Re-read every feed. A failed feed keeps its previous episodes. Writes the file atomically."""
    now = now or dt.datetime.now(dt.timezone.utc)
    data = raw()
    ok = 0
    for s in data["podcasts"]:
        s.setdefault("added_at", now.date().isoformat())
        try:
            if not robots_ok(s["feed"]):
                log("podcasts: robots.txt disallows", s["id"])
                continue
            r = get(s["feed"], conditional=False)
            if r.status_code != 200:
                log("podcasts:", s["id"], "HTTP", r.status_code)
                continue
            eps = _episodes(r.content, s["site"])
            if eps:
                s["episodes"] = eps
                ok += 1
        except Exception as ex:
            log("podcasts:", s["id"], type(ex).__name__, str(ex)[:80])
        last = (s.get("episodes") or [{}])[0].get("date")
        s["active"] = bool(last) and (now.date() - dt.date.fromisoformat(last)).days <= ACTIVE_DAYS
    data["podcasts"] = sorted(data["podcasts"], key=_sort_key)
    data["updated"] = now.isoformat(timespec="seconds")
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, PATH)
    log(f"podcasts: {ok}/{len(data['podcasts'])} feeds read, {sum(s['active'] for s in data['podcasts'])} active")
    return data
