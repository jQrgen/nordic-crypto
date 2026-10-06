#!/usr/bin/env python3
"""Events (calendar) for Crypto Nordic: Norway, Sweden, Denmark, Finland and Iceland.
Called from fetch.py in every run, or on its own:
  .venv/bin/python events.py                     # search event_sources in sources.json
  .venv/bin/python events.py --add-event URL     # add from the organiser's page (JSON-LD or iCal) – researcher
Rules (editor): only events where the organiser's own page or a public listing shows date, place and organiser,
and which are genuinely about crypto, bitcoin or blockchain. Paid and sponsored events are labelled. Never invented.
EVERY new event gets status "pending"; the editor approves/rejects in queue/approved.json -> events.approve / events.reject (id).
Times keep the event's own UTC offset (Helsinki is one hour ahead of Oslo/Stockholm, Reykjavík is behind).

Luma: public calendar Subscribe iCal only (api.lu.ma/ics/get?entity=calendar&id=cal-…).
Individual event pages are schema.org JSON-LD. City pages, category pages and api.lu.ma discover
are not crawled: Luma's terms allow only publicly supported interfaces, and the official API
needs Luma Plus and only covers calendars you administer.
Eventbrite: v3 /organizers/{id}/events/ and /venues/{id}/events/ when EVENTBRITE_TOKEN is set.
Without a token, JSON-LD on the event page. The public search API (removed 2020) is not used.
A dead feed is recorded and skipped. Finished events already stored are never deleted."""
import argparse, datetime as dt, hashlib, json, os, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
ROOT = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(ROOT, *a)
TZ = {"NO": "Europe/Oslo", "SE": "Europe/Stockholm", "DK": "Europe/Copenhagen", "FI": "Europe/Helsinki", "IS": "Atlantic/Reykjavik"}
UTC = dt.timezone.utc

def _load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
def _save(p, d):
    t = p + ".tmp"; json.dump(d, open(t, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(t, p)
def parse_dt(s, tz="Europe/Oslo"):
    """ISO or iCal date -> aware datetime in the event's own offset (or the source country's zone if none is given)."""
    if not s: return None
    s = s.strip(); z = ZoneInfo(tz)
    m = re.fullmatch(r"(\d{8})T(\d{6})(Z?)", s)
    if m:
        d = dt.datetime.strptime(m[1] + m[2], "%Y%m%d%H%M%S")
        return d.replace(tzinfo=UTC).astimezone(z) if m[3] else d.replace(tzinfo=z)
    if re.fullmatch(r"\d{8}", s): return dt.datetime.strptime(s, "%Y%m%d").replace(tzinfo=z)
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=z)
    except ValueError: return None
def _ld_nodes(d):
    """Top-level Events, @graph, and schema.org ItemList entries (event pages nest the Event)."""
    if isinstance(d, list): nodes = d
    elif isinstance(d, dict) and d.get("@type") == "ItemList": nodes = [d]
    elif isinstance(d, dict): nodes = d.get("@graph", [d])
    else: return []
    out = []
    for x in nodes:
        if not isinstance(x, dict): continue
        if x.get("@type") == "ItemList":
            for el in x.get("itemListElement") or []:
                item = el.get("item") if isinstance(el, dict) else None
                if isinstance(item, dict): out.append(item)
            continue
        out.append(x)
    return out
def jsonld_events(html, tz="Europe/Oslo"):
    s = BeautifulSoup(html, "lxml"); out = []
    for sc in s.find_all("script", type="application/ld+json"):
        try: d = json.loads(sc.string or "")
        except Exception: continue
        for x in _ld_nodes(d):
            if not isinstance(x, dict) or "Event" not in str(x.get("@type")): continue
            loc = x.get("location") or {}; loc = loc[0] if isinstance(loc, list) and loc else loc
            addr = loc.get("address") if isinstance(loc, dict) else None
            street = addr.get("streetAddress") if isinstance(addr, dict) else None
            online = ("OnlineEventAttendanceMode" in str(x.get("eventAttendanceMode"))
                      or (isinstance(loc, dict) and loc.get("@type") == "VirtualLocation")
                      or (isinstance(street, str) and re.search(r"\bonline\b", street, re.I)))
            city = (addr.get("addressLocality") if isinstance(addr, dict) else None)
            ctry = (addr.get("addressCountry") if isinstance(addr, dict) else None)
            lname = loc.get("name") if isinstance(loc, dict) else (loc if isinstance(loc, str) else None)
            parts = [v.strip() for v in [lname, street] if isinstance(v, str) and v.strip() and not re.search(r"\bonline event\b", v, re.I)]
            parts = [v for v in parts if not any(v != w and v in w for w in parts)]
            place = ", ".join(dict.fromkeys(parts)) or None
            org = x.get("organizer") or {}; org = org[0] if isinstance(org, list) and org else org
            offers = x.get("offers") or {}; offers = offers if isinstance(offers, list) else [offers]
            prices = [float(o.get("price")) for o in offers if isinstance(o, dict) and str(o.get("price", "")).replace(".", "", 1).isdigit()]
            out.append({"title": x.get("name"), "start": parse_dt(x.get("startDate"), tz), "end": parse_dt(x.get("endDate"), tz), "place": place or None,
                        "city": (city or "").strip() or None, "country_hint": ctry if isinstance(ctry, str) else None, "online": online,
                        "organiser": org.get("name") if isinstance(org, dict) else None,
                        "url": x.get("url"), "description": BeautifulSoup(x.get("description") or "", "lxml").get_text(" ")[:600],
                        "paid": (max(prices) > 0) if prices else None})
    return out
def _ics_unescape(v):
    return v.replace("\\,", ",").replace("\\n", " ").replace("\\;", ";").strip()
def ics_events(text, tz="Europe/Oslo"):
    out = []; text = re.sub(r"\r?\n[ \t]", "", text)
    for blk in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        f = {}
        for line in blk.strip().splitlines():
            if ":" not in line: continue
            k, v = line.split(":", 1); base = k.split(";")[0].upper(); f[base] = _ics_unescape(v)
            if base == "ORGANIZER":
                cn = re.search(r'CN="?([^";]+)"?', k)
                if cn: f["ORGANIZER_CN"] = cn.group(1).strip().strip('"')
        desc = f.get("DESCRIPTION") or ""
        url = f.get("URL")
        if not url:
            m = re.search(r"https://(?:www\.)?(?:luma\.com|lu\.ma)/[A-Za-z0-9_-]+", desc)
            if m: url = m.group(0)
        place = f.get("LOCATION")
        if place and re.match(r"https?://", place.strip()): place = None
        out.append({"title": f.get("SUMMARY"), "start": parse_dt(f.get("DTSTART"), tz), "end": parse_dt(f.get("DTEND"), tz), "place": place,
                    "city": None, "online": False, "organiser": f.get("ORGANIZER_CN"), "url": url, "description": desc[:600], "paid": None})
    return out
def clear_kaupr_sponsor(value):
    """Kaupr is a news source only. Never record it as a sponsor of an event."""
    if isinstance(value, str) and re.search(r"\bkaupr\b", value, re.I): return None
    return value
def _norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower(), flags=re.U).strip()
def _day(e):
    s = e.get("start")
    if hasattr(s, "date"): return s.date()
    if isinstance(s, str) and len(s) >= 10:
        try: return dt.date.fromisoformat(s[:10])
        except ValueError: return None
    return None
def same_event(a, b):
    """Same listing when title, calendar date and venue match, even if the URL differs."""
    if not _norm(a.get("title")) or _norm(a.get("title")) != _norm(b.get("title")): return False
    if _day(a) is None or _day(a) != _day(b): return False
    va = _norm(" ".join(x for x in [a.get("place"), a.get("city")] if x))
    vb = _norm(" ".join(x for x in [b.get("place"), b.get("city")] if x))
    if va and vb and va not in vb and vb not in va: return False
    return True
def _eb_text(block):
    if isinstance(block, dict): return (block.get("text") or block.get("html") or "") or ""
    return block or ""
def eventbrite_to_event(raw, tz="Europe/Oslo"):
    """One Eventbrite v3 event object -> the dict take() expects."""
    if not isinstance(raw, dict): return None
    venue = raw.get("venue") if isinstance(raw.get("venue"), dict) else {}
    addr = venue.get("address") if isinstance(venue.get("address"), dict) else {}
    org = raw.get("organizer") if isinstance(raw.get("organizer"), dict) else {}
    start = (raw.get("start") or {}) if isinstance(raw.get("start"), dict) else {}
    end = (raw.get("end") or {}) if isinstance(raw.get("end"), dict) else {}
    parts = [venue.get("name"), addr.get("address_1"), addr.get("localized_address_display")]
    parts = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    parts = [v for v in parts if not any(v != w and v in w for w in parts)]
    online = bool(raw.get("online_event"))
    free = raw.get("is_free")
    return {"title": BeautifulSoup(_eb_text(raw.get("name")), "lxml").get_text(" ").strip() or None,
            "start": parse_dt(start.get("utc") or start.get("local"), start.get("timezone") or tz),
            "end": parse_dt(end.get("utc") or end.get("local"), end.get("timezone") or tz),
            "place": ", ".join(dict.fromkeys(parts)) or None,
            "city": (addr.get("city") or "").strip() or None,
            "country_hint": addr.get("country") if isinstance(addr.get("country"), str) else None,
            "online": online, "organiser": org.get("name"), "url": raw.get("url"),
            "description": BeautifulSoup(_eb_text(raw.get("description")), "lxml").get_text(" ")[:600],
            "paid": (not free) if isinstance(free, bool) else None}
def eb_get(url, token, robots_ok, pause, ua):
    """Authorized Eventbrite v3 GET. The token stays in the header and is never logged."""
    if not robots_ok(url): raise RuntimeError("robots.txt disallows")
    if pause: time.sleep(pause)
    r = requests.get(url, headers={"Authorization": "Bearer " + token, "User-Agent": ua, "Accept": "application/json"}, timeout=25)
    r.raise_for_status()
    return r.json()
def _eventbrite(src, tz, fetch_page, robots_ok, pause, ua):
    """v3 organizers/venues API when EVENTBRITE_TOKEN is set; otherwise JSON-LD on event pages.
    One dead event page is skipped. The removed public search API is not called."""
    token = os.environ.get("EVENTBRITE_TOKEN", "").strip()
    kind = "organizers" if src.get("type") == "eventbrite-organizer" else "venues"
    ident = src.get("organizer_id") if kind == "organizers" else src.get("venue_id")
    api_err = None
    if token and ident:
        try:
            return eventbrite_api_events(kind, ident, token, robots_ok, pause, ua, tz), None
        except Exception as ex:
            api_err = f"{type(ex).__name__}: {ex}"[:160]
    pages = [u for u in (src.get("event_pages") or []) if u]
    page = src.get("url") or ""
    if page and "/e/" not in page:
        try:
            soup = BeautifulSoup(fetch_page(page).text, "lxml")
            for a in soup.find_all("a", href=True):
                u = urllib.parse.urljoin(page, a["href"]).split("?")[0]
                if re.search(r"/e/.+tickets", u) and u not in pages: pages.append(u)
                if len(pages) >= 8: break
        except Exception as ex:
            if api_err is None and not src.get("event_pages"): api_err = f"{type(ex).__name__}: {ex}"[:160]
    elif page and "/e/" in page and page not in pages:
        pages.insert(0, page)
    evs = []
    for u in pages[:8]:
        try: evs.extend(jsonld_events(fetch_page(u).text, tz))
        except Exception: continue
    return evs, (None if evs or api_err is None else api_err)
def eventbrite_api_events(kind, ident, token, robots_ok, pause, ua, tz):
    """kind is 'organizers' or 'venues'. Follows continuation, at most five pages."""
    if kind not in ("organizers", "venues") or not ident: return []
    q = urllib.parse.urlencode({"status": "live", "time_filter": "current_future", "expand": "venue,organizer"})
    url = f"https://www.eventbriteapi.com/v3/{kind}/{ident}/events/?{q}"
    out = []
    for _ in range(5):
        data = eb_get(url, token, robots_ok, pause, ua)
        for raw in data.get("events") or []:
            ev = eventbrite_to_event(raw, tz)
            if ev: out.append(ev)
        pag = data.get("pagination") or {}
        cont = pag.get("continuation")
        if not pag.get("has_more_items") or not cont: break
        url = f"https://www.eventbriteapi.com/v3/{kind}/{ident}/events/?{q}&continuation={urllib.parse.quote(cont)}"
    return out
def eid(e): return hashlib.sha1(f"{(e.get('url') or '').split('?')[0]}|{e['start'].date() if e.get('start') else ''}|{(e.get('title') or '').lower()}".encode()).hexdigest()[:12]
CITIES = {"NO": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Kristiansand", "Tromsø", "Bodø", "Drammen", "Fredrikstad", "Ålesund", "Fornebu", "Lysaker", "Lillehammer"],
          "SE": ["Stockholm", "Göteborg", "Gothenburg", "Malmö", "Uppsala", "Linköping", "Örebro", "Västerås", "Umeå", "Lund", "Luleå", "Boden"],
          "DK": ["København", "Copenhagen", "Frederiksberg", "Aarhus", "Odense", "Aalborg", "Esbjerg", "Kolding", "Roskilde", "Lyngby"],
          "FI": ["Helsinki", "Helsingfors", "Espoo", "Tampere", "Turku", "Åbo", "Oulu", "Vantaa", "Jyväskylä"],
          "IS": ["Reykjavík", "Reykjavik", "Akureyri", "Kópavogur", "Hafnarfjörður"]}
CC = {"NO": "NO", "NOR": "NO", "NORWAY": "NO", "SE": "SE", "SWE": "SE", "SWEDEN": "SE", "DK": "DK", "DNK": "DK", "DENMARK": "DK", "FI": "FI", "FIN": "FI", "FINLAND": "FI", "IS": "IS", "ISL": "IS", "ICELAND": "IS"}
def guess_city(place):
    for c, cs in CITIES.items():
        for x in cs:
            if place and re.search(rf"\b{x}\b", place, re.I): return x, c
    return None, None

def run(get, robots_ok, matches, log, cfg, add_url=None, a=None, root=None, now=None):
    base = root or ROOT
    def lp(*parts): return os.path.join(base, *parts)
    for d in ("data", "state", "queue"): os.makedirs(os.path.join(base, d), exist_ok=True)
    data = _load(lp("data", "events.json"), {"events": []}); by = {e["id"]: e for e in data["events"]}
    original = [dict(e) for e in data["events"]]  # finished events are never removed
    status = _load(lp("state", "source_status.json"), {}); now = now or dt.datetime.now(UTC)
    if now.tzinfo is None: now = now.replace(tzinfo=UTC)
    new = []
    def _fill(old, ev):
        for k in ("place", "city", "end", "organiser"):
            v = ev.get(k)
            if v and not old.get(k): old[k] = v.isoformat() if hasattr(v, "isoformat") else v
    def take(ev, src, trusted):
        if not ev.get("title") or not ev.get("start"): return
        text = f"{ev['title']} {ev.get('description', '')} {ev.get('place') or ''}"
        if not trusted and not matches(text): return
        ev["organiser"] = ev.get("organiser") or src.get("organiser")
        city, c = guess_city(" ".join(x for x in [ev.get("place") or "", ev.get("city") or ""] if x))
        country = CC.get((ev.get("country_hint") or "").upper()) or c
        if not country and ev.get("online"): country = src.get("country")
        if not country and (ev.get("place") or ev.get("city")):
            return  # a physical event we cannot place in NO/SE/DK/FI/IS: not ours (search results include other countries)
        country = country or src.get("country")
        if country not in TZ: return
        nordic_hint = CC.get((ev.get("country_hint") or "").upper())
        if not trusted and ev.get("online") and not city and not nordic_hint: return  # online webinars found via search have no Nordic link
        ev["start"] = ev["start"].astimezone(ZoneInfo(TZ[country]))  # show local time in the event's country
        if ev.get("end"): ev["end"] = ev["end"].astimezone(ZoneInfo(TZ[country]))
        ev["city"] = ev.get("city") or city or (src.get("city") if country == src.get("country") else None)
        if ev.get("url") is None: ev["url"] = src.get("page") or src["url"]
        ev["paid"] = ev["paid"] if ev.get("paid") is not None else ev.get("paid_hint")
        twin = next((old for old in by.values() if same_event(ev, old)), None)
        if twin: _fill(twin, ev); return  # same title, date and venue, whatever the URL
        i = eid(ev)
        if i in by: _fill(by[i], ev); return
        if (ev.get("end") or ev["start"]) < now: return  # do not add a finished event; ones already stored stay
        complete = bool(ev.get("place") or ev.get("online")) and bool(ev.get("organiser"))
        rec = {"id": i, "title": ev["title"], "start": ev["start"].isoformat(), "end": ev["end"].isoformat() if ev.get("end") else None,
               "place": ev.get("place"), "city": ev.get("city"), "country": country, "online": bool(ev.get("online")), "organiser": ev.get("organiser"),
               "url": ev["url"], "source": src["name"], "source_url": src.get("page") or src["url"], "paid": ev.get("paid"),
               "sponsored": clear_kaupr_sponsor(None),
               "trusted_source": bool(trusted), "found": now.isoformat(timespec="seconds"), "status": "pending",
               "note": None if complete else "missing place or organiser – check the organiser's page"}
        data["events"].append(rec); by[i] = rec; new.append(rec)
    def fetch_page(u):
        if not robots_ok(u): raise RuntimeError("robots.txt disallows")
        r = get(u); r.raise_for_status(); return r
    sources = cfg.get("event_sources", [])
    if add_url:
        tz = TZ.get(a.country or "NO", "Europe/Oslo")
        r = fetch_page(add_url); evs = jsonld_events(r.text, tz)
        if not evs:
            s = BeautifulSoup(r.text, "lxml"); ic = next((x["href"] for x in s.find_all("a", href=True) if re.search(r"ical|\.ics", x["href"], re.I)), None)
            if ic: evs = ics_events(fetch_page(urllib.parse.urljoin(add_url, ic)).text, tz)
        src = {"name": a.source_name or urllib.parse.urlparse(add_url).netloc.removeprefix("www."), "url": add_url, "page": add_url,
               "organiser": a.organiser, "city": a.city, "country": a.country}
        if not evs and a.title and a.start:
            evs = [{"title": a.title, "start": parse_dt(a.start, tz), "end": parse_dt(a.end, tz) if a.end else None, "place": a.place, "city": a.city,
                    "online": bool(a.online), "organiser": a.organiser, "url": add_url, "description": "", "paid": a.paid, "country_hint": a.country}]
        for ev in evs:
            if a.paid is not None: ev["paid"] = a.paid
            take(ev, src, True)
        for n in new: n["note"] = "added manually by the researcher – editor must approve"
        log(f"event: {len(new)} added from {add_url}" if new else f"event: found no new dated events on {add_url} (use --title/--start/--place/--organiser/--country)")
    else:
        pause = cfg.get("min_delay_seconds", 2); ua = cfg.get("user_agent") or "CryptoNordicBot/0.1"
        for src in sources:
            if not src.get("enabled", True): continue
            err = None; n0 = len(new); n_found = 0; tz = TZ.get(src.get("country"), "Europe/Oslo")
            try:
                if src["type"] == "luma-ical":
                    # Public Subscribe feed only. Do not call Luma discover or the Plus API.
                    evs = ics_events(fetch_page(src.get("ics") or src["url"]).text, tz); n_found = len(evs)
                    for ev in evs: take(ev, src, False)
                elif src["type"] == "luma-event":
                    evs = jsonld_events(fetch_page(src["url"]).text, tz); n_found = len(evs)
                    for ev in evs: take(ev, src, False)
                elif src["type"] in ("eventbrite-organizer", "eventbrite-venue"):
                    evs, err = _eventbrite(src, tz, fetch_page, robots_ok, pause, ua)
                    n_found = len(evs)
                    for ev in evs: take(ev, src, False)
                elif src["type"] == "jsonld":
                    r = fetch_page(src["url"]); evs = jsonld_events(r.text, tz); n_found = len(evs)
                    for ev in evs: take(ev, src, src.get("trusted", False))
                elif src["type"] == "listing-ical":
                    r = fetch_page(src["url"]); s = BeautifulSoup(r.text, "lxml")
                    links = {urllib.parse.urljoin(src["url"], x["href"]) for x in s.find_all("a", href=True)
                             if re.search(src["link_pattern"], x["href"]) and (src.get("trusted") or matches(x.get_text(" ") + " " + x["href"].replace("-", " ")))}
                    for u in sorted(links)[:20]:
                        pg = fetch_page(u); ps = BeautifulSoup(pg.text, "lxml")
                        ic = next((x["href"] for x in ps.find_all("a", href=True) if re.search(r"download-ical|\.ics", x["href"], re.I)), None)
                        if not ic: continue
                        price = re.search(r"kr\.?\s?(\d[\d .]*),?-?", ps.get_text(" "))
                        for ev in ics_events(fetch_page(urllib.parse.urljoin(u, ic)).text, tz):
                            n_found += 1; ev["paid_hint"] = True if price and int(re.sub(r"\D", "", price[1]) or 0) > 0 else None
                            ev["description"] = ps.get_text(" ")[:1500]; src2 = dict(src, page=u); take(ev, src2, src.get("trusted", False))
                elif src["type"] == "manual":
                    n_found = 0
                else:
                    err = f"unknown event source type {src.get('type')}"
            except Exception as ex: err = f"{type(ex).__name__}: {ex}"[:200]
            status["ev-" + src["id"]] = {"checked": now.isoformat(timespec="seconds"), "ok": err is None, "entries": n_found, "new": len(new) - n0, "error": err}
            log(f"event {src['id']:<28} found={n_found} new={len(new) - n0} err={err}")
    # Never drop an event that was already stored. Finished ones move to the past archive in the build.
    stored = {e["id"] for e in data["events"]}
    for old in original:
        if old["id"] not in stored: data["events"].append(old)
    data["events"].sort(key=lambda e: dt.datetime.fromisoformat(e["start"])); data["updated"] = now.isoformat(timespec="seconds")
    _save(lp("data", "events.json"), data); _save(lp("state", "source_status.json"), status)
    q = _load(lp("queue", "review.json"), {"items_needing_summary": [], "candidate_entities": []})
    apev = (_load(lp("queue", "approved.json"), {}) or {}).get("events", {}); done = set(apev.get("approve", [])) | set(apev.get("reject", []))
    q["events_pending"] = [e for e in data["events"] if e["status"] == "pending" and e["id"] not in done and dt.datetime.fromisoformat(e["end"] or e["start"]) >= now]
    _save(lp("queue", "review.json"), q)
    log(f"events: {len(new)} new, {len(q['events_pending'])} awaiting the editor")
    return new

if __name__ == "__main__":
    import fetch
    ap = argparse.ArgumentParser(); ap.add_argument("--add-event", metavar="URL"); ap.add_argument("--source-name"); ap.add_argument("--organiser")
    ap.add_argument("--title"); ap.add_argument("--start", help="YYYY-MM-DDTHH:MM (local time in --country)"); ap.add_argument("--end"); ap.add_argument("--place"); ap.add_argument("--city")
    ap.add_argument("--country", choices=list(TZ), help="NO, SE, DK, FI or IS"); ap.add_argument("--online", action="store_true")
    ap.add_argument("--paid", type=lambda s: s.lower() in ("1", "true", "yes", "ja"), default=None)
    a, _ = ap.parse_known_args()
    run(fetch.get, fetch.robots_ok, lambda t: bool(fetch.matches(t)), fetch.log, fetch.CFG, a.add_event, a)
