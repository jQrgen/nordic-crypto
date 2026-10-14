#!/usr/bin/env python3
"""Litteraturhuset intake: Sanity query, Webflow programme, WordPress programme.

No network. Does not write data/events.json.
"""
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


def sanity_payload():
    return {"result": {
        "address": ["Stiftelsen Litteraturhuset\nWergelandsveien 29\n0167 Oslo"],
        "events": [
            {
                "title_nb": "Cantillon-effekten & pengar",
                "desc_nb": "Kven var Richard Cantillon? Er pengeteorien hans enno relevant?",
                "slug": "cantillon-effekten-and-pengar",
                "english": False,
                "dates": [{"eventStart": "2026-10-29T18:00:00.000Z", "eventDuration": 60}],
                "organizers": ["Bitcoinpolitisk institutt Noreg"],
                "room": "Kverneland",
                "blocks_nb": [{"spans": ["Cantillon meinte at berre myntar var pengar. ", "Bitcoin illustrerer teorien."]}],
            },
            {
                "title_nb": "Bitcoin er tid",
                "desc_nb": "Kva har pengar med tid å gjera?",
                "slug": "bitcoin-er-tid",
                "english": False,
                "dates": [{"eventStart": "2026-11-11T18:00:00.000Z", "eventDuration": 60}],
                "organizers": ["Bitcoinpolitisk institutt Noreg"],
                "room": "Kverneland",
                "blocks_nb": [{"spans": ["Ein føredrag om bitcoin."]}],
            },
            {
                "title_nb": "Skattekommisjonen",
                "desc_nb": "Skatt og erfaringer med Skattekommisjonens arbeid.",
                "slug": "skattekommisjonen",
                "dates": [{"eventStart": "2026-10-21T12:00:00.000Z", "eventDuration": 60}],
                "organizers": ["NOU"],
                "room": "Amalie Skram",
                "blocks_nb": [{"spans": ["Økonomi i en roman er ikke tema her, bare skatt."]}],
            },
            {
                "title_nb": "Fortellerstund om penger",
                "desc_nb": "En eventyrstund for de minste.",
                "slug": "fortellerstund-penger",
                "dates": [{"eventStart": "2026-11-01T10:00:00.000Z", "eventDuration": 45}],
                "organizers": ["Litteraturhuset"],
                "room": "Nedjma",
                "blocks_nb": [{"spans": ["Vi leser om penger."]}],
            },
            {
                "title_nb": "Kryptisk roman",
                "desc_nb": "Om kryptografi i en spenningsbok.",
                "slug": "kryptisk-roman",
                "dates": [{"eventStart": "2026-11-02T18:00:00.000Z", "eventDuration": 60}],
                "organizers": ["Forlaget"],
                "room": "Amalie Skram",
                "blocks_nb": [{"spans": ["Premiepenger til vinneren av quizzen."]}],
            },
            {
                "title_nb": "Inflasjon og sentralbanken",
                "desc_nb": "Et foredrag om pengepolitikk.",
                "slug": "inflasjon",
                "dates": [{"eventStart": "2026-12-01T17:00:00.000Z", "eventDuration": 90}],
                "organizers": ["Universitetet"],
                "room": "Skram",
                "blocks_nb": [],
            },
        ],
    }}


WEBFLOW = """
<html><body>
<div class="program-item w-dyn-item">
  <div class="date-event"><h3>Ons.</h3><h3>14</h3><h3>.</h3><h3>10</h3></div>
  <div class="time-event"><h3>19:00</h3><h3>–</h3><h3>20:00</h3></div>
  <a href="/arrangement/klassikaren-odysseen" class="event-name-in-grid"><h3>Klassikaren: Odysseen</h3></a>
  <div class="heading-3">Auditoriet Trond Mohn</div>
  <div class="text-block">Panelsamtale om eposet.</div>
</div>
<div class="program-item w-dyn-item">
  <div class="date-event"><h3>Tor.</h3><h3>29</h3><h3>.</h3><h3>10</h3></div>
  <div class="time-event"><h3>19:00</h3><h3>–</h3><h3>20:30</h3></div>
  <a href="/arrangement/pengar-og-bitcoin" class="event-name-in-grid"><h3>Pengar og bitcoin</h3></a>
  <div class="heading-3">Fosse-stova</div>
  <div class="text-block">En kveld om blokkjede.</div>
  <div class="event-gratis program">Gratis</div>
</div>
<a class="w-pagination-next" href="?page=2">Neste</a>
</body></html>
"""

WEBFLOW_PAGE = """
<html><body>
<div class="event-page-arrangor"><h5>Arrangør:</h5><div>Bitcoin Bergen</div></div>
</body></html>
"""

WP = """
<html><body><div class="ss-list-events"></div><div class="ss-list-events"><div class="item"><div class="content">
<h3>Bokstart Fredrikstad: Fortellerstund på Litteraturhuset Fredrikstad</h3>
<p>man 19. oktober 2026 | kl 11.00</p>
<p>Arr. Litteraturhuset Fredrikstad</p>
<a href="https://litthusfred.no/event/bokstart-fredrikstad/">Les mer</a>
</div></div>
<div class="item"><div class="content">
<div class="ss-height-match">Cantillon-effekten på Litteraturhuset Fredrikstad</div>
<p>tor 29. oktober 2026 | kl 19:00</p>
<p>Arr. Bitcoinpolitisk institutt</p>
<a href="/event/cantillon-fredrikstad/">Les mer</a>
</div></div>
<div class="item"><div class="content">
<h3>Fortellerstund på Lisleby samfunnshus om penger</h3>
<p>man 2. november 2026 | kl 11.00</p>
<p>Arr. Litteraturhuset Fredrikstad</p>
<a href="/event/penger-barn/">Les mer</a>
</div></div>
</div></body></html>
"""


class LitteraturhusetTests(unittest.TestCase):
    def test_keywords_keep_money_talks_and_drop_false_positives(self):
        self.assertTrue(events.crypto_money_hit("Cantillon-effekten & pengar", "pengeteori"))
        self.assertTrue(events.crypto_money_hit("En roman", "Ingenting", "bitcoin i brødteksten"))
        self.assertTrue(events.crypto_money_hit("Inflasjon", "Et foredrag"))
        self.assertTrue(events.crypto_money_hit("Sentralbanken", ""))
        self.assertFalse(events.crypto_money_hit("Skattekommisjonen", "Skatt og erfaringer"))
        self.assertFalse(events.crypto_money_hit("Kryptisk roman", "Om kryptografi"))
        self.assertFalse(events.crypto_money_hit("Premiepenger", "Quiz"))
        self.assertFalse(events.crypto_money_hit("Fortellerstund om penger", "For barn"))
        self.assertFalse(events.crypto_money_hit("En roman", "Kort", "senere nevnes penger i et avsnitt"))

    def test_sanity_keeps_two_talks_with_oslo_time_and_street(self):
        src = {
            "name": "Litteraturhuset Oslo", "venue": "Litteraturhuset", "address": "fallback 1",
            "city": "Oslo", "country": "NO", "site": "https://www.litteraturhuset.no", "lang_path": "nb",
        }
        evs = events.sanity_events(src, sanity_payload(), OSLO)
        titles = sorted(e["title"] for e in evs)
        self.assertEqual(titles, ["Bitcoin er tid", "Cantillon-effekten & pengar", "Inflasjon og sentralbanken"])
        cant = next(e for e in evs if e["title"].startswith("Cantillon"))
        self.assertEqual(cant["start"].isoformat(), "2026-10-29T18:00:00+00:00")
        self.assertEqual(cant["end"].isoformat(), "2026-10-29T19:00:00+00:00")
        self.assertEqual(cant["place"], "Kverneland, Litteraturhuset, Wergelandsveien 29")
        self.assertEqual(cant["organiser"], "Bitcoinpolitisk institutt Noreg")
        self.assertEqual(cant["url"], "https://www.litteraturhuset.no/nb/arrangement/cantillon-effekten-and-pengar")
        self.assertEqual(cant["description_lang"], "nn")
        self.assertIn("Bitcoin illustrerer", cant["description"])
        self.assertTrue(events.source_keeps(cant, {"keyword_profile": "crypto-money"}, False, lambda t: False))

    def test_webflow_follows_only_the_keyword_hit(self):
        cards, nxt = events.webflow_program_cards(WEBFLOW, "https://www.litthusbergen.no/program")
        self.assertEqual(len(cards), 2)
        self.assertEqual(nxt, "https://www.litthusbergen.no/program?page=2")
        opened = []

        def page(url):
            opened.append(url)
            return WEBFLOW_PAGE

        src = {
            "venue": "Litteraturhuset", "address": "Østre Skostredet 5-7",
            "city": "Bergen", "country": "NO", "max_links": 8,
        }
        evs = events.webflow_events(src, cards, NOW.date(), OSLO, page)
        self.assertEqual(opened, ["https://www.litthusbergen.no/arrangement/pengar-og-bitcoin"])
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["organiser"], "Bitcoin Bergen")
        self.assertEqual(evs[0]["start"].isoformat(), "2026-10-29T19:00:00+01:00")
        self.assertEqual(evs[0]["end"].isoformat(), "2026-10-29T20:30:00+01:00")
        self.assertEqual(evs[0]["place"], "Fosse-stova, Litteraturhuset, Østre Skostredet 5-7")
        self.assertIs(evs[0]["paid"], False)

    def test_wp_programme_skips_the_archive_and_reads_one_slug(self):
        cards = events.wp_program_cards(WP, "https://litthusfred.no/program/")
        self.assertEqual(len(cards), 3)
        asked = []

        def detail(slug):
            asked.append(slug)
            return {"acf": {"pris": "0", "gratis": "ja"}, "excerpt": {"rendered": "<p>En kveld om Cantillon og bitcoin.</p>"}}

        src = {
            "venue": "Litteraturhuset", "address": "Storgata 11",
            "city": "Fredrikstad", "country": "NO", "max_links": 8,
        }
        evs = events.wp_events(src, cards, OSLO, detail)
        self.assertEqual(asked, ["cantillon-fredrikstad"])
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["start"].isoformat(), "2026-10-29T19:00:00+01:00")
        self.assertEqual(evs[0]["organiser"], "Bitcoinpolitisk institutt")
        self.assertEqual(evs[0]["place"], "Litteraturhuset Fredrikstad, Storgata 11")
        self.assertIs(evs[0]["paid"], False)
        self.assertIn("Cantillon", evs[0]["description"])

    def test_offsite_title_does_not_use_the_house_street(self):
        src = {"venue": "Litteraturhuset", "address": "Storgata 11", "name": "Litteraturhuset Fredrikstad"}
        self.assertEqual(events._venue_place(src, named="Lisleby samfunnshus"), "Lisleby samfunnshus")

    def test_run_writes_the_oslo_talk_as_pending(self):
        src = {
            "id": "litteraturhuset-oslo", "name": "Litteraturhuset Oslo", "type": "sanity-events",
            "country": "NO", "city": "Oslo", "venue": "Litteraturhuset", "address": "Wergelandsveien 29",
            "url": "https://www.litteraturhuset.no/nb/kalender",
            "site": "https://www.litteraturhuset.no",
            "api": "https://4bjarlop.api.sanity.io/v2021-06-07/data/query/production",
            "keyword_profile": "crypto-money", "trusted": False, "enabled": True, "lang_path": "nb",
        }
        body = json.dumps(sanity_payload())

        class Resp:
            text = body
            status_code = 200

            def raise_for_status(self):
                return None

        with tempfile.TemporaryDirectory() as root:
            new = events.run(lambda url: Resp(), lambda url: True, lambda t: False, lambda *a: None,
                             {"event_sources": [src], "min_delay_seconds": 0, "user_agent": "test"},
                             root=root, now=NOW)
            saved = json.load(open(os.path.join(root, "data", "events.json"), encoding="utf-8"))
        titles = sorted(e["title"] for e in new)
        self.assertEqual(titles, ["Bitcoin er tid", "Cantillon-effekten & pengar", "Inflasjon og sentralbanken"])
        self.assertTrue(all(e["status"] == "pending" and e["country"] == "NO" for e in new))
        cant = next(e for e in saved["events"] if "Cantillon" in e["title"])
        self.assertEqual(cant["start"], "2026-10-29T19:00:00+01:00")
        self.assertEqual(cant["end"], "2026-10-29T20:00:00+01:00")
        self.assertEqual(cant["city"], "Oslo")
        self.assertIn("Wergelandsveien 29", cant["place"])
        self.assertTrue(cant["url"].endswith("/nb/arrangement/cantillon-effekten-and-pengar"))
        self.assertEqual(cant["source"], "Litteraturhuset Oslo")

    def test_sources_are_registered(self):
        cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
        by = {s["id"]: s for s in cfg["event_sources"]}
        self.assertEqual(by["litteraturhuset-oslo"]["type"], "sanity-events")
        self.assertIn("4bjarlop.api.sanity.io", by["litteraturhuset-oslo"]["api"])
        self.assertEqual(by["litteraturhuset-bergen"]["type"], "webflow-program")
        self.assertEqual(by["litteraturhuset-fredrikstad"]["type"], "wp-program")
        for sid in ("litteraturhuset-oslo", "litteraturhuset-bergen", "litteraturhuset-fredrikstad"):
            self.assertFalse(by[sid]["trusted"])
            self.assertEqual(by[sid]["keyword_profile"], "crypto-money")
            blob = (by[sid].get("url") or "") + " " + (by[sid].get("api") or "")
            self.assertNotIn("ticketco", blob.lower())
            self.assertNotIn("crescat", blob.lower())


if __name__ == "__main__":
    unittest.main()
