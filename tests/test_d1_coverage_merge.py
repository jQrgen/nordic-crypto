#!/usr/bin/env python3
"""A stale checkout must not drop outlets that D1 already has on a reviewed story.

  python3 -m unittest tests.test_d1_coverage_merge
"""
import json
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, ROOT)
from tools import d1_store

DN = {"outlet": "dn", "url": "https://www.dn.no/krypto/a/1", "title": "DN"}
NRK = {"outlet": "nrk", "url": "https://www.nrk.no/krypto-1", "title": "NRK"}
E24 = {"outlet": "e24", "url": "https://e24.no/krypto/a/2?utm_source=x", "title": "E24"}
FIRST_FETCH = "2026-10-01T03:00:00+00:00"


def story(extras, seen_via, fetched=FIRST_FETCH):
    return {
        "id": "s1", "url": "https://firi.com/news/1", "title": "Story", "source": "firi",
        "status": "published", "summary": "Editor summary.",
        "approved_by": "Editor", "approved_at": "2026-10-01T09:00:00+00:00",
        "also_covered_by": extras, "seen_via": seen_via, "matched": ["Firi"],
        "fetched": fetched, "published": "2026-10-01T02:00:00+00:00",
    }


class StaleCheckout(unittest.TestCase):
    """D1 has s1 approved with [dn, nrk] and [e24, bing-no]. The checkout is older."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nc-d1-cov-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.store = d1_store.open_sqlite(os.path.join(self.tmp, "content.sqlite"))
        d1_store.import_stories(self.store, [story([DN, NRK], ["e24", "bing-no"])], "2026-10-02T08:00:00+00:00", "import")
        row = d1_store.one(self.store, "SELECT review_status FROM stories WHERE id = 's1'")
        self.assertEqual(row["review_status"], "approved")
        os.makedirs(os.path.join(self.tmp, "data"))

    def write(self, item):
        with open(os.path.join(self.tmp, "data", "news.json"), "w", encoding="utf-8") as fh:
            json.dump({"items": [item]}, fh)

    def push(self):
        return d1_store.sync_root(self.store, self.tmp, "2026-10-10T03:00:00+00:00")["stories"]

    def payload(self):
        return json.loads(d1_store.one(self.store, "SELECT payload FROM stories WHERE id = 's1'")["payload"])

    def audits(self):
        return d1_store.one(self.store, "SELECT COUNT(*) AS n FROM review_audit WHERE item_id = 's1'")["n"]

    def test_restore_then_push_keeps_d1_outlets(self):
        self.write(story([DN], ["e24"]))
        self.assertEqual(d1_store.restore_root(self.store, self.tmp)["stories_added"], 0)
        before = self.audits()
        stories = self.push()
        self.assertEqual(stories["coverage"], 0)
        self.assertEqual(stories["kept"], 1)
        got = self.payload()
        self.assertEqual([ex["outlet"] for ex in got["also_covered_by"]], ["dn", "nrk"])
        self.assertEqual(got["seen_via"], ["e24", "bing-no"])
        self.assertEqual(self.audits(), before)

    def test_new_outlet_is_appended_after_the_d1_ones(self):
        dn_noise = dict(DN, url="https://dn.no/krypto/a/1/?utm_source=rss")
        self.write(story([dn_noise, E24], ["e24", "nightly"], fetched="2026-10-10T03:00:00+00:00"))
        before = self.audits()
        self.assertEqual(self.push()["coverage"], 1)
        got = self.payload()
        self.assertEqual([ex["outlet"] for ex in got["also_covered_by"]], ["dn", "nrk", "e24"])
        self.assertEqual(got["also_covered_by"][0]["url"], DN["url"])
        self.assertEqual(got["seen_via"], ["e24", "bing-no", "nightly"])
        self.assertEqual(got["matched"], ["Firi"])
        self.assertEqual(got["fetched"], FIRST_FETCH)
        self.assertEqual(got["summary"], "Editor summary.")
        self.assertEqual(self.audits(), before + 1)

    def test_primary_url_is_not_an_extra(self):
        primary = {"outlet": "firi", "url": "https://www.firi.com/news/1?utm_medium=feed", "title": "Firi"}
        self.write(story([DN, primary, "not-an-outlet", {"outlet": "x"}], ["e24"]))
        self.assertEqual(self.push()["kept"], 1)
        self.assertEqual([ex["outlet"] for ex in self.payload()["also_covered_by"]], ["dn", "nrk"])

    def test_nothing_new_is_kept_without_an_audit_row(self):
        self.write(story([dict(NRK, url="https://nrk.no/krypto-1/"), DN], ["bing-no", "e24"]))
        before = self.audits()
        stories = self.push()
        self.assertEqual(stories["kept"], 1)
        self.assertEqual(stories["coverage"], 0)
        self.assertEqual(self.audits(), before)


if __name__ == "__main__":
    unittest.main()
