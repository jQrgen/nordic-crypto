#!/usr/bin/env python3
"""KÅKÅ (Squarespace) programme intake. No network. Does not write data/events.json."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import events

SRC = {"id": "kaakaa", "name": "KÅKÅ", "country": "NO", "city": "Stavanger", "venue": "KÅKÅ",
       "url": "https://www.kaakaa.no/program", "site": "https://www.kaakaa.no", "type": "squarespace-events",
       "trusted": False, "organiser": "KÅKÅ"}
PAYLOAD = {"upcoming": [
    {"title": "Har bankene kuppet kryptorevolusjonen?", "fullUrl": "/program/har-bankene-kuppet-kryptorevolusjonen",
     "startDate": 1792859400387, "endDate": 1792862100387,
     "excerpt": "<p>Når bankene omfavner kryptovaluta, hvem får makten over framtidens penger?</p>",
     "body": "<p>Bitcoin og kryptovaluta ble født ut av en mistillit til bankene.</p>",
     "location": {"addressTitle": "Vingtor", "addressLine1": ""}},
    {"title": "Sentralbankens time: Den vanskelige pengepolitikken", "fullUrl": "/program/sentralbankens-time",
     "startDate": 1792681200000, "endDate": 1792684800000, "excerpt": "<p>Renten og inflasjonen.</p>", "body": "",
     "location": {"addressTitle": "Gaffel &amp; Karaffel"}},
]}


def matches(text):
    return any(w in text.lower() for w in ("bitcoin", "krypto", "blockchain"))


class KaakaaTest(unittest.TestCase):
    def test_query_url(self):
        self.assertEqual(events.squarespace_query_url(SRC), "https://www.kaakaa.no/program?format=json")

    def test_crypto_only_with_oslo_time(self):
        evs = events.squarespace_events(SRC, PAYLOAD, "Europe/Oslo", matches)
        self.assertEqual([e["title"] for e in evs], ["Har bankene kuppet kryptorevolusjonen?"])
        e = evs[0]
        self.assertEqual(e["start"].isoformat(), "2026-10-24T18:30:00+02:00")
        self.assertEqual(e["end"].isoformat(), "2026-10-24T19:15:00+02:00")
        self.assertEqual(e["place"], "Vingtor")
        self.assertEqual(e["city"], "Stavanger")
        self.assertEqual(e["url"], "https://www.kaakaa.no/program/har-bankene-kuppet-kryptorevolusjonen")
        self.assertIsNone(e["paid"])

    def test_crypto_money_profile_keeps_monetary_policy(self):
        evs = events.squarespace_events(dict(SRC, keyword_profile="crypto-money"), PAYLOAD, "Europe/Oslo", matches)
        self.assertEqual(len(evs), 2)
        self.assertEqual(evs[1]["place"], "Gaffel & Karaffel")

    def test_kryptorevolusjon_is_crypto(self):
        self.assertTrue(events.crypto_money_hit("Har bankene kuppet kryptorevolusjonen?"))
        self.assertFalse(events.crypto_money_hit("Kryptisk dikt"))


if __name__ == "__main__":
    unittest.main()
