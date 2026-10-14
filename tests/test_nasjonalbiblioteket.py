#!/usr/bin/env python3
"""Nasjonalbiblioteket Hva skjer intake. No network. Does not write data/events.json."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import events

NOW = dt.datetime(2026, 10, 14, 12, tzinfo=dt.timezone.utc)
OSLO = "Europe/Oslo"
LISTING = """
<div class="is-post-type-exhibit"><a href="https://www.nb.no/utstilling/med-pennen/"><h2 class="t2-post-title">Med pennen på strupen</h2></a></div>
<div class="is-post-type-event">
  <a class="nb-post-link" href="https://www.nb.no/hva-skjer/satoshi-nakamoto-arstalen/">
    <div class="nb-post-label">Ekstern arrangør</div>
    <h2 class="t2-post-title">Satoshi Nakamoto-årstalen</h2>
    <div class="nb-post-subtitle">Ons. 11. november kl. 18:00–20:00</div>
  </a>
</div>
<div class="is-post-type-event">
  <a class="nb-post-link" href="https://www.nb.no/hva-skjer/en-roman/">
    <div class="nb-post-label">Arrangement</div>
    <h2 class="t2-post-title">En roman om hverdagen</h2>
    <div class="nb-post-subtitle">Ons. 14. oktober kl. 18:00–19:00</div>
  </a>
</div>
<div class="is-post-type-event">
  <a class="nb-post-link" href="https://www.nb.no/hva-skjer/fortellerstund-om-penger/">
    <div class="nb-post-label">Arrangement</div>
    <h2 class="t2-post-title">Fortellerstund om penger</h2>
    <div class="nb-post-subtitle">Man. 2. november kl. 11:00–11:30</div>
  </a>
</div>
<div class="is-post-type-event">
  <a class="nb-post-link" href="https://www.nb.no/hva-skjer/kryptisk-dikt/">
    <div class="nb-post-label">Arrangement</div>
    <h2 class="t2-post-title">Kryptisk dikt</h2>
    <div class="nb-post-subtitle">Tir. 3. november kl. 18:00–19:00</div>
  </a>
</div>
"""
PAGE = """
<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"Event","name":"Satoshi Nakamoto-årstalen","startDate":"2026-11-11T18:00:00+01:00","endDate":"2026-11-11T20:00:00+01:00","location":{"@type":"Place","name":"Nasjonalbiblioteket - Målstova","address":{"@type":"PostalAddress","addressCountry":"NO","addressLocality":"Oslo","streetAddress":"Henrik Ibsens gate 110"}}}</script></head>
<body><main><div class="wp-block-post-content"><p>ignored by the json-ld path</p></div></main></body></html>
"""
SATOSHI_HTML = """
<h2>En alternativ forelesning om penger, teknologi og samfunn.</h2>
<p class="t2-ingress">Dagen før sentralbanksjefen holder årstalen, arrangerer Bitcoinpolitisk institutt Norge (BPI) tidenes første Satoshi Nakamoto-årstale. Velkommen til en tale om bitcoin og penger.</p>
<p>Praktisk informasjon: <a href="https://example.invalid/?q=person%40nb.no">Påmelding</a></p>
"""


def records():
    return [
        {
            "slug": "satoshi-nakamoto-arstalen",
            "link": "https://www.nb.no/hva-skjer/satoshi-nakamoto-arstalen/",
            "title": {"rendered": "Satoshi Nakamoto-årstalen"},
            "content": {"rendered": SATOSHI_HTML},
            "meta": {
                "event_start_datetime": "2026-11-11T18:00:00",
                "event_end_datetime": "2026-11-11T20:00:00",
                "event_ticket_price_text": "Gratis",
                "event_tba_datetime": False,
            },
        },
        {
            "slug": "en-roman",
            "title": {"rendered": "En roman om hverdagen"},
            "content": {"rendered": "<h2>En roman om hverdagen</h2><p>En samtale om en roman.</p><p>Langt nede i teksten nevnes penger en gang, uten at det er tema.</p>"},
            "meta": {"event_start_datetime": "2026-10-14T18:00:00", "event_end_datetime": "2026-10-14T19:00:00"},
        },
        {
            "slug": "fortellerstund-om-penger",
            "title": {"rendered": "Fortellerstund om penger"},
            "content": {"rendered": "<p>Vi leser om penger.</p>"},
            "meta": {"event_start_datetime": "2026-11-02T11:00:00", "event_end_datetime": "2026-11-02T11:30:00"},
        },
        {
            "slug": "kryptisk-dikt",
            "title": {"rendered": "Kryptisk dikt"},
            "content": {"rendered": "<p>Et dikt om kryptografi og premiepenger.</p>"},
            "meta": {"event_start_datetime": "2026-11-03T18:00:00", "event_end_datetime": "2026-11-03T19:00:00"},
        },
    ]


class NbTests(unittest.TestCase):
    def test_cards_are_events_only(self):
        cards = events.nb_program_cards(LISTING, "https://www.nb.no/hva-skjer/")
        self.assertEqual([c["slug"] for c in cards], [
            "satoshi-nakamoto-arstalen", "en-roman", "fortellerstund-om-penger", "kryptisk-dikt"])

    def test_only_the_keyword_hit_is_opened(self):
        cards = events.nb_program_cards(LISTING, "https://www.nb.no/hva-skjer/")
        opened = []

        def page(url):
            opened.append(url)
            return PAGE

        src = {
            "venue": "Nasjonalbiblioteket", "address": "Henrik Ibsens gate 110",
            "city": "Oslo", "country": "NO", "max_links": 8,
            "api": "https://www.nb.no/wp-json/wp/v2/event",
        }
        evs = events.nb_events(src, cards, records(), OSLO, page)
        self.assertEqual(opened, ["https://www.nb.no/hva-skjer/satoshi-nakamoto-arstalen/"])
        self.assertEqual(len(evs), 1)
        ev = evs[0]
        self.assertEqual(ev["title"], "Satoshi Nakamoto-årstalen")
        self.assertEqual(ev["start"].isoformat(), "2026-11-11T18:00:00+01:00")
        self.assertEqual(ev["end"].isoformat(), "2026-11-11T20:00:00+01:00")
        self.assertEqual(ev["place"], "Målstova, Nasjonalbiblioteket, Henrik Ibsens gate 110")
        self.assertEqual(ev["city"], "Oslo")
        self.assertEqual(ev["organiser"], "Bitcoinpolitisk institutt Norge")
        self.assertIs(ev["paid"], False)
        self.assertIn("bitcoin", ev["description"])
        self.assertNotIn("person@nb.no", ev["description"])
        self.assertNotIn("Praktisk informasjon", ev["description"])
        url = events.nb_query_url(src, [c["slug"] for c in cards])
        self.assertIn("wp-json/wp/v2/event", url)
        self.assertIn("satoshi-nakamoto-arstalen", url)
        self.assertNotIn("orderby=meta", url)

    def test_tba_time_is_not_invented(self):
        cards = events.nb_program_cards(LISTING, "https://www.nb.no/hva-skjer/")
        rows = records()
        rows[0]["meta"]["event_tba_datetime"] = True
        evs = events.nb_events(
            {"venue": "Nasjonalbiblioteket", "address": "Henrik Ibsens gate 110", "city": "Oslo", "country": "NO"},
            cards, rows, OSLO, lambda url: PAGE)
        self.assertEqual(evs, [])

    def test_run_writes_a_future_hit_as_pending(self):
        src = {
            "id": "nasjonalbiblioteket", "name": "Nasjonalbiblioteket", "type": "nb-program",
            "country": "NO", "city": "Oslo", "venue": "Nasjonalbiblioteket",
            "address": "Henrik Ibsens gate 110",
            "url": "https://www.nb.no/hva-skjer/",
            "api": "https://www.nb.no/wp-json/wp/v2/event",
            "keyword_profile": "crypto-money", "trusted": False, "enabled": True, "max_cards": 40,
        }

        class Resp:
            def __init__(self, text):
                self.text = text
                self.status_code = 200

            def raise_for_status(self):
                return None

        def get(url):
            if "wp-json" in url:
                return Resp(json.dumps(records()))
            if url.rstrip("/").endswith("satoshi-nakamoto-arstalen"):
                return Resp(PAGE)
            return Resp(LISTING)

        with tempfile.TemporaryDirectory() as root:
            new = events.run(get, lambda url: True, lambda t: False, lambda *a: None,
                             {"event_sources": [src], "min_delay_seconds": 0, "user_agent": "test"},
                             root=root, now=NOW)
            saved = json.load(open(os.path.join(root, "data", "events.json"), encoding="utf-8"))
        self.assertEqual([e["title"] for e in new], ["Satoshi Nakamoto-årstalen"])
        row = saved["events"][0]
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["start"], "2026-11-11T18:00:00+01:00")
        self.assertEqual(row["end"], "2026-11-11T20:00:00+01:00")
        self.assertEqual(row["place"], "Målstova, Nasjonalbiblioteket, Henrik Ibsens gate 110")
        self.assertEqual(row["organiser"], "Bitcoinpolitisk institutt Norge")
        self.assertIs(row["paid"], False)
        self.assertEqual(row["url"], "https://www.nb.no/hva-skjer/satoshi-nakamoto-arstalen/")
        self.assertEqual(row["source_url"], "https://www.nb.no/hva-skjer/")

    def test_satoshi_is_on_the_public_archive(self):
        rows = json.load(open(os.path.join(ROOT, "archive", "events.json"), encoding="utf-8"))["events"]
        ev = next(e for e in rows if e["id"] == "4a60aa9b39c4")
        self.assertEqual(ev["title"], "Satoshi Nakamoto-årstalen")
        self.assertEqual(ev["status"], "published")
        self.assertEqual(ev["start"], "2026-02-11T18:00:00+01:00")
        self.assertEqual(ev["end"], "2026-02-11T20:00:00+01:00")
        self.assertEqual(ev["place"], "Målstova, Nasjonalbiblioteket, Henrik Ibsens gate 110")
        self.assertEqual(ev["city"], "Oslo")
        self.assertEqual(ev["organiser"], "Bitcoinpolitisk institutt Norge")
        self.assertEqual(ev["url"], "https://www.nb.no/hva-skjer/satoshi-nakamoto-arstalen/")
        self.assertEqual(ev["source_url"], "https://www.nb.no/hva-skjer/")
        self.assertIs(ev["paid"], False)
        self.assertEqual(ev["description"]["lang"], "nb")
        self.assertIn("bitcoin", ev["description"]["text"])

    def test_source_is_registered(self):
        cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
        src = next(s for s in cfg["event_sources"] if s["id"] == "nasjonalbiblioteket")
        self.assertEqual(src["type"], "nb-program")
        self.assertEqual(src["keyword_profile"], "crypto-money")
        self.assertFalse(src["trusted"])
        self.assertEqual(src["url"], "https://www.nb.no/hva-skjer/")
        self.assertIn("/wp-json/wp/v2/event", src["api"])


if __name__ == "__main__":
    unittest.main()
