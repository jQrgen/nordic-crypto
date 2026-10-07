#!/usr/bin/env python3
"""Calendar intake: Luma public iCal, Eventbrite v3 or JSON-LD, dedupe, keywords, no discovery crawl.
  python3 tests/test_calendar_intake.py
Uses a temp data directory. Does not fetch the network and does not write data/events.json.
"""
import datetime as dt, json, os, sys, tempfile, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import events
import fetch

NOW = dt.datetime(2026, 10, 6, tzinfo=dt.timezone.utc)
FUTURE = "20261115T180000Z"
PAST = "20260115T180000Z"


class Resp:
    def __init__(self, text, code=200):
        self.text = text
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http %s" % self.status_code)


def ics(events_txt):
    return "BEGIN:VCALENDAR\n" + events_txt + "END:VCALENDAR\n"


def vevent(summary, start, uid_url, place="Sentrum, Oslo", end=None, desc="", cn="K33 Markets"):
    end = end or start
    return (
        "BEGIN:VEVENT\n"
        f"SUMMARY:{summary}\n"
        f"DTSTART:{start}\n"
        f"DTEND:{end}\n"
        f"LOCATION:{place}\n"
        f"DESCRIPTION:{desc}\n"
        f'ORGANIZER;CN="{cn}":mailto:hidden@example.com\n'
        "END:VEVENT\n"
    )


def ld_event(name, start, url, city="Oslo", country="NO", street="Sentrum", online=False):
    loc = {"@type": "VirtualLocation", "url": "https://example.com/room"} if online else {
        "@type": "Place", "name": "Hall",
        "address": {"streetAddress": street, "addressLocality": city, "addressCountry": country},
    }
    body = {
        "@context": "https://schema.org", "@type": "Event", "name": name,
        "startDate": start, "endDate": start, "location": loc,
        "organizer": {"@type": "Organization", "name": "Virtune"},
        "url": url, "description": name,
    }
    return "<html><script type=\"application/ld+json\">" + json.dumps(body) + "</script></html>"


def eb_raw(name, url, city="Stockholm", country="SE", when="2026-11-20T18:00:00Z"):
    return {
        "name": {"text": name}, "url": url,
        "start": {"utc": when, "timezone": "Europe/Stockholm"},
        "end": {"utc": "2026-11-20T20:00:00Z", "timezone": "Europe/Stockholm"},
        "online_event": False, "is_free": True,
        "venue": {"name": "Kungsgatan 26", "address": {"city": city, "country": country, "address_1": "Kungsgatan 26"}},
        "organizer": {"name": "Virtune AB"},
        "description": {"text": name},
    }


class CalendarIntakeTests(unittest.TestCase):
    def test_ics_parse_organiser_url_and_ignore_url_location(self):
        text = ics(vevent(
            "Bitcoin meetup", FUTURE, "https://luma.com/abc",
            place="https://maps.example/pin",
            desc="See https://luma.com/abc123 for details",
        ))
        evs = events.ics_events(text)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["organiser"], "K33 Markets")
        self.assertEqual(evs[0]["url"], "https://luma.com/abc123")
        self.assertIsNone(evs[0]["place"])

    def test_jsonld_itemlist(self):
        item = {
            "@type": "Event", "name": "Bitcoin workshop",
            "startDate": "2026-11-15T18:00:00+01:00",
            "location": {"@type": "Place", "name": "Hall", "address": {"addressLocality": "Oslo", "addressCountry": "NO"}},
            "url": "https://luma.com/one",
        }
        html = "<html><script type=\"application/ld+json\">" + json.dumps({
            "@type": "ItemList", "itemListElement": [{"@type": "ListItem", "item": item}],
        }) + "</script></html>"
        evs = events.jsonld_events(html)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["title"], "Bitcoin workshop")
        self.assertEqual(evs[0]["country_hint"], "NO")

    def test_keywords_dedupe_past_and_non_nordic(self):
        pages = {
            "https://api.lu.ma/ics/a": ics(
                vevent("Bitcoin meetup Oslo", FUTURE, "https://luma.com/a", place="Sentrum, Oslo", desc="https://luma.com/evt-a")
                + vevent("Jazz night", FUTURE, "https://luma.com/jazz", place="Sentrum, Oslo")
                + vevent("Krypto og blokkjede", FUTURE, "https://luma.com/no", place="Sentrum, Oslo", desc="https://luma.com/evt-no")
                + vevent("Blockkedja i Stockholm", FUTURE, "https://luma.com/se", place="Old Town, Stockholm", desc="https://luma.com/evt-se")
                + vevent("Blokkæde Aarhus", FUTURE, "https://luma.com/dk", place="Aarhus", desc="https://luma.com/evt-dk")
                + vevent("Lohkoketju Helsinki", FUTURE, "https://luma.com/fi", place="Helsinki", desc="https://luma.com/evt-fi")
                + vevent("Rafmynt Reykjavik", FUTURE, "https://luma.com/is", place="Reykjavik", desc="https://luma.com/evt-is")
                + vevent("Bitcoin already over", PAST, "https://luma.com/old", place="Sentrum, Oslo")
                + vevent("Bitcoin in Paris", FUTURE, "https://luma.com/paris", place="Paris")
            ),
            "https://api.lu.ma/ics/b": ics(vevent(
                "Bitcoin meetup Oslo", FUTURE, "https://luma.com/other",
                place="Sentrum, Oslo", desc="https://luma.com/evt-dup",
            )),
        }
        got = []

        def get(url):
            got.append(url)
            return Resp(pages[url])

        sources = [
            {"id": "a", "name": "Cal A", "type": "luma-ical", "url": "https://luma.com/a", "ics": "https://api.lu.ma/ics/a",
             "country": "NO", "city": "Oslo", "enabled": True, "trusted": False},
            {"id": "b", "name": "Cal B", "type": "luma-ical", "url": "https://luma.com/b", "ics": "https://api.lu.ma/ics/b",
             "country": "NO", "city": "Oslo", "enabled": True, "trusted": False},
        ]
        with tempfile.TemporaryDirectory() as root:
            new = self._run(root, sources, get)
            titles = sorted(e["title"] for e in new)
        self.assertEqual(titles, [
            "Bitcoin meetup Oslo", "Blockkedja i Stockholm", "Blokkæde Aarhus",
            "Krypto og blokkjede", "Lohkoketju Helsinki", "Rafmynt Reykjavik",
        ])
        self.assertEqual(got, ["https://api.lu.ma/ics/a", "https://api.lu.ma/ics/b"])
        self.assertTrue(all(e["status"] == "pending" and e["sponsored"] is None for e in new))
        countries = {e["title"]: e["country"] for e in new}
        self.assertEqual(countries["Blockkedja i Stockholm"], "SE")
        self.assertEqual(countries["Blokkæde Aarhus"], "DK")
        self.assertEqual(countries["Lohkoketju Helsinki"], "FI")
        self.assertEqual(countries["Rafmynt Reykjavik"], "IS")

    def test_existing_past_event_is_not_deleted(self):
        past = {
            "id": "keptpast0001", "title": "Old bitcoin night", "start": "2026-01-02T18:00:00+01:00",
            "end": "2026-01-02T20:00:00+01:00", "place": "Oslo", "city": "Oslo", "country": "NO",
            "online": False, "organiser": "Someone", "url": "https://example.com/old",
            "source": "manual", "source_url": "https://example.com/old", "paid": None,
            "sponsored": None, "trusted_source": True, "found": "2026-01-01T00:00:00+00:00",
            "status": "approved", "note": None,
        }
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "data"))
            json.dump({"events": [past]}, open(os.path.join(root, "data", "events.json"), "w"))
            self._run(root, [{
                "id": "empty", "name": "Empty", "type": "luma-ical", "url": "https://luma.com/e",
                "ics": "https://api.lu.ma/ics/empty", "country": "NO", "enabled": True,
            }], lambda url: Resp(ics("")))
            saved = json.load(open(os.path.join(root, "data", "events.json")))
        self.assertEqual([e["id"] for e in saved["events"]], ["keptpast0001"])

    def test_dead_feed_does_not_stop_the_next(self):
        def get(url):
            if "dead" in url:
                raise RuntimeError("boom")
            return Resp(ics(vevent("Bitcoin lives", FUTURE, "https://luma.com/ok", desc="https://luma.com/ok1")))

        sources = [
            {"id": "dead", "name": "Dead", "type": "luma-ical", "url": "https://luma.com/dead",
             "ics": "https://api.lu.ma/ics/dead", "country": "NO", "city": "Oslo", "enabled": True},
            {"id": "ok", "name": "Ok", "type": "luma-ical", "url": "https://luma.com/ok",
             "ics": "https://api.lu.ma/ics/ok", "country": "NO", "city": "Oslo", "enabled": True},
        ]
        with tempfile.TemporaryDirectory() as root:
            new = self._run(root, sources, get)
            status = json.load(open(os.path.join(root, "state", "source_status.json")))
        self.assertEqual([e["title"] for e in new], ["Bitcoin lives"])
        self.assertFalse(status["ev-dead"]["ok"])
        self.assertTrue(status["ev-ok"]["ok"])

    def test_robots_disallow_is_recorded(self):
        sources = [{
            "id": "blocked", "name": "Blocked", "type": "luma-ical", "url": "https://luma.com/b",
            "ics": "https://api.lu.ma/ics/blocked", "country": "NO", "city": "Oslo", "enabled": True,
        }]
        with tempfile.TemporaryDirectory() as root:
            new = self._run(root, sources, lambda url: Resp("nope"), robots_ok=lambda url: False)
            status = json.load(open(os.path.join(root, "state", "source_status.json")))
        self.assertEqual(new, [])
        self.assertFalse(status["ev-blocked"]["ok"])
        self.assertIn("robots", status["ev-blocked"]["error"])

    def test_eventbrite_without_token_uses_jsonld(self):
        page = "https://www.eventbrite.com/e/krypto-tickets-1"
        html = ld_event("Krypto i Stockholm", "2026-11-20T18:00:00+01:00", page, city="Stockholm", country="SE", street="Kungsgatan 26")
        seen = []

        def get(url):
            seen.append(url)
            if "/o/" in url:
                return Resp("<html><body>no events</body></html>")
            return Resp(html)

        src = {
            "id": "eb", "name": "Virtune", "type": "eventbrite-organizer", "country": "SE", "city": "Stockholm",
            "url": "https://www.eventbrite.com/o/virtune-1", "organizer_id": "1",
            "event_pages": [page], "enabled": True, "trusted": False,
        }
        with mock.patch.dict(os.environ, {"EVENTBRITE_TOKEN": ""}):
            with tempfile.TemporaryDirectory() as root:
                new = self._run(root, [src], get)
        self.assertEqual([e["title"] for e in new], ["Krypto i Stockholm"])
        self.assertEqual(new[0]["country"], "SE")
        self.assertTrue(any(page in u for u in seen))

    def test_eventbrite_token_uses_api_and_skips_pages(self):
        seen_pages = []
        api_urls = []

        def get(url):
            seen_pages.append(url)
            return Resp("<html></html>")

        def fake_eb(url, token, robots_ok, pause, ua):
            api_urls.append(url)
            self.assertEqual(token, "secret-token")
            self.assertNotIn("secret-token", url)
            if "/venues/" in url:
                raw = eb_raw("Bitcoin venue night", "https://www.eventbrite.com/e/venue-1")
            elif "continuation" in url:
                raw = eb_raw("Blockchain page two", "https://www.eventbrite.com/e/page-2")
                return {"events": [raw], "pagination": {"has_more_items": False}}
            else:
                raw = eb_raw("Blockchain page one", "https://www.eventbrite.com/e/page-1")
                return {"events": [raw], "pagination": {"has_more_items": True, "continuation": "next"}}
            return {"events": [raw], "pagination": {"has_more_items": False}}

        org = {
            "id": "org", "name": "Org", "type": "eventbrite-organizer", "country": "SE", "city": "Stockholm",
            "url": "https://www.eventbrite.com/o/org", "organizer_id": "99",
            "event_pages": ["https://www.eventbrite.com/e/should-not-fetch"], "enabled": True,
        }
        venue = {
            "id": "ven", "name": "Venue", "type": "eventbrite-venue", "country": "SE", "city": "Stockholm",
            "url": "https://www.eventbrite.com/v/1", "venue_id": "55", "enabled": True,
        }
        with mock.patch.dict(os.environ, {"EVENTBRITE_TOKEN": "secret-token"}):
            with mock.patch.object(events, "eb_get", fake_eb):
                with tempfile.TemporaryDirectory() as root:
                    new = self._run(root, [org, venue], get)
        titles = sorted(e["title"] for e in new)
        self.assertEqual(titles, ["Bitcoin venue night", "Blockchain page one", "Blockchain page two"])
        self.assertEqual(seen_pages, [])
        self.assertTrue(any("/organizers/99/events/" in u for u in api_urls))
        self.assertTrue(any("/venues/55/events/" in u for u in api_urls))
        self.assertTrue(any("continuation=" in u for u in api_urls))

    def test_eventbrite_api_error_falls_back_to_jsonld(self):
        page = "https://www.eventbrite.com/e/fallback-tickets-1"
        html = ld_event("Bitcoin fallback", "2026-12-01T18:00:00+01:00", page, city="Helsinki", country="FI")

        def get(url):
            return Resp(html if page in url else "<html></html>")

        def fake_eb(url, token, robots_ok, pause, ua):
            raise RuntimeError("api down")

        src = {
            "id": "fb", "name": "Fallback", "type": "eventbrite-organizer", "country": "FI", "city": "Helsinki",
            "url": "https://www.eventbrite.com/o/fb", "organizer_id": "7",
            "event_pages": [page], "enabled": True,
        }
        with mock.patch.dict(os.environ, {"EVENTBRITE_TOKEN": "secret-token"}):
            with mock.patch.object(events, "eb_get", fake_eb):
                with tempfile.TemporaryDirectory() as root:
                    new = self._run(root, [src], get)
                    status = json.load(open(os.path.join(root, "state", "source_status.json")))
        self.assertEqual([e["title"] for e in new], ["Bitcoin fallback"])
        self.assertTrue(status["ev-fb"]["ok"])

    def test_empty_api_does_not_scrape_pages(self):
        def get(url):
            raise AssertionError("event page fetched: " + url)

        def fake_eb(url, token, robots_ok, pause, ua):
            return {"events": [], "pagination": {"has_more_items": False}}

        src = {
            "id": "emptyapi", "name": "Empty API", "type": "eventbrite-organizer", "country": "SE",
            "url": "https://www.eventbrite.com/o/x", "organizer_id": "1",
            "event_pages": ["https://www.eventbrite.com/e/old"], "enabled": True,
        }
        with mock.patch.dict(os.environ, {"EVENTBRITE_TOKEN": "secret-token"}):
            with mock.patch.object(events, "eb_get", fake_eb):
                with tempfile.TemporaryDirectory() as root:
                    new = self._run(root, [src], get)
        self.assertEqual(new, [])

    def test_clear_kaupr_sponsor(self):
        self.assertIsNone(events.clear_kaupr_sponsor("Kaupr"))
        self.assertIsNone(events.clear_kaupr_sponsor("sponsored by KAUPR AS"))
        self.assertEqual(events.clear_kaupr_sponsor("Firi"), "Firi")
        self.assertIsNone(events.clear_kaupr_sponsor(None))

    def test_sources_are_ical_not_discovery(self):
        cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
        ev = cfg["event_sources"]
        ids = {s["id"] for s in ev}
        for required in ("luma-k33", "luma-nordic-blockchain", "luma-kth-assert", "luma-btchel",
                         "eb-blockchain-smart-solutions", "eb-virtune", "eb-web3-community"):
            self.assertIn(required, ids)
        for s in ev:
            if s["id"].startswith("luma-") or s["id"].startswith("eb-"):
                self.assertTrue(str(s.get("status", "")).lower().startswith("used"))
                self.assertTrue(s.get("method"))
                self.assertFalse(s.get("trusted"))
            url = (s.get("url") or "") + " " + (s.get("ics") or "")
            self.assertNotIn("luma.com/oslo", url)
            self.assertNotIn("luma.com/crypto", url)
            self.assertNotIn("luma.com/web3", url)
            self.assertNotIn("luma.com/ai", url)
            self.assertNotRegex(s.get("url") or "", r"eventbrite\.com/d/")
            self.assertNotIn(s.get("type"), ("luma-discover", "eventbrite-search"))
        luma = [s for s in ev if s.get("type") == "luma-ical"]
        self.assertTrue(all("api.lu.ma/ics/get" in s["ics"] for s in luma))
        self.assertFalse(any(s.get("type") == "eventbrite-venue" for s in ev))

    def test_sources_page_is_left_aligned(self):
        text = open(os.path.join(ROOT, "build.py"), encoding="utf-8").read()
        self.assertIn("table.list th,table.list td{border-bottom:1px solid var(--line);padding:6px 6px;text-align:left", text)
        self.assertIn('t("st_used")', text)
        self.assertIn('style="text-align:left"', text)
        en = open(os.path.join(ROOT, "i18n", "en.py"), encoding="utf-8").read()
        self.assertIn('"st_used"', en)
        self.assertIn("publicly supported interfaces", en)

    def _run(self, root, sources, get, robots_ok=lambda url: True):
        return events.run(
            get, robots_ok, lambda t: bool(fetch.matches(t)), lambda *a: None,
            {"event_sources": sources, "min_delay_seconds": 0, "user_agent": "test"},
            root=root, now=NOW,
        )


if __name__ == "__main__":
    unittest.main()
