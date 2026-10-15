#!/usr/bin/env python3
"""Bitcoinpolitisk institutt homepage Kalender. No network. Does not write data/events.json."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import events
import event_description as ed
import i18n

NOW = dt.datetime(2026, 10, 14, 12, tzinfo=dt.timezone.utc)
OSLO = "Europe/Oslo"
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "bpi_homepage.html")
HOME = "https://bpinorge.no/"


def fixture_html():
    return open(FIXTURE, encoding="utf-8").read()


def src():
    return {
        "id": "bpi-arrangementer",
        "name": "Bitcoinpolitisk institutt – events",
        "type": "bpi_kalender",
        "url": HOME,
        "country": "NO",
        "organiser": "Bitcoinpolitisk institutt Norge",
        "trusted": True,
        "enabled": True,
        "status": "ok",
    }


class Resp:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        return None


class BpiKalenderTests(unittest.TestCase):
    def test_fixture_is_the_homepage_kalender(self):
        html = fixture_html()
        self.assertIn(">Kalender<", html)
        self.assertIn("https://www.polyteknisk.no/program/crypto-killer-apps", html)
        self.assertIn("https://www.litteraturhuset.no/nb/arrangement/cantillon-effekten-and-pengar", html)
        self.assertIn("Satoshi Nakamoto-årstalen", html)
        cards = events.bpi_kalender_cards(html, HOME)
        self.assertEqual([c["title"] for c in cards], [
            "Crypto killer apps", "Cantillon-effekten & pengar", "Satoshi Nakamoto-årstalen"])
        self.assertEqual([(c["day"], c["month"], c["year"], c["city"], c["kind"]) for c in cards], [
            (14, 10, 2026, "Oslo", "Foredrag med PF"),
            (29, 10, 2026, "Oslo", "Satoshi-samtale"),
            (10, 2, 2027, "Oslo", "Årstale"),
        ])
        self.assertEqual(cards[0]["url"], "https://www.polyteknisk.no/program/crypto-killer-apps")
        self.assertEqual(cards[1]["url"], "https://www.litteraturhuset.no/nb/arrangement/cantillon-effekten-and-pengar")
        self.assertEqual(cards[2]["url"], HOME)

    def test_no_clock_is_the_civil_day(self):
        evs = events.bpi_events(src(), events.bpi_kalender_cards(fixture_html(), HOME), OSLO)
        by = {e["title"]: e for e in evs}
        self.assertEqual(by["Crypto killer apps"]["start"].isoformat(), "2026-10-14T00:00:00+02:00")
        self.assertEqual(by["Crypto killer apps"]["end"].isoformat(), "2026-10-14T23:59:00+02:00")
        self.assertEqual(by["Cantillon-effekten & pengar"]["start"].isoformat(), "2026-10-29T00:00:00+01:00")
        self.assertEqual(by["Satoshi Nakamoto-årstalen"]["start"].isoformat(), "2027-02-10T00:00:00+01:00")
        self.assertEqual(by["Satoshi Nakamoto-årstalen"]["end"].isoformat(), "2027-02-10T23:59:00+01:00")

    def test_normalised_title_and_date_match_a_venue_calendar(self):
        bpi = src()
        short = {
            "title": "Crypto killer apps", "start": "2026-10-14T00:00:00+02:00",
            "url": HOME, "city": "Bergen", "place": None,
        }
        poly = {
            "title": "Crypto killer apps: bitcoin-appene som endrer økonomien",
            "start": "2026-10-14T17:30:00+02:00",
            "url": "https://www.polyteknisk.no/program/crypto-killer-apps",
            "source": "Polyteknisk Forening (program)",
            "place": "Rosenkrantz' gate 7", "city": "Trondheim",
        }
        self.assertFalse(events.same_event(short, poly))
        self.assertTrue(events.bpi_venue_duplicate(short, poly, bpi))
        nb = {
            "title": "Satoshi Nakamoto-årstalen", "start": "2027-02-10T18:00:00+01:00",
            "url": "https://www.nb.no/hva-skjer/satoshi-nakamoto-arstalen-2027/",
            "source": "Nasjonalbiblioteket", "source_url": "https://www.nb.no/hva-skjer/",
            "place": "Målstova", "city": None,
        }
        talk = {
            "title": "Satoshi Nakamoto-årstalen",
            "start": dt.datetime(2027, 2, 10, tzinfo=ZoneInfo(OSLO)),
            "url": HOME, "city": "Oslo", "place": None,
        }
        self.assertFalse(events.same_event(talk, nb))
        self.assertTrue(events.bpi_venue_duplicate(talk, nb, bpi))
        self.assertTrue(events.bpi_venue_duplicate(nb, dict(talk, source="Bitcoinpolitisk institutt – events", source_url=HOME)))
        other_day = dict(nb, start="2026-02-11T18:00:00+01:00")
        self.assertFalse(events.bpi_venue_duplicate(talk, other_day, bpi))
        meetup = dict(poly, source="Swedish Bitcoin Meetups (Meetup.com)", url="https://www.meetup.com/events/1/", source_url="https://www.meetup.com/swedish-bitcoin-meetups/")
        self.assertFalse(events.bpi_venue_duplicate(short, meetup, bpi))

    def test_run_keeps_venue_rows_and_adds_the_bpi_only_talk(self):
        stored = json.load(open(os.path.join(ROOT, "data", "events.json"), encoding="utf-8"))["events"]
        seed = [e for e in stored if e["id"] in ("019f42a4506c", "bddf7842a80a")]
        self.assertEqual(len(seed), 2)
        opened = []

        def get(url):
            opened.append(url)
            self.assertEqual(url, HOME)
            return Resp(fixture_html())

        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "data"))
            json.dump({"events": seed}, open(os.path.join(root, "data", "events.json"), "w", encoding="utf-8"))
            new = events.run(get, lambda url: True, lambda t: False, lambda *a: None,
                             {"event_sources": [src()], "min_delay_seconds": 0, "user_agent": "test"},
                             root=root, now=NOW)
            saved = json.load(open(os.path.join(root, "data", "events.json"), encoding="utf-8"))["events"]
        self.assertEqual(opened, [HOME])
        self.assertEqual([e["title"] for e in new], ["Satoshi Nakamoto-årstalen"])
        row = new[0]
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["start"], "2027-02-10T00:00:00+01:00")
        self.assertEqual(row["end"], "2027-02-10T23:59:00+01:00")
        self.assertEqual(row["city"], "Oslo")
        self.assertEqual(row["country"], "NO")
        self.assertEqual(row["url"], HOME)
        self.assertEqual(row["source_url"], HOME)
        self.assertEqual(row["organiser"], "Bitcoinpolitisk institutt Norge")
        by_id = {e["id"]: e for e in saved}
        for old in seed:
            kept = by_id[old["id"]]
            self.assertEqual(kept["title"], old["title"])
            self.assertEqual(kept["start"], old["start"])
            self.assertEqual(kept["place"], old["place"])
            self.assertEqual(kept["organiser"], old["organiser"])
            self.assertEqual(kept["description"]["text"], old["description"]["text"])

    def test_archive_venue_row_is_not_added_again(self):
        opened = []

        def get(url):
            opened.append(url)
            return Resp(fixture_html())

        archive_row = {
            "id": "nb-2027",
            "title": "Satoshi Nakamoto-årstalen",
            "start": "2027-02-10T18:00:00+01:00",
            "url": "https://www.nb.no/hva-skjer/satoshi-nakamoto-arstalen-2027/",
            "source": "Nasjonalbiblioteket",
            "source_url": "https://www.nb.no/hva-skjer/",
            "place": "Målstova",
            "city": None,
            "country": "NO",
        }
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "data"))
            os.makedirs(os.path.join(root, "archive"))
            json.dump({"events": []}, open(os.path.join(root, "data", "events.json"), "w", encoding="utf-8"))
            json.dump({"events": [archive_row]}, open(os.path.join(root, "archive", "events.json"), "w", encoding="utf-8"))
            new = events.run(get, lambda url: True, lambda t: False, lambda *a: None,
                             {"event_sources": [src()], "min_delay_seconds": 0, "user_agent": "test"},
                             root=root, now=NOW)
            saved = json.load(open(os.path.join(root, "data", "events.json"), encoding="utf-8"))["events"]
        titles = [e["title"] for e in new]
        self.assertNotIn("Satoshi Nakamoto-årstalen", titles)
        self.assertTrue(all("Satoshi" not in e["title"] for e in saved))
        self.assertEqual(opened, [HOME])

    def test_source_is_registered(self):
        cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
        row = next(s for s in cfg["event_sources"] if s["id"] == "bpi-arrangementer")
        self.assertEqual(row["type"], "bpi_kalender")
        self.assertEqual(row["url"], HOME)
        self.assertEqual(row["status"], "ok")
        self.assertNotIn("arrangementer", row["url"])
        self.assertIn("Kalender", row["method"])

    def test_satoshi_2027_is_stored_with_every_site_language(self):
        rows = json.load(open(os.path.join(ROOT, "data", "events.json"), encoding="utf-8"))["events"]
        ev = next(e for e in rows if e["title"] == "Satoshi Nakamoto-årstalen 2027")
        self.assertEqual(ev["start"], "2027-02-10T00:00:00+01:00")
        self.assertEqual(ev["end"], "2027-02-10T23:59:00+01:00")
        self.assertEqual(ev["city"], "Oslo")
        self.assertEqual(ev["country"], "NO")
        self.assertEqual(ev["place"], "Nasjonalbiblioteket")
        self.assertEqual(ev["organiser"], "Bitcoinpolitisk institutt Noreg")
        self.assertEqual(ev["url"], HOME)
        self.assertEqual(ev["source_url"], HOME)
        self.assertEqual(ev["status"], "pending")
        text = ev["description"]["text"]
        self.assertEqual(ev["description"]["lang"], "nb")
        self.assertEqual(ev["description"]["source_url"], HOME)
        self.assertIn("Nasjonalbiblioteket", text)
        self.assertIn("10. februar 2027", text)
        catalogue = json.load(open(os.path.join(ROOT, "data", "event_description_i18n.json"), encoding="utf-8"))["items"]
        item = catalogue[ev["id"]]
        self.assertEqual(item["source"], text)
        missing = [lang for lang in i18n.ALL_LANGS if lang != "nb" and not (item.get(lang) or "").strip()]
        self.assertEqual(missing, [])
        self.assertNotIn("nb", item)
        shown, lang, orig = ed.show(ev, "de")
        self.assertEqual(lang, "de")
        self.assertEqual(orig, text)
        self.assertIn("Oslo", shown)
        shown, lang, orig = ed.show(ev, "nb")
        self.assertEqual(shown, text)
        self.assertEqual(orig, "")
        archive = json.load(open(os.path.join(ROOT, "archive", "events.json"), encoding="utf-8"))["events"]
        self.assertNotIn(ev["id"], {e["id"] for e in archive})


if __name__ == "__main__":
    unittest.main()
