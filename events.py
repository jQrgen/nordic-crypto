#!/usr/bin/env python3
"""Events (calendar) for Nordic Crypto: Norway, Sweden, Denmark, Finland and Iceland.
Called from fetch.py in every run, or on its own:
  .venv/bin/python events.py                     # search event_sources in sources.json
  .venv/bin/python events.py --only id,id        # one or more event sources
  .venv/bin/python events.py --add-event URL     # add from the organiser's page (JSON-LD or iCal) – researcher
Rules (editor): only events where the organiser's own page or a public listing shows date, place and organiser,
and which are genuinely about crypto, bitcoin or blockchain. Paid and sponsored events are labelled. Never invented.
EVERY new event gets status "pending"; the editor approves/rejects in queue/approved.json -> events.approve / events.reject (id).
Times keep the event's own UTC offset (Helsinki is one hour ahead of Oslo/Stockholm, Reykjavík is behind).

type listing-jsonld: read the country listing, follow event links (link_pattern, crypto keywords unless trusted,
soonest first, max_links), and read schema.org Event JSON-LD on each page (title, dates, place, organiser, url).
A street address under a Venue label is used when it is more specific than the city. A timestamp of 00:00:00Z is
stored as that calendar day in the event country's time zone, not as midnight UTC shifted into the previous evening.
No images are stored. The calendar links to the event page. Refresh with the commands above; a failed fetch keeps
events already in data/events.json. A finished event is not deleted from data/events.json.
JSON-LD attendeeCount (and the same kind of explicit count) and an iCal X-GUEST-COUNT are stored with the
page URL and the time they were read. Seat capacity is not a participant count and is not stored.
The organiser's description (JSON-LD, iCal, Eventbrite, or the Meetup event object) is stored with
the page URL and its language. A description that is only the title, a URL, or a sponsor line is not
stored. A predatory listing is not a source for that text. Kaupr is never kept in it.

Predatory conference listings are never imported (event_block.py): International Conference Alerts, Conference
Alerts, All Conference Alert, Conference Next, WASET, conferenceindex.org, and the organisers WASET, IRAJ, IIER,
ISER, Academics World and World Academics. A matching URL, source or organiser is dropped, including a row already
in data/events.json and an event added with --add-event.

Luma: public calendar Subscribe iCal only (api.lu.ma/ics/get?entity=calendar&id=cal-…).
Individual event pages are schema.org JSON-LD. City pages, category pages and api.lu.ma discover
are not crawled: Luma's terms allow only publicly supported interfaces, and the official API
needs Luma Plus and only covers calendars you administer.
Eventbrite: v3 /organizers/{id}/events/ and /venues/{id}/events/ when EVENTBRITE_TOKEN is set.
Without a token, JSON-LD on the event page. The public search API (removed 2020) is not used.
A dead feed is recorded and skipped. Finished events already stored are never deleted.

Litteraturhuset Oslo: one public Sanity query (the CMS the site itself reads). No images.
Litteraturhuset i Bergen has no iCal, JSON-LD or public API; the programme page is parsed, and
only a keyword hit is opened for the organiser. Litteraturhuset Fredrikstad: the upcoming
programme page, then the WordPress event JSON for a keyword hit only (the full archive is not
paged). TicketCo and room-booking calendars are not sources. A mixed programme is kept only
when crypto_money_hit matches (crypto terms, or money/inflation in the title or the short text,
not a passing mention and not a children's listing).

Nasjonalbiblioteket: the upcoming Hva skjer page (event cards only; exhibitions are not events).
One WordPress request reads those slugs (start, end, price, text). The archive of past events
is not paged. schema.org Event JSON-LD is read only for a keyword hit, for the room and street.
No images. A per-event iCal link is not a calendar feed.

Bitcoinpolitisk institutt: the Kalender block on https://bpinorge.no/ (an Elementor grid).
Each card is a day, a Norwegian month and year, a type, a city and a title. The title's
link is the event URL when the card has one; otherwise the homepage. The arrangementer
page is an empty placeholder and is not read. A card with the same normalised title and
date as a Litteraturhuset, Nasjonalbiblioteket or Polyteknisk row is not added again.
No clock is published on the card, so the row is that civil day. No images."""
import argparse, datetime as dt, hashlib, json, os, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
from html import unescape as html_unescape
import requests
from bs4 import BeautifulSoup
from event_block import blocked_event, blocked_source
import site_url
from tools.event_description import language_of, prefer as prefer_description, record as description_record
from tools.event_select import explicit_attendee_count, explicit_ics_count
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
def _apply_next_description(html, events):
    """Meetup puts the full description in __NEXT_DATA__, and a short one in JSON-LD."""
    s = BeautifulSoup(html or "", "lxml")
    node = s.find("script", id="__NEXT_DATA__")
    if node is None or not node.string:
        return
    try:
        data = json.loads(node.string)
    except Exception:
        return
    ev = ((data.get("props") or {}).get("pageProps") or {}).get("event") or {}
    if not isinstance(ev, dict):
        return
    desc = ev.get("description") or ""
    if not isinstance(desc, str) or not desc.strip():
        return
    url = (ev.get("eventUrl") or "").split("?")[0].rstrip("/")
    title = ev.get("title") or ""
    for row in events:
        row_url = (row.get("url") or "").split("?")[0].rstrip("/")
        if (url and row_url == url) or (title and row.get("title") == title):
            if len(desc) > len(row.get("description") or ""):
                row["description"] = desc
                row["description_lang"] = language_of(desc, None, None)
def jsonld_events(html, tz="Europe/Oslo"):
    s = BeautifulSoup(html, "lxml"); out = []
    html_lang = s.html.get("lang") if s.html else None
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
            raw_desc = x.get("description") or ""
            if not isinstance(raw_desc, str): raw_desc = ""
            desc = BeautifulSoup(raw_desc, "lxml").get_text("\n")
            # A stated registered-count only. maximumAttendeeCapacity is seats, not people who signed up.
            out.append({"title": x.get("name"), "start": parse_dt(x.get("startDate"), tz), "end": parse_dt(x.get("endDate"), tz), "place": place or None,
                        "city": (city or "").strip() or None, "country_hint": ctry if isinstance(ctry, str) else None, "online": online,
                        "organiser": org.get("name") if isinstance(org, dict) else None,
                        "url": x.get("url"), "description": desc,
                        "description_lang": language_of(desc, x.get("inLanguage"), html_lang),
                        "paid": (max(prices) > 0) if prices else None, "attendees_count": explicit_attendee_count(x)})
    _apply_next_description(html, out)
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
                    "city": None, "online": False, "organiser": f.get("ORGANIZER_CN"), "url": url, "description": desc,
                    "description_lang": language_of(desc), "paid": None, "attendees_count": explicit_ics_count(f)})
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
def _start_key(e):
    s = e.get("start")
    if isinstance(s, str):
        try: s = dt.datetime.fromisoformat(s)
        except ValueError: return None
    return s.astimezone(UTC) if hasattr(s, "astimezone") and getattr(s, "tzinfo", None) else s
def _bare_url(u):
    return (u or "").split("?")[0].split("#")[0].rstrip("/").lower()
def similar_titles(a, b):
    """Exact, one a prefix of the other (a subtitle added later), or close by edit ratio."""
    import difflib
    na, nb = _norm(a), _norm(b)
    if not na or not nb: return False
    if na == nb: return True
    short, long_ = sorted((na, nb), key=len)
    if len(short) >= 8 and (long_ + " ").startswith(short + " "): return True  # whole-word prefix: a subtitle was added
    if re.findall(r"\d+", na) != re.findall(r"\d+", nb): return False  # "2026" vs "2027", "part 1" vs "part 2"
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.9
def _venue(e): return _norm(" ".join(x for x in [e.get("place"), e.get("city")] if x))
def same_event(a, b):
    """Same listing when the titles match (exact, prefix or near) on the same date and venue,
    or on the same start time at the same venue, or with the same event URL on the same date."""
    if _day(a) is None or _day(a) != _day(b): return False
    if not similar_titles(a.get("title"), b.get("title")): return False
    va, vb = _venue(a), _venue(b)
    venue_ok = not (va and vb and va not in vb and vb not in va)
    url_ok = bool(_bare_url(a.get("url")) and _bare_url(a.get("url")) == _bare_url(b.get("url")))
    sa, sb = _start_key(a), _start_key(b)
    if _norm(a.get("title")) == _norm(b.get("title")): return venue_ok or url_ok
    return url_ok or (venue_ok and sa is not None and sa == sb)
def merge_event(keep, other):
    """Fold other into keep: fuller title, missing fields, richest description. Nothing is dropped."""
    if len(_norm(other.get("title"))) > len(_norm(keep.get("title"))): keep["title"] = other["title"]
    for k, v in other.items():
        if k in ("id", "title", "description"): continue
        if v not in (None, "", [], {}) and keep.get(k) in (None, "", [], {}): keep[k] = v
    if other.get("found") and keep.get("found") and other["found"] < keep["found"]: keep["found"] = other["found"]
    if isinstance(other.get("description"), dict): prefer_description(keep, other["description"])
    return keep
def dedupe_events(rows):
    """Merge duplicate rows. The row with the fuller title is kept. Returns (rows, {removed_id: kept_id})."""
    out, moved = [], {}
    for e in rows:
        i = next((n for n, k in enumerate(out) if same_event(e, k)), None)
        if i is None: out.append(e); continue
        keep, drop = out[i], e
        if len(_norm(drop.get("title"))) > len(_norm(keep.get("title"))): keep, drop = drop, keep
        out[i] = merge_event(keep, drop); moved[drop["id"]] = keep["id"]
    for a, b in list(moved.items()):
        while b in moved: b = moved[b]
        moved[a] = b
    return out, moved
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
    desc = BeautifulSoup(_eb_text(raw.get("description")), "lxml").get_text("\n")
    return {"title": BeautifulSoup(_eb_text(raw.get("name")), "lxml").get_text(" ").strip() or None,
            "start": parse_dt(start.get("utc") or start.get("local"), start.get("timezone") or tz),
            "end": parse_dt(end.get("utc") or end.get("local"), end.get("timezone") or tz),
            "place": ", ".join(dict.fromkeys(parts)) or None,
            "city": (addr.get("city") or "").strip() or None,
            "country_hint": addr.get("country") if isinstance(addr.get("country"), str) else None,
            "online": online, "organiser": org.get("name"), "url": raw.get("url"),
            "description": desc, "description_lang": language_of(desc),
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
_LIST_MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
def listing_blocked(html):
    s = BeautifulSoup(html or "", "lxml"); title = s.title.string if s.title and s.title.string else ""
    return "Just a moment" in title
def listing_event_links(html, base, pattern):
    """Event links on a listing page. pattern is matched against the path and the raw href. No images."""
    s = BeautifulSoup(html or "", "lxml"); rx = re.compile(pattern); out, seen = [], set()
    for a in s.find_all("a", href=True):
        raw = a["href"].split("#")[0].split("?")[0]
        if not raw or raw.startswith(("mailto:", "javascript:")): continue
        absu = urllib.parse.urljoin(base, raw); path = urllib.parse.urlparse(absu).path or raw
        if not (rx.search(path) or rx.search(raw)): continue
        if absu in seen: continue
        seen.add(absu); out.append({"url": absu, "text": re.sub(r"\s+", " ", a.get_text(" ", strip=True))})
    return out
def listing_span(text):
    """First and last 'Mon D, YYYY' dates in a listing card, used only to order and skip finished cards."""
    found = []
    for m in re.finditer(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),\s+(20\d\d)", text or "", re.I):
        try: found.append(dt.date(int(m.group(3)), _LIST_MON[m.group(1)[:3].lower()], int(m.group(2))))
        except ValueError: continue
    return (found[0], found[-1]) if found else (None, None)
def civil_from_utc_midnight(d, tz, end=False):
    """00:00:00Z means that calendar day on the listing, not midnight UTC. Keep the day in tz (end of that day if end)."""
    if not d: return d
    u = d.astimezone(UTC)
    if (u.hour, u.minute, u.second, u.microsecond) != (0, 0, 0, 0): return d
    if end: return dt.datetime(u.year, u.month, u.day, 23, 59, tzinfo=ZoneInfo(tz))
    return dt.datetime(u.year, u.month, u.day, 0, 0, tzinfo=ZoneInfo(tz))
def venue_place(html):
    """Street address from a Venue label. Text only; photos on the page are ignored."""
    if not html: return None
    s = BeautifulSoup(html, "lxml")
    for node in s.find_all(string=re.compile(r"^\s*Venue\s*$")):
        card = node.find_parent(attrs={"data-slot": "card"}) or node.find_parent("div")
        if card is None: continue
        p = card.find("p")
        if p is None: continue
        lines = [ln.strip(" ,") for ln in p.get_text("\n").splitlines() if ln.strip()]
        if not lines: continue
        place = ", ".join(dict.fromkeys(lines))
        return place[:300].rsplit(",", 1)[0] if len(place) > 300 else place
    return None
def listing_jsonld_events(src, listing_html, fetch_text, matches, today, tz):
    """Follow event links on a listing and read schema.org Event JSON-LD. fetch_text(url) returns HTML.
    Raises if the listing is a bot challenge. Returns (events, links_seen, page_errors)."""
    if listing_blocked(listing_html): raise RuntimeError("Cloudflare challenge instead of the listing")
    links = listing_event_links(listing_html, src["url"], src.get("link_pattern") or r"/event-[a-z0-9-]+$")
    if not src.get("trusted"): links = [x for x in links if matches(x["text"])]
    def start_of(x):
        a, _b = listing_span(x["text"]); return a or dt.date.max
    kept = []
    for x in links:
        a, b = listing_span(x["text"]); last = b or a
        if last and last < today: continue
        kept.append(x)
    kept.sort(key=start_of); cap = int(src.get("max_links") or 40)
    events, errors = [], []
    for x in kept[:cap]:
        try: html = fetch_text(x["url"])
        except Exception as ex:
            errors.append(f"{x['url']}: {type(ex).__name__}: {ex}"); continue
        if listing_blocked(html):
            errors.append(f"{x['url']}: Cloudflare challenge"); continue
        for ev in jsonld_events(html, tz):
            ev["start"] = civil_from_utc_midnight(ev.get("start"), tz, end=False)
            ev["end"] = civil_from_utc_midnight(ev.get("end"), tz, end=True)
            venue = venue_place(html)
            if venue and (any(ch.isdigit() for ch in venue) or venue.count(",") >= 2): ev["place"] = venue
            if not ev.get("url"): ev["url"] = x["url"]
            events.append(ev)
    return events, len(links), errors
CITIES = {"NO": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Kristiansand", "Tromsø", "Bodø", "Drammen", "Fredrikstad", "Ålesund", "Fornebu", "Lysaker", "Lillehammer"],
          "SE": ["Stockholm", "Göteborg", "Gothenburg", "Malmö", "Uppsala", "Linköping", "Örebro", "Västerås", "Umeå", "Lund", "Luleå", "Boden"],
          "DK": ["København", "Copenhagen", "Frederiksberg", "Aarhus", "Odense", "Aalborg", "Esbjerg", "Kolding", "Roskilde", "Lyngby"],
          "FI": ["Helsinki", "Helsingfors", "Espoo", "Tampere", "Turku", "Åbo", "Oulu", "Vantaa", "Jyväskylä"],
          "IS": ["Reykjavík", "Reykjavik", "Akureyri", "Kópavogur", "Hafnarfjörður"]}
CC = {"NO": "NO", "NOR": "NO", "NORWAY": "NO", "SE": "SE", "SWE": "SE", "SWEDEN": "SE", "DK": "DK", "DNK": "DK", "DENMARK": "DK", "FI": "FI", "FIN": "FI", "FINLAND": "FI", "IS": "IS", "ISL": "IS", "ICELAND": "IS"}
def _attendee_block(count, name, url, retrieved):
    """Store a registered count only with the page it came from and when it was read."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 0: return None
    if not name or not url: return None
    return {"count": count, "source_name": name, "source_url": url, "retrieved": retrieved}
def _place_block(name, url, retrieved):
    if not name or not url: return None
    return {"name": name, "url": url, "retrieved": retrieved}
def retain_events(rows):
    """Every event stays, including after it has ended. Only a predatory listing is removed."""
    return [e for e in (rows or []) if not blocked_event(e)]
def guess_city(place):
    for c, cs in CITIES.items():
        for x in cs:
            if place and re.search(rf"\b{x}\b", place, re.I): return x, c
    return None, None

def carry_over_approvals(ap, moved):
    """Move editor decisions from a merged-away event id to the kept id (moved: removed id -> kept id).
    Works on the approvals dict from queue/approved.json or from D1, in place. Returns ap."""
    if not isinstance(ap, dict) or not moved: return ap
    moved = {a: b for a, b in moved.items() if not str(a).startswith("_")}
    for key in ("approve", "reject", "ready_for_owner", "sponsored"):
        ids = ap.get(key)
        if isinstance(ids, list):
            out = []
            for i in ids:
                j = moved.get(i, i)
                if j not in out: out.append(j)
            ap[key] = out
    for key in ("notes", "notes_i18n", "sponsor", "paid", "title_en"):
        m = ap.get(key)
        if not isinstance(m, dict): continue
        for old, new in moved.items():
            if old not in m: continue
            v = m.pop(old)
            if new not in m: m[new] = v
            elif key == "notes" and isinstance(v, str) and v and v not in m[new]: m[new] = v + " " + m[new]
            elif key == "notes_i18n" and isinstance(v, dict) and isinstance(m[new], dict):
                for l, t in v.items():
                    if t and t not in (m[new].get(l) or ""): m[new][l] = (t + " " + (m[new].get(l) or "")).strip()
    return ap

def _drop_queue_ids(gone, log, base=None):
    """Remove predatory event ids from the editor queue and the approval list, when those files exist."""
    root = base or ROOT
    qf = os.path.join(root, "queue", "review.json"); q = _load(qf, None)
    if isinstance(q, dict) and isinstance(q.get("events_pending"), list):
        kept = [e for e in q["events_pending"] if e.get("id") not in gone and not blocked_event(e)]
        if len(kept) != len(q["events_pending"]):
            q["events_pending"] = kept; _save(qf, q); log("event: removed predatory listings from the editor queue")
    af = os.path.join(root, "queue", "approved.json"); ap = _load(af, None)
    evs = ap.get("events") if isinstance(ap, dict) else None
    if not isinstance(evs, dict): return
    changed = False
    for key in ("approve", "reject", "ready_for_owner", "sponsored"):
        if isinstance(evs.get(key), list):
            nxt = [i for i in evs[key] if i not in gone]
            if nxt != evs[key]: evs[key] = nxt; changed = True
    for key in ("notes", "notes_i18n", "sponsor", "paid", "title_en"):
        if isinstance(evs.get(key), dict):
            for i in gone:
                if evs[key].pop(i, None) is not None: changed = True
    if changed: _save(af, ap); log("event: removed predatory listings from the approval list")

_MONEY_STRONG = re.compile(
    r"(?:"
    r"\bbitcoins?\b|\bBTC\b|\bsatoshis?\b|"
    r"\bkryptovaluta\w*|\bkrypto(?:en|er)?\b|\bkrypto(?:revolusjon|basert|selskap|marked|børs|eiendel|handel|investor|verden|vinter)\w*|"
    r"\bcryptocurrenc\w*|\bcrypto\b|"
    r"\bblokkjede\w*|\bblockchains?\b|\bblockkedj\w*|\bblokkæde\w*|\blohkoketju\w*|\bbálkakeðj\w*|"
    r"\bweb3\b|\bethereum\b|\bstablecoins?\b|\bCBDC\b|"
    r"\bsentralbank\w*|\bcentral\s+banks?\b|\bkeskuspank\w*|\bse[ðd]labank\w*|\briksbanks?\b|"
    r"\bcantillon\w*|"
    r"\bpengeteori\w*|\bpengepolitikk\w*|\bpengevesen\w*|\bpengesystem\w*|"
    r"\bpenningteori\w*|\bpenningpolitik\w*|"
    r"\brahapoliti\w*|\brahateori\w*|"
    r"\bmonetær\w*|\bmonetaer\w*|\bmonetary\s+(?:policy|theory|economics|system)\b|"
    r"\bdigitale\s+penger\b|\bdigitale\s+pengar\b|\be-krona\w*"
    r")",
    re.I,
)
# Whole words only. "penger" inside premiepenger or kulturpenger does not count.
_MONEY_WEAK = re.compile(
    r"\b(?:penger|pengar|penge|money|inflasjon\w*|inflation\w*|inflaatio\w*|ver[ðd]b[oó]lg\w*)\b",
    re.I,
)
_MONEY_CHILD = re.compile(
    r"\b(?:skolebes[øo]k|fortellerstund|barnehage|barn og unge|eventyrstund|småbarn|smabarn)\b",
    re.I,
)
_NN_MARK = re.compile(
    r"\b(?:kven|ikkje|enno|pengar|meinte|noko|kva|gjera|skreiv|kvifor|eit|berre|vert|læra|døydde|myntar)\b",
    re.I,
)
_NO_MONTH = {n: i for i, n in enumerate(
    ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "desember"], 1)}
_FRED_WHEN = re.compile(
    r"(\d{1,2})\.\s+([A-Za-zæøåÆØÅ]+)\s+(20\d\d)\s*\|\s*kl\.?\s*(\d{1,2})[.:](\d{2})",
    re.I,
)
_FRED_ARR = re.compile(r"Arr\.\s+(.+?)(?:\s+Les mer\b|$)", re.I)
SANITY_QUERY = """
{
  "address": *[_id == "configuration"][0].address[].children[].text,
  "events": *[_type == "event" && fromArchive != true && count(dates[eventStart >= "NOW"]) > 0]{
    "title_nb": title.nb,
    "title_en": title.en,
    "desc_nb": description.nb,
    "desc_en": description.en,
    "slug": slug.current,
    "english": english,
    "dates": dates[]{"eventStart": eventStart, "eventDuration": eventDuration},
    "organizers": organizers[]->title,
    "room": venues[0].room->title,
    "blocks_nb": content.nb[]{"spans": children[].text},
    "blocks_en": content.en[]{"spans": children[].text}
  }
}
"""


def crypto_money_hit(title, lead="", body=""):
    """True for a crypto term, or for money/inflation in the title or the short text.

    A strong term counts in the title, the short text and the body. A bare word such as
    penger, pengar, money or inflasjon counts only in the title and the short text, and
    not on a children's listing. A passing mention in a long novel blurb is not enough.
    kryptisk and kryptografi are not crypto. premiepenger is not penger.
    """
    head = f"{title or ''} {lead or ''}"
    if _MONEY_STRONG.search(f"{head} {body or ''}"):
        return True
    if _MONEY_CHILD.search(head):
        return False
    return bool(_MONEY_WEAK.search(head))


def source_keeps(ev, src, trusted, matches):
    """False drops a row from a mixed calendar. A trusted source keeps every dated row."""
    if trusted:
        return True
    if (src or {}).get("keyword_profile") == "crypto-money":
        lead = ev.get("lead")
        if lead is None:
            lead = ev.get("description") or ""
        return crypto_money_hit(ev.get("title"), lead, ev.get("body") or "")
    text = f"{ev.get('title') or ''} {ev.get('description') or ''} {ev.get('place') or ''}"
    return bool(matches(text))


def prose_lang(text, fallback=None):
    """Nynorsk when the wording is clearly nn. The CMS locale tag is often nb for that text."""
    if len(_NN_MARK.findall(text or "")) >= 2:
        return "nn"
    return fallback


def _plain_blocks(blocks):
    lines = []
    for block in blocks or []:
        if isinstance(block, str):
            spans = [block]
        elif isinstance(block, dict):
            spans = block.get("spans") or []
            if isinstance(spans, str):
                spans = [spans]
        else:
            continue
        line = "".join(s for s in spans if isinstance(s, str)).strip()
        if line:
            lines.append(line)
    return lines


def _street_line(address_text):
    """The street line of a house address. A postcode line is not a street."""
    for ln in (address_text or "").splitlines():
        ln = ln.strip()
        if re.search(r"\d", ln) and not re.match(r"\d{4}\b", ln):
            return ln
    return None


def _venue_place(src, room=None, named=None):
    """Room, the house name and the street. An off-site name replaces the house street."""
    house = src.get("venue") or src.get("name") or ""
    street = src.get("address") or ""
    if named and house and named.casefold() not in house.casefold() and house.casefold() not in named.casefold():
        return named
    bits = [b for b in (room, named or house, street) if b]
    return ", ".join(dict.fromkeys(bits)) or None


def sanity_events(src, payload, tz):
    """Upcoming events from one Sanity query result. Images are not read."""
    data = payload.get("result") if isinstance(payload, dict) and "result" in payload else payload
    if not isinstance(data, dict):
        return []
    if data.get("error"):
        raise RuntimeError(str(data.get("error"))[:180])
    bits = data.get("address") or []
    address_text = "\n".join(x for x in bits if isinstance(x, str)) if isinstance(bits, list) else (bits or "")
    street = _street_line(address_text) or src.get("address")
    src = dict(src, address=street)
    site = (src.get("site") or "https://www.litteraturhuset.no").rstrip("/")
    out = []
    for raw in data.get("events") or []:
        if not isinstance(raw, dict):
            continue
        slug = raw.get("slug") or ""
        if isinstance(slug, dict):
            slug = slug.get("current") or ""
        slug = str(slug).strip().strip("/")
        title = (raw.get("title_nb") or raw.get("title_en") or "").strip()
        lead = (raw.get("desc_nb") or raw.get("desc_en") or "").strip()
        blocks = raw.get("blocks_nb") or raw.get("blocks_en") or []
        body_lines = _plain_blocks(blocks)
        body = "\n".join(body_lines)
        orgs = [o.strip() for o in (raw.get("organizers") or []) if isinstance(o, str) and o.strip()]
        if not slug or not crypto_money_hit(title, " ".join(x for x in (lead, " ".join(orgs)) if x), body):
            continue
        desc_parts = [lead] if lead else []
        for line in body_lines:
            if not lead or line.strip() != lead.strip():
                desc_parts.append(line)
        description = "\n".join(desc_parts)
        room = (raw.get("room") or "").strip() or None
        for slot in raw.get("dates") or []:
            if not isinstance(slot, dict):
                continue
            start = parse_dt(slot.get("eventStart"), tz)
            if not start:
                continue
            dur = slot.get("eventDuration")
            end = None
            if isinstance(dur, (int, float)) and not isinstance(dur, bool) and dur > 0:
                end = start + dt.timedelta(minutes=int(dur))
            path = "en" if raw.get("english") else (src.get("lang_path") or "nb")
            out.append({
                "title": title or None, "start": start, "end": end,
                "place": _venue_place(src, room), "city": src.get("city"), "country_hint": src.get("country"),
                "online": False, "organiser": ", ".join(orgs) or None,
                "url": f"{site}/{path}/arrangement/{slug}",
                "description": description, "description_lang": prose_lang(f"{title}\n{description}", "nb"),
                "lead": lead, "body": body, "paid": None,
            })
    return out


def _program_date(day, month, today):
    if not day or not month or not (1 <= int(month) <= 12):
        return None
    y = today.year
    try:
        d = dt.date(y, int(month), int(day))
    except ValueError:
        return None
    if d < today - dt.timedelta(days=1):
        try:
            d = dt.date(y + 1, int(month), int(day))
        except ValueError:
            return None
    return d


def _clock(day, hm, tz):
    if not day or not hm:
        return None
    return dt.datetime(day.year, day.month, day.day, int(hm[0]), int(hm[1]), tzinfo=ZoneInfo(tz))


def webflow_program_cards(html, base):
    """Cards on a Webflow programme page: title, link, day, month, clock, room, blurb. No images."""
    s = BeautifulSoup(html or "", "lxml")
    cards, seen = [], set()
    for item in s.select(".program-item"):
        a = item.select_one("a.event-name-in-grid") or item.find("a", href=re.compile(r"/arrangement/"))
        if a is None or not a.get("href"):
            continue
        url = urllib.parse.urljoin(base, a["href"].split("#")[0].split("?")[0])
        if url in seen:
            continue
        seen.add(url)
        date_el, time_el = item.select_one(".date-event"), item.select_one(".time-event")
        nums = [int(x) for x in re.findall(r"\d+", date_el.get_text(" ") if date_el else "")]
        day, month = (nums[0], nums[1]) if len(nums) >= 2 else (None, None)
        hm = re.findall(r"(\d{1,2}):(\d{2})", time_el.get_text(" ") if time_el else "")
        room_el, blurb_el = item.select_one(".heading-3"), item.select_one(".text-block")
        gratis = item.select_one(".event-gratis")
        paid = False if gratis is not None and "w-condition-invisible" not in " ".join(gratis.get("class") or []) else None
        cards.append({
            "url": url, "title": a.get_text(" ", strip=True), "day": day, "month": month,
            "start_hm": hm[0] if hm else None, "end_hm": hm[1] if len(hm) > 1 else None,
            "room": room_el.get_text(" ", strip=True) if room_el else None,
            "blurb": blurb_el.get_text(" ", strip=True) if blurb_el else "",
            "paid": paid,
        })
    nxt = s.select_one("a.w-pagination-next")
    next_url = None
    if nxt is not None and nxt.get("href") and "w-condition-invisible" not in " ".join(nxt.get("class") or []):
        href = nxt["href"].strip()
        if href and not href.startswith(("#", "javascript:")):
            next_url = urllib.parse.urljoin(base, href)
    return cards, next_url


def webflow_organiser(html):
    s = BeautifulSoup(html or "", "lxml")
    box = s.select_one(".event-page-arrangor")
    if box is None:
        return None
    text = re.sub(r"^Arrangør:\s*", "", box.get_text(" ", strip=True), flags=re.I).strip()
    return text or None


def webflow_events(src, cards, today, tz, page_html):
    """Keyword hits only. page_html(url) is called for those hits, for the organiser line."""
    cap = int(src.get("max_links") or 8)
    hits = [c for c in cards if crypto_money_hit(c.get("title"), c.get("blurb") or "")][:cap]
    out = []
    for c in hits:
        day = _program_date(c.get("day"), c.get("month"), today)
        start = _clock(day, c.get("start_hm"), tz)
        end = _clock(day, c.get("end_hm"), tz)
        if end and start and end <= start:
            end = None
        if not c.get("title") or not start:
            continue
        org = None
        try:
            org = webflow_organiser(page_html(c["url"]))
        except Exception:
            org = None
        out.append({
            "title": c["title"], "start": start, "end": end,
            "place": _venue_place(src, c.get("room")), "city": src.get("city"), "country_hint": src.get("country"),
            "online": False, "organiser": org, "url": c["url"],
            "description": c.get("blurb") or "", "description_lang": prose_lang(c.get("blurb") or "", "nb"),
            "lead": c.get("blurb") or "", "body": "", "paid": c.get("paid"),
        })
    return out


def _paa_place(title):
    m = re.search(r"\bpå\s+(.+)$", title or "", flags=re.I)
    return m.group(1).strip(" .") if m else None


def wp_program_cards(html, base):
    """Upcoming cards on an Eventchamp programme page. The archive is not read."""
    s = BeautifulSoup(html or "", "lxml")
    # The programme page has several tab lists. The first is often empty.
    items = []
    for root in s.select(".ss-list-events"):
        items.extend(root.select(".item"))
    if not items:
        items = s.select(".item")
    cards, seen = [], set()
    for item in items:
        a = item.find("a", href=re.compile(r"/event/"))
        if a is None or not a.get("href"):
            continue
        url = urllib.parse.urljoin(base, a["href"].split("#")[0].split("?")[0])
        if url in seen:
            continue
        seen.add(url)
        title_el = item.select_one(".ss-height-match")
        if title_el is not None and title_el.get_text(strip=True):
            title = title_el.get_text(" ", strip=True)
        else:
            heads = [h.get_text(" ", strip=True) for h in item.find_all(["h2", "h3", "h4"])]
            heads = [h for h in heads if h and h.casefold() != "les mer"]
            title = max(heads, key=len) if heads else ""
        text = re.sub(r"\s+", " ", item.get_text(" ", strip=True))
        if not title:
            m0 = _FRED_WHEN.search(text)
            if m0:
                title = re.sub(r"\b(?:man|tirs|ons|tors|fre|lør|lor|søn|son)\.?\s*$", "", text[:m0.start()], flags=re.I).strip()
        m = _FRED_WHEN.search(text)
        if not title or not m:
            continue
        month = _NO_MONTH.get(m.group(2).lower().rstrip("."))
        if not month:
            continue
        arr = _FRED_ARR.search(text)
        cards.append({
            "url": url, "title": title,
            "day": int(m.group(1)), "month": month, "year": int(m.group(3)),
            "start_hm": (m.group(4), m.group(5)),
            "organiser": arr.group(1).strip(" .") if arr else None,
            "named_place": _paa_place(title),
        })
    return cards


def wp_paid(acf):
    """A stated price or a stated free entry. Empty fields stay unknown."""
    if not isinstance(acf, dict):
        return None
    gratis = str(acf.get("gratis") or "").strip().lower()
    if gratis in ("1", "true", "ja", "yes", "gratis"):
        return False
    pris = str(acf.get("pris") or "")
    if re.search(r"\bgratis\b", pris, re.I):
        return False
    m = re.search(r"(\d+)", pris.replace(" ", "").replace("\xa0", ""))
    if m and int(m.group(1)) > 0:
        return True
    return None


def wp_events(src, cards, tz, detail):
    """detail(slug) returns the WordPress event JSON for a keyword hit, or None. Other cards are not requested."""
    cap = int(src.get("max_links") or 8)
    hits = [c for c in cards if crypto_money_hit(c.get("title"), c.get("organiser") or "")][:cap]
    out = []
    for c in hits:
        try:
            day = dt.date(c["year"], c["month"], c["day"])
        except ValueError:
            continue
        start = _clock(day, c.get("start_hm"), tz)
        if not start:
            continue
        paid, excerpt = None, ""
        slug = c["url"].rstrip("/").rsplit("/", 1)[-1]
        raw = None
        try:
            raw = detail(slug)
        except Exception:
            raw = None
        if isinstance(raw, dict):
            paid = wp_paid(raw.get("acf"))
            ex = raw.get("excerpt")
            if isinstance(ex, dict):
                excerpt = BeautifulSoup(ex.get("rendered") or "", "lxml").get_text(" ", strip=True)
        out.append({
            "title": c["title"], "start": start, "end": None,
            "place": _venue_place(src, named=c.get("named_place")),
            "city": src.get("city"), "country_hint": src.get("country"), "online": False,
            "organiser": c.get("organiser"), "url": c["url"],
            "description": excerpt, "description_lang": prose_lang(excerpt, "nb"),
            "lead": " ".join(x for x in (c["title"], c.get("organiser") or "") if x),
            "body": excerpt, "paid": paid,
        })
    return out


_NB_ARR = re.compile(
    r"\barrangerer\s+(.+?)\s*(?:\([^)]*\)|\s+tidenes\b|\s+den\b|\s+et\b|\s+en\b|$)",
    re.I,
)


def nb_program_cards(html, base):
    """Upcoming event cards on Hva skjer. Exhibitions and images are not cards."""
    s = BeautifulSoup(html or "", "lxml")
    cards, seen = [], set()
    for card in s.select(".is-post-type-event"):
        a = card.select_one("a[href]")
        title_el = card.select_one(".t2-post-title")
        if a is None or not a.get("href") or title_el is None:
            continue
        url = urllib.parse.urljoin(base, a["href"].split("#")[0].split("?")[0])
        path = urllib.parse.urlparse(url).path or ""
        if "/hva-skjer/" not in path or url in seen:
            continue
        seen.add(url)
        label = card.select_one(".nb-post-label")
        sub = card.select_one(".nb-post-subtitle")
        cards.append({
            "url": url,
            "slug": url.rstrip("/").rsplit("/", 1)[-1],
            "title": title_el.get_text(" ", strip=True),
            "label": label.get_text(" ", strip=True) if label else "",
            "subtitle": sub.get_text(" ", strip=True) if sub else "",
        })
    return cards


def nb_query_url(src, slugs):
    """One WordPress request for the upcoming slugs. The past archive is not requested."""
    api = (src.get("api") or "https://www.nb.no/wp-json/wp/v2/event").split("?")[0]
    q = urllib.parse.urlencode({
        "slug": ",".join(slugs),
        "_fields": "slug,link,title,content,meta",
        "per_page": str(min(100, max(len(slugs), 1))),
    })
    return api + "?" + q


def nb_plain(html):
    """Organiser text. The practical-information block and every link target are left out."""
    s = BeautifulSoup(html or "", "lxml")
    root = s.select_one(".wp-block-post-content") or s
    text = root.get_text("\n", strip=True)
    return re.split(r"\bPraktisk informasjon\b", text, maxsplit=1, flags=re.I)[0].strip()


def nb_lead_body(plain):
    parts = [p.strip() for p in re.split(r"\n+", plain or "") if p.strip()]
    return " ".join(parts[:2]), " ".join(parts[2:])


def nb_organiser_name(text, label):
    """The name after «arrangerer». «Ekstern arrangør» is a category, not a name."""
    m = _NB_ARR.search(re.sub(r"\s+", " ", text or ""))
    if m:
        name = m.group(1).strip(" .,-")
        if len(name) >= 3:
            return name
    if re.search(r"\bekstern\b", label or "", re.I):
        return None
    return None


def nb_paid(price_text):
    """A stated free entry, or a price that contains a number. Empty stays unknown."""
    t = re.sub(r"\s+", " ", price_text or "").strip()
    if not t:
        return None
    if re.search(r"\bgratis\b", t, re.I):
        return False
    if re.search(r"\d", t):
        return True
    return None


def nb_format_place(place):
    """«House - Room, street» becomes «Room, House, street». The city is not part of the place."""
    if not place:
        return None
    m = re.match(r"^(?P<house>.+?)\s+[-–]\s+(?P<room>[^,]+),\s*(?P<street>.+)$", place.strip())
    if not m:
        return place.strip()
    return ", ".join(dict.fromkeys([
        m.group("room").strip(), m.group("house").strip(), m.group("street").strip()]))


def nb_events(src, cards, records, tz, page_html):
    """Keyword hits only. page_html(url) is the event page, read for JSON-LD place. Other pages are not opened."""
    by_slug = {}
    for raw in records or []:
        if isinstance(raw, dict) and raw.get("slug"):
            by_slug[raw["slug"]] = raw
    cap = int(src.get("max_links") or 8)
    house = src.get("venue") or src.get("name") or "Nasjonalbiblioteket"
    prepared = []
    for c in cards:
        raw = by_slug.get(c.get("slug")) or {}
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        if meta.get("event_tba_datetime") is True:
            continue
        content = raw.get("content")
        rendered = content.get("rendered") if isinstance(content, dict) else ""
        plain = nb_plain(rendered)
        lead, body = nb_lead_body(plain)
        title_raw = raw.get("title")
        api_title = title_raw.get("rendered") if isinstance(title_raw, dict) else ""
        title = c.get("title") or BeautifulSoup(api_title or "", "lxml").get_text(" ", strip=True)
        if not crypto_money_hit(title, " ".join(x for x in (c.get("subtitle"), lead) if x), body):
            continue
        start = parse_dt(meta.get("event_start_datetime"), tz)
        end = parse_dt(meta.get("event_end_datetime"), tz)
        if end and start and end <= start:
            end = None
        if not title or not start:
            continue
        org = nb_organiser_name(plain, c.get("label"))
        if org is None and not re.search(r"\bekstern\b", c.get("label") or "", re.I):
            org = house
        prepared.append({
            "title": title, "start": start, "end": end, "url": c["url"],
            "organiser": org, "paid": nb_paid(meta.get("event_ticket_price_text")),
            "description": plain, "description_lang": prose_lang(plain, "nb"),
            "lead": lead, "body": body,
        })
    out = []
    for ev in prepared[:cap]:
        place, city = _venue_place(src), src.get("city")
        try:
            found = jsonld_events(page_html(ev["url"]), tz)
        except Exception:
            found = []
        match = next((x for x in found if similar_titles(x.get("title"), ev["title"])), None)
        if match is None and found:
            match = found[0]
        if match:
            place = nb_format_place(match.get("place")) or place
            city = match.get("city") or city
            if match.get("country_hint"):
                ev["country_hint"] = match["country_hint"]
            if ev.get("paid") is None and match.get("paid") is not None:
                ev["paid"] = match["paid"]
        ev["place"] = place
        ev["city"] = city
        ev["country_hint"] = ev.get("country_hint") or src.get("country")
        ev["online"] = False
        out.append(ev)
    return out


def squarespace_query_url(src):
    """The public JSON view of a Squarespace events collection (upcoming and a short past list)."""
    u = src["url"].split("?")[0]
    return u + "?format=json"


def squarespace_events(src, payload, tz, matches=None):
    """Upcoming items of a Squarespace events collection. Keyword hits only. Images are not read.

    With "keyword_profile": "crypto-money" the Litteraturhus filter is used. Otherwise the
    site-wide crypto filter (matches) is used: an economics festival is full of money talk,
    and only crypto, bitcoin and blockchain events belong on the calendar.

    startDate and endDate are epoch milliseconds (UTC); they are stored in the house time zone.
    Squarespace has no price field; a price line in the text is read when present.
    """
    items = (payload or {}).get("upcoming") if isinstance(payload, dict) else None
    out = []
    base = src.get("site") or src["url"]
    cap = int(src.get("max_links") or 8)
    for raw in items or []:
        if not isinstance(raw, dict) or not raw.get("title") or not raw.get("startDate"):
            continue
        title = html_unescape(BeautifulSoup(raw["title"], "lxml").get_text(" ", strip=True))
        lead = BeautifulSoup(raw.get("excerpt") or "", "lxml").get_text(" ", strip=True)
        body = BeautifulSoup(raw.get("body") or "", "lxml").get_text("\n", strip=True)
        if src.get("keyword_profile") == "crypto-money":
            if not crypto_money_hit(title, lead, body):
                continue
        elif matches is not None and not src.get("trusted") and not matches(f"{title} {lead} {body}"):
            continue
        z = ZoneInfo(tz)
        start = dt.datetime.fromtimestamp(int(raw["startDate"]) / 1000, UTC).replace(second=0, microsecond=0).astimezone(z)
        end = None
        if raw.get("endDate"):
            end = dt.datetime.fromtimestamp(int(raw["endDate"]) / 1000, UTC).replace(second=0, microsecond=0).astimezone(z)
            if end <= start:
                end = None
        loc = raw.get("location") if isinstance(raw.get("location"), dict) else {}
        room = html_unescape((loc.get("addressTitle") or "").strip()) or None
        street = html_unescape((loc.get("addressLine1") or "").strip())
        place = ", ".join(x for x in (room, street) if x) or _venue_place(src)
        url = urllib.parse.urljoin(base, raw.get("fullUrl") or "")
        price = re.search(r"(?:billett|pris|inngang)[^\n]{0,40}?(gratis|\d[\d .]*\s*(?:kr|,-))", body, re.I)
        paid = None
        if price:
            paid = False if price.group(1).lower() == "gratis" else True
        out.append({
            "title": title, "start": start, "end": end, "url": url,
            "place": place, "city": src.get("city"), "country_hint": src.get("country"), "online": False,
            "organiser": src.get("organiser"), "paid": paid,
            "description": "\n".join(x for x in (lead, body) if x), "description_lang": prose_lang(body, "nb"),
            "lead": lead, "body": body,
        })
        if len(out) >= cap:
            break
    return out


_BPI_MARK = re.compile(r"bpinorge|bitcoinpolitisk\s+institutt", re.I)
_VENUE_MARK = re.compile(
    r"litteraturhuset|litthusbergen|litthusfred|nasjonalbiblioteket|polyteknisk|(?:^|[./])nb\.no\b",
    re.I,
)


def _listing_blob(row, src=None):
    parts = [str((row or {}).get(k) or "") for k in ("source", "source_url", "url")]
    if src:
        parts.extend(str(src.get(k) or "") for k in ("name", "id", "url"))
    return " ".join(parts)


def bpi_venue_duplicate(ev, old, src=None):
    """Same normalised title and calendar day, one side BPI and the other a venue calendar.

    Litteraturhuset, Nasjonalbiblioteket and Polyteknisk already list some of these talks.
    The homepage often shortens the venue's title, so a whole-word prefix counts
    (the same rule as similar_titles). The place is not compared: the card usually names only the city.
    """
    if _day(ev) is None or _day(ev) != _day(old):
        return False
    if not similar_titles(ev.get("title"), old.get("title")):
        return False
    src_bpi = bool(src and _BPI_MARK.search(_listing_blob({}, src)))
    ev_bpi = src_bpi or bool(_BPI_MARK.search(_listing_blob(ev)))
    old_bpi = bool(_BPI_MARK.search(_listing_blob(old)))
    # A venue link on a BPI card is the event URL, not a second venue-calendar source.
    ev_venue = False if src_bpi else bool(_VENUE_MARK.search(_listing_blob(ev)))
    old_venue = bool(_VENUE_MARK.search(_listing_blob(old)))
    return (ev_bpi and old_venue and not old_bpi) or (old_bpi and ev_venue and not ev_bpi)


def bpi_kalender_cards(html, base):
    """Cards in the homepage Kalender block. No other page is opened and no image is read."""
    s = BeautifulSoup(html or "", "lxml")
    heading = None
    for h in s.find_all(["h2", "h3"]):
        if re.sub(r"\s+", " ", h.get_text(" ", strip=True)).casefold() == "kalender":
            heading = h
            break
    if heading is None:
        return []
    box = heading.find_parent(class_="e-con")
    grid = box.find_next_sibling(class_="e-con") if box is not None else None
    if grid is None:
        return []
    home = (base or "https://bpinorge.no/").split("#")[0].split("?")[0] or "https://bpinorge.no/"
    join_base = home if home.endswith("/") else home + "/"
    cards = []
    for card in grid.find_all(class_="e-con", recursive=False):
        day_el = None
        for h in card.find_all("h2"):
            if re.fullmatch(r"\d{1,2}", h.get_text(strip=True)):
                day_el = h
                break
        if day_el is None:
            continue
        when, kind, city = "", "", ""
        for p in card.find_all("p"):
            span1, span2 = p.select_one(".span1"), p.select_one(".span2")
            if span1 is not None or span2 is not None:
                if span1 is not None:
                    kind = re.sub(r"\s+", " ", span1.get_text(" ", strip=True))
                if span2 is not None:
                    city = re.sub(r"\s+", " ", span2.get_text(" ", strip=True))
                continue
            text = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
            if re.search(r"\b20\d\d\b", text):
                when = text
        m = re.search(r"([A-Za-zæøåÆØÅ]+)\s+(20\d\d)", when)
        month = _NO_MONTH.get(m.group(1).lower()) if m else None
        year = int(m.group(2)) if m else None
        title_el = card.find("h1")
        link = title_el.find("a", href=True) if title_el is not None else None
        if link is None:
            link = card.find("a", href=True)
        title = re.sub(r"\s+", " ", title_el.get_text(" ", strip=True)) if title_el is not None else ""
        if not title and link is not None:
            title = re.sub(r"\s+", " ", link.get_text(" ", strip=True))
        url = home
        if link is not None:
            href = (link.get("href") or "").strip()
            if href and not href.startswith(("#", "javascript:")):
                url = urllib.parse.urljoin(join_base, href.split("#")[0])
        if not title or not month or not year:
            continue
        try:
            day = int(day_el.get_text(strip=True))
            dt.date(year, month, day)
        except ValueError:
            continue
        cards.append({
            "title": title, "day": day, "month": month, "year": year,
            "city": city or None, "kind": kind or None, "url": url,
        })
    return cards


def bpi_events(src, cards, tz):
    """Dated rows from Kalender cards. The page states no clock, so the row is that civil day."""
    zone = ZoneInfo(tz)
    home = src.get("url") or "https://bpinorge.no/"
    out = []
    for c in cards or []:
        try:
            day = dt.date(int(c["year"]), int(c["month"]), int(c["day"]))
        except (KeyError, TypeError, ValueError):
            continue
        if not c.get("title"):
            continue
        out.append({
            "title": c["title"],
            "start": dt.datetime(day.year, day.month, day.day, 0, 0, tzinfo=zone),
            "end": dt.datetime(day.year, day.month, day.day, 23, 59, tzinfo=zone),
            "place": None, "city": c.get("city") or src.get("city"),
            "country_hint": None, "online": False, "organiser": None,
            "url": c.get("url") or home, "description": "", "description_lang": None,
            "lead": " ".join(x for x in (c.get("kind"), c.get("city")) if x),
            "body": "", "paid": None,
        })
    return out


def sanity_query_url(src, now):
    stamp = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    api = src.get("api") or ""
    query = SANITY_QUERY.replace("NOW", stamp)
    join = "&" if "?" in api else "?"
    return api + join + urllib.parse.urlencode({"query": query})


def run(get, robots_ok, matches, log, cfg, add_url=None, a=None, only=None, root=None, now=None):
    base = root or ROOT
    def lp(*parts): return os.path.join(base, *parts)
    for d in ("data", "state", "queue"): os.makedirs(lp(d), exist_ok=True)
    data = _load(lp("data", "events.json"), {"events": []})
    dropped = [e for e in data["events"] if blocked_event(e)]
    if dropped:
        gone = {e["id"] for e in dropped}
        data["events"] = [e for e in data["events"] if e["id"] not in gone]
        log(f"event: removed {len(dropped)} predatory conference listing(s)")
        _drop_queue_ids(gone, log, base)
    data["events"], merged = dedupe_events(data["events"])
    if merged:
        log(f"event: merged {len(merged)} duplicate listing(s): " + ", ".join(f"{a} -> {b}" for a, b in merged.items()))
        rd = _load(lp("data", "event_redirects.json"), {}); rd.update(merged); _save(lp("data", "event_redirects.json"), rd)
    by = {e["id"]: e for e in data["events"]}
    archive_rows = []
    ark = _load(lp("archive", "events.json"), {})
    if isinstance(ark, dict):
        for row in ark.get("events") or []:
            if isinstance(row, dict) and row.get("id") not in by:
                archive_rows.append(row)
    original = [dict(e) for e in data["events"]]  # non-predatory rows already stored are kept
    status = _load(lp("state", "source_status.json"), {}); now = now or dt.datetime.now(UTC)
    if now.tzinfo is None: now = now.replace(tzinfo=UTC)
    new = []
    def _fill(old, ev):
        for k in ("place", "city", "end", "organiser"):
            v = ev.get(k)
            if v and not old.get(k): old[k] = v.isoformat() if hasattr(v, "isoformat") else v
    def take(ev, src, trusted):
        if blocked_event(ev, src): return  # predatory listing: refused even when the source is marked trusted
        if not ev.get("title") or not ev.get("start"): return
        if not source_keeps(ev, src, trusted, matches): return
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
        twin = next((old for old in by.values() if same_event(ev, old) or bpi_venue_duplicate(ev, old, src)), None)
        if twin is None and any(bpi_venue_duplicate(ev, old, src) for old in archive_rows):
            return  # the venue calendar already has this title and date in the archive
        page = ev.get("url") or src.get("page") or src["url"]
        retrieved = now.isoformat(timespec="seconds")
        if twin:
            _fill(twin, ev)
            if len(_norm(ev.get("title"))) > len(_norm(twin.get("title"))): twin["title"] = ev["title"]  # a fuller title from a later read
            prefer_description(twin, description_record(ev.get("description"), ev.get("description_lang"), page, src.get("name"), retrieved, ev.get("title")))
            return  # same title, date and venue, whatever the URL
        i = eid(ev)
        attendees = _attendee_block(ev.get("attendees_count"), src["name"], page, retrieved)
        place_source = _place_block(src["name"], page, retrieved) if (ev.get("place") or ev.get("online")) else None
        if i in by:
            _fill(by[i], ev)
            # Fill a count or a place credit only when the row does not have one. Never replace a stored count.
            if attendees and not by[i].get("attendees"): by[i]["attendees"] = attendees
            if place_source and not by[i].get("place_source") and (by[i].get("place") or by[i].get("online") or ev.get("place") or ev.get("online")):
                by[i]["place_source"] = place_source
            prefer_description(by[i], description_record(ev.get("description"), ev.get("description_lang"), page, src.get("name"), retrieved, ev.get("title")))
            return
        if (ev.get("end") or ev["start"]) < now: return  # do not add a finished event; ones already stored stay
        complete = bool(ev.get("place") or ev.get("online")) and bool(ev.get("organiser"))
        rec = {"id": i, "title": ev["title"], "start": ev["start"].isoformat(), "end": ev["end"].isoformat() if ev.get("end") else None,
               "place": ev.get("place"), "city": ev.get("city"), "country": country, "online": bool(ev.get("online")), "organiser": ev.get("organiser"),
               "url": ev["url"], "source": src["name"], "source_url": src.get("page") or src["url"], "paid": ev.get("paid"),
               "sponsored": clear_kaupr_sponsor(None),
               "trusted_source": bool(trusted), "found": retrieved, "status": "pending",
               "note": None if complete else "missing place or organiser – check the organiser's page"}
        if attendees: rec["attendees"] = attendees
        if place_source: rec["place_source"] = place_source
        desc = description_record(ev.get("description"), ev.get("description_lang"), page, src.get("name"), retrieved, ev.get("title"))
        if desc: rec["description"] = desc
        data["events"].append(rec); by[i] = rec; new.append(rec)
    def fetch_page(u):
        if not robots_ok(u): raise RuntimeError("robots.txt disallows")
        r = get(u); r.raise_for_status(); return r
    sources = [s for s in cfg.get("event_sources", []) if not blocked_source(s)]
    refused = [s for s in cfg.get("event_sources", []) if blocked_source(s)]
    for src in refused:
        if only and src.get("id") not in only: continue
        status["ev-" + src["id"]] = {"checked": now.isoformat(timespec="seconds"), "ok": False, "entries": 0, "new": 0,
                                     "error": "blocked: predatory conference listing"}
        log(f"event {src.get('id', '?'):<28} blocked predatory conference listing")
    manual = a or argparse.Namespace(organiser=None, source_name=None)
    if add_url and blocked_event({"url": add_url, "organiser": manual.organiser},
                                 {"url": add_url, "name": manual.source_name, "organiser": manual.organiser}):
        log(f"event: refused {add_url} (predatory conference listing)")
    elif add_url:
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
        pause = cfg.get("min_delay_seconds", 2)
        ua = site_url.expand(cfg.get("user_agent") or ("NordicCryptoBot/0.1 (+" + site_url.BASE + "about/; news headline bot)"))
        for src in sources:
            if not src.get("enabled", True): continue
            if only and src["id"] not in only: continue
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
                elif src["type"] == "listing-jsonld":
                    r = fetch_page(src["url"])
                    evs, _n_links, page_errors = listing_jsonld_events(src, r.text, lambda u: fetch_page(u).text, matches, now.date(), tz)
                    n_found = len(evs)
                    for ev in evs: take(ev, src, src.get("trusted", False))
                    if page_errors and not evs: raise RuntimeError(page_errors[0][:180])
                    if page_errors: log(f"event {src['id']}: {len(page_errors)} event page(s) failed, first {page_errors[0][:120]}")
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
                            src2 = dict(src, page=u); take(ev, src2, src.get("trusted", False))
                elif src["type"] == "sanity-events":
                    # One public content query. Event pages and images are not fetched.
                    raw = json.loads(fetch_page(sanity_query_url(src, now)).text)
                    if isinstance(raw, dict) and raw.get("error"):
                        raise RuntimeError(str(raw.get("error"))[:180])
                    evs = sanity_events(src, raw, tz); n_found = len(evs)
                    for ev in evs: take(ev, src, src.get("trusted", False))
                elif src["type"] == "webflow-program":
                    # Programme HTML. No iCal or JSON-LD on this site. Only a keyword hit is opened.
                    page_url, seen_pages, cards, seen_urls = src["url"], 0, [], set()
                    while page_url and seen_pages < int(src.get("max_pages") or 3):
                        batch, nxt = webflow_program_cards(fetch_page(page_url).text, page_url)
                        for c in batch:
                            if c["url"] not in seen_urls:
                                seen_urls.add(c["url"]); cards.append(c)
                        seen_pages += 1
                        if not nxt or nxt == page_url: break
                        page_url = nxt
                    evs = webflow_events(src, cards, now.date(), tz, lambda u: fetch_page(u).text)
                    n_found = len(evs)
                    for ev in evs:
                        src2 = dict(src, page=ev["url"]); take(ev, src2, src.get("trusted", False))
                elif src["type"] == "wp-program":
                    # The upcoming programme page. The WordPress archive (thousands of past events) is not paged.
                    cards = wp_program_cards(fetch_page(src["url"]).text, src["url"])
                    api = (src.get("api") or "").rstrip("/")

                    def detail(slug, api=api):
                        if not api: return None
                        q = urllib.parse.urlencode({"slug": slug, "_fields": "link,excerpt,acf,event_start_date"})
                        body = json.loads(fetch_page(api + "?" + q).text)
                        if isinstance(body, list): return body[0] if body else None
                        return body if isinstance(body, dict) else None

                    evs = wp_events(src, cards, tz, detail); n_found = len(evs)
                    for ev in evs:
                        src2 = dict(src, page=ev["url"]); take(ev, src2, src.get("trusted", False))
                elif src["type"] == "bpi_kalender":
                    # Homepage Kalender only. Venue pages are not opened. The arrangementer placeholder is not read.
                    cards = bpi_kalender_cards(fetch_page(src["url"]).text, src["url"])
                    evs = bpi_events(src, cards, tz)
                    n_found = len(evs)
                    for ev in evs:
                        src2 = dict(src, page=ev.get("url") or src["url"])
                        take(ev, src2, src.get("trusted", False))
                elif src["type"] == "nb-program":
                    # Upcoming cards on one page. One WordPress request for those slugs.
                    # The past archive (about 1,400 events) is not paged. JSON-LD only for a keyword hit.
                    cards = nb_program_cards(fetch_page(src["url"]).text, src["url"])
                    slugs = [c["slug"] for c in cards if c.get("slug")][:int(src.get("max_cards") or 40)]
                    records = []
                    if slugs:
                        raw = json.loads(fetch_page(nb_query_url(src, slugs)).text)
                        if isinstance(raw, dict) and raw.get("code"):
                            raise RuntimeError(str(raw.get("message") or raw.get("code"))[:180])
                        records = raw if isinstance(raw, list) else []
                    evs = nb_events(src, cards, records, tz, lambda u: fetch_page(u).text)
                    n_found = len(evs)
                    for ev in evs:
                        take(ev, src, src.get("trusted", False))
                elif src["type"] == "squarespace-events":
                    # One public ?format=json request for the programme collection. Event pages are not opened.
                    raw = json.loads(fetch_page(squarespace_query_url(src)).text)
                    evs = squarespace_events(src, raw, tz, matches); n_found = len(evs)
                    for ev in evs:
                        src2 = dict(src, page=ev["url"]); take(ev, src2, src.get("trusted", False))
                elif src["type"] == "manual":
                    n_found = 0
                else:
                    err = f"unknown event source type {src.get('type')}"
            except Exception as ex: err = f"{type(ex).__name__}: {ex}"[:200]
            status["ev-" + src["id"]] = {"checked": now.isoformat(timespec="seconds"), "ok": err is None, "entries": n_found, "new": len(new) - n0, "error": err}
            log(f"event {src['id']:<28} found={n_found} new={len(new) - n0} err={err}")
    # Finished events stay in this file. Predatory rows were removed above and are not restored.
    data["events"] = retain_events(data["events"])
    stored = {e["id"] for e in data["events"]}
    for old in original:
        if old["id"] not in stored and not blocked_event(old): data["events"].append(old)
    data["events"].sort(key=lambda e: dt.datetime.fromisoformat(e["start"])); data["updated"] = now.isoformat(timespec="seconds")
    _save(lp("data", "events.json"), data); _save(lp("state", "source_status.json"), status)
    from tools import event_translate; event_translate.run(lp(), log)
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
    ap.add_argument("--only", help="comma-separated event source ids")
    a, _ = ap.parse_known_args()
    only = {x.strip() for x in a.only.split(",") if x.strip()} if a.only else None
    run(fetch.get, fetch.robots_ok, lambda t: bool(fetch.matches(t)), fetch.log, fetch.CFG, a.add_event, a, only)
