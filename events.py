#!/usr/bin/env python3
"""Events (calendar) for Nordic Crypto: Norway, Sweden, Finland, Iceland and the Faroe Islands.
Called from fetch.py in every run, or on its own:
  .venv/bin/python events.py                     # search event_sources in sources.json
  .venv/bin/python events.py --add-event URL     # add from the organiser's page (JSON-LD or iCal) – researcher
Rules (editor): only events where the organiser's own page or a public listing shows date, place and organiser,
and which are genuinely about crypto, bitcoin or blockchain. Paid and sponsored events are labelled. Never invented.
EVERY new event gets status "pending"; the editor approves/rejects in queue/approved.json -> events.approve / events.reject (id).
Times keep the event's own UTC offset (Helsinki is one hour ahead of Oslo/Stockholm, Reykjavík and Tórshavn are behind)."""
import argparse, datetime as dt, hashlib, json, os, re, sys, urllib.parse
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
ROOT = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(ROOT, *a)
TZ = {"NO": "Europe/Oslo", "SE": "Europe/Stockholm", "FI": "Europe/Helsinki", "IS": "Atlantic/Reykjavik", "FO": "Atlantic/Faroe"}
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
def jsonld_events(html, tz="Europe/Oslo"):
    s = BeautifulSoup(html, "lxml"); out = []
    for sc in s.find_all("script", type="application/ld+json"):
        try: d = json.loads(sc.string or "")
        except Exception: continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d])):
            if not isinstance(x, dict) or "Event" not in str(x.get("@type")): continue
            loc = x.get("location") or {}; loc = loc[0] if isinstance(loc, list) and loc else loc
            online = "OnlineEventAttendanceMode" in str(x.get("eventAttendanceMode")) or (isinstance(loc, dict) and loc.get("@type") == "VirtualLocation")
            addr = loc.get("address") if isinstance(loc, dict) else None
            city = (addr.get("addressLocality") if isinstance(addr, dict) else None)
            ctry = (addr.get("addressCountry") if isinstance(addr, dict) else None)
            lname = loc.get("name") if isinstance(loc, dict) else (loc if isinstance(loc, str) else None)
            street = addr.get("streetAddress") if isinstance(addr, dict) else None
            parts = [v.strip() for v in [lname, street] if isinstance(v, str) and v.strip()]
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
def ics_events(text, tz="Europe/Oslo"):
    out = []; text = re.sub(r"\r?\n[ \t]", "", text)
    for blk in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        f = {}
        for line in blk.strip().splitlines():
            if ":" in line: k, v = line.split(":", 1); f[k.split(";")[0].upper()] = v.replace("\\,", ",").replace("\\n", " ").strip()
        out.append({"title": f.get("SUMMARY"), "start": parse_dt(f.get("DTSTART"), tz), "end": parse_dt(f.get("DTEND"), tz), "place": f.get("LOCATION"),
                    "city": None, "online": False, "organiser": None, "url": f.get("URL"), "description": f.get("DESCRIPTION", "")[:600], "paid": None})
    return out
def eid(e): return hashlib.sha1(f"{(e.get('url') or '').split('?')[0]}|{e['start'].date() if e.get('start') else ''}|{(e.get('title') or '').lower()}".encode()).hexdigest()[:12]
CITIES = {"NO": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Kristiansand", "Tromsø", "Bodø", "Drammen", "Fredrikstad", "Ålesund", "Fornebu", "Lysaker", "Lillehammer"],
          "SE": ["Stockholm", "Göteborg", "Gothenburg", "Malmö", "Uppsala", "Linköping", "Örebro", "Västerås", "Umeå", "Lund", "Luleå", "Boden"],
          "FI": ["Helsinki", "Helsingfors", "Espoo", "Tampere", "Turku", "Åbo", "Oulu", "Vantaa", "Jyväskylä"],
          "IS": ["Reykjavík", "Reykjavik", "Akureyri", "Kópavogur", "Hafnarfjörður"],
          "FO": ["Tórshavn", "Torshavn", "Klaksvík", "Runavík"]}
CC = {"NO": "NO", "NOR": "NO", "NORWAY": "NO", "SE": "SE", "SWE": "SE", "SWEDEN": "SE", "FI": "FI", "FIN": "FI", "FINLAND": "FI", "IS": "IS", "ISL": "IS", "ICELAND": "IS", "FO": "FO", "FRO": "FO"}
def guess_city(place):
    for c, cs in CITIES.items():
        for x in cs:
            if place and re.search(rf"\b{x}\b", place, re.I): return x, c
    return None, None

def run(get, robots_ok, matches, log, cfg, add_url=None, a=None):
    data = _load(P("data", "events.json"), {"events": []}); by = {e["id"]: e for e in data["events"]}
    status = _load(P("state", "source_status.json"), {}); now = dt.datetime.now(UTC); new = []
    def take(ev, src, trusted):
        if not ev.get("title") or not ev.get("start"): return
        text = f"{ev['title']} {ev.get('description', '')}"
        if not trusted and not matches(text): return
        ev["organiser"] = ev.get("organiser") or src.get("organiser")
        city, c = guess_city(" ".join(x for x in [ev.get("place") or "", ev.get("city") or ""] if x))
        country = CC.get((ev.get("country_hint") or "").upper()) or c
        if not country and ev.get("online"): country = src.get("country")
        if not country and (ev.get("place") or ev.get("city")):
            return  # a physical event we cannot place in NO/SE/FI/IS/FO: not ours (search results include other countries)
        country = country or src.get("country")
        if country not in TZ: return
        if not trusted and ev.get("online") and not city: return  # online webinars found via search have no Nordic link
        ev["start"] = ev["start"].astimezone(ZoneInfo(TZ[country]))  # show local time in the event's country
        if ev.get("end"): ev["end"] = ev["end"].astimezone(ZoneInfo(TZ[country]))
        ev["city"] = ev.get("city") or city or (src.get("city") if country == src.get("country") else None)
        if ev.get("url") is None: ev["url"] = src.get("page") or src["url"]
        ev["paid"] = ev["paid"] if ev.get("paid") is not None else ev.get("paid_hint")
        i = eid(ev)
        if i in by:
            for k in ("place", "city", "end", "organiser"):
                v = ev.get(k)
                if v and not by[i].get(k): by[i][k] = v.isoformat() if hasattr(v, "isoformat") else v
            return
        complete = bool(ev.get("place") or ev.get("online")) and bool(ev.get("organiser"))
        rec = {"id": i, "title": ev["title"], "start": ev["start"].isoformat(), "end": ev["end"].isoformat() if ev.get("end") else None,
               "place": ev.get("place"), "city": ev.get("city"), "country": country, "online": bool(ev.get("online")), "organiser": ev.get("organiser"),
               "url": ev["url"], "source": src["name"], "source_url": src.get("page") or src["url"], "paid": ev.get("paid"), "sponsored": None,
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
        for src in sources:
            if not src.get("enabled", True): continue
            err = None; n0 = len(new); n_found = 0; tz = TZ.get(src.get("country"), "Europe/Oslo")
            try:
                r = fetch_page(src["url"])
                if src["type"] == "jsonld":
                    evs = jsonld_events(r.text, tz); n_found = len(evs)
                    for ev in evs: take(ev, src, src.get("trusted", False))
                elif src["type"] == "listing-ical":
                    s = BeautifulSoup(r.text, "lxml")
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
            except Exception as ex: err = f"{type(ex).__name__}: {ex}"[:200]
            status["ev-" + src["id"]] = {"checked": now.isoformat(timespec="seconds"), "ok": err is None, "entries": n_found, "new": len(new) - n0, "error": err}
            log(f"event {src['id']:<28} found={n_found} new={len(new) - n0} err={err}")
    data["events"].sort(key=lambda e: dt.datetime.fromisoformat(e["start"])); data["updated"] = now.isoformat(timespec="seconds")
    _save(P("data", "events.json"), data); _save(P("state", "source_status.json"), status)
    q = _load(P("queue", "review.json"), {"items_needing_summary": [], "candidate_entities": []})
    apev = (_load(P("queue", "approved.json"), {}) or {}).get("events", {}); done = set(apev.get("approve", [])) | set(apev.get("reject", []))
    q["events_pending"] = [e for e in data["events"] if e["status"] == "pending" and e["id"] not in done and dt.datetime.fromisoformat(e["end"] or e["start"]) >= now]
    _save(P("queue", "review.json"), q)
    log(f"events: {len(new)} new, {len(q['events_pending'])} awaiting the editor")
    return new

if __name__ == "__main__":
    import fetch
    ap = argparse.ArgumentParser(); ap.add_argument("--add-event", metavar="URL"); ap.add_argument("--source-name"); ap.add_argument("--organiser")
    ap.add_argument("--title"); ap.add_argument("--start", help="YYYY-MM-DDTHH:MM (local time in --country)"); ap.add_argument("--end"); ap.add_argument("--place"); ap.add_argument("--city")
    ap.add_argument("--country", choices=list(TZ), help="NO, SE, FI, IS or FO"); ap.add_argument("--online", action="store_true")
    ap.add_argument("--paid", type=lambda s: s.lower() in ("1", "true", "yes", "ja"), default=None)
    a, _ = ap.parse_known_args()
    run(fetch.get, fetch.robots_ok, lambda t: bool(fetch.matches(t)), fetch.log, fetch.CFG, a.add_event, a)
