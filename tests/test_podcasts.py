"""Podcasts: data/podcasts.json, nav tab, i18n keys, robots handling and the newsletter section.
  python3 tests/test_podcasts.py"""
import datetime as dt, os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "newsletter")]
import i18n, podcasts, build, digest


class Podcasts(unittest.TestCase):
    def test_data(self):
        self.assertEqual(podcasts.problems(), [])
        rows = podcasts.rows()
        self.assertEqual(len(rows), 25)
        act = [r["active"] for r in rows]
        self.assertEqual(act, sorted(act, reverse=True))
        by = {r["id"]: r for r in rows}
        self.assertEqual(by["kryptopodden"]["country"], "SE")
        self.assertIn("advertiser-paid", by["kryptoskeptikerne"]["flags"])
        self.assertIn("altcoin-promotion", by["morgendagens-krypto"]["flags"])

    def test_nav_and_i18n(self):
        self.assertIn(("podcasts", "nav_podcasts"), build.NAV)
        keys = [k for k in i18n.strings("en") if k == "nav_podcasts" or k.startswith(("podcasts_", "pod_flag_"))]
        self.assertEqual(len(keys), 16)
        for lang in i18n.ALL_LANGS:
            for k in keys:
                self.assertTrue(i18n.strings(lang).get(k), f"{lang} {k}")

    def test_podcast_sources_not_in_news(self):
        import json
        cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
        feeds = {r["feed"] for r in podcasts.rows()}
        for s in cfg["sources"]:
            if s.get("feed") in feeds:
                self.assertTrue(s.get("podcast"), s["id"])

    def test_newsletter_section(self):
        d = dt.date(2026, 10, 16)
        pods = digest.new_podcasts(d, d)
        self.assertEqual(len(pods), 25)
        md, _tx, _h = digest.render([], "nb", d, d, pods[:1])
        self.assertIn("## Nye podkaster", md)
        self.assertEqual(digest.new_podcasts(d + dt.timedelta(days=1), d + dt.timedelta(days=7)), [])


if __name__ == "__main__":
    unittest.main()
