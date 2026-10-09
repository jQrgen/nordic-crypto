#!/usr/bin/env python3
"""Story cards lead with the page-language headline and keep the source headline underneath."""
import json, os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build
from tools.headlines import card_headline, check, needed_langs, public_title_i18n

NEWS = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8"))
BY_ID = {i["id"]: i for i in NEWS["items"]}

# The Nynorsk screenshot: Swedish source headlines were the only title.
DUCT = "2d38c9c89e0e"
LICENCE = "7b2030aea964"


class Headlines(unittest.TestCase):
    def test_catalogue(self):
        self.assertEqual(check(), 0)

    def test_nynorsk_shows_translated_headline_and_swedish_original(self):
        for sid, nn_start in (
            (DUCT, "Opplysningar:"),
            (LICENCE, "Kryptokjempa"),
        ):
            it = BY_ID[sid]
            head, code, orig = card_headline(it, "nn")
            self.assertEqual(code, "nn")
            self.assertTrue(head.startswith(nn_start), head)
            self.assertEqual(orig, it["title"])
            self.assertNotEqual(head, it["title"])
            build.LANG = "nn"
            shown, _hl, attr, html = build.story_heads(it)
            self.assertEqual(shown, head)
            self.assertEqual(attr, "")
            self.assertIn(it["title"], html)
            self.assertIn('lang="sv"', html)
            self.assertIn('class="orig"', html)
            self.assertIn("Originaltittel (svensk):", html)

    def test_same_language_is_one_headline(self):
        it = BY_ID[DUCT]
        head, code, orig = card_headline(it, "sv")
        self.assertEqual(head, it["title"])
        self.assertEqual(orig, "")
        self.assertEqual(code, "sv")
        nb = next(i for i in NEWS["items"] if i.get("status") == "published" and i.get("language") == "Norwegian")
        head, code, orig = card_headline(nb, "nb")
        self.assertEqual(head, nb["title"])
        self.assertEqual(orig, "")
        en = BY_ID["f6301aef3314"]
        head, code, orig = card_headline(en, "en")
        self.assertEqual(head, en["title"])
        self.assertEqual(orig, "")

    def test_other_pairs_and_english_fallback(self):
        it = BY_ID[LICENCE]
        head, code, orig = card_headline(it, "da")
        self.assertEqual(code, "da")
        self.assertIn("uden licens", head)
        self.assertEqual(orig, it["title"])
        head, code, orig = card_headline(it, "en")
        self.assertEqual(head, it["title_en"])
        self.assertEqual(code, "en")
        self.assertEqual(orig, it["title"])
        head, code, orig = card_headline(it, "de")
        self.assertEqual(head, it["title_en"])
        self.assertEqual(code, "en")
        self.assertEqual(orig, it["title"])
        # Bokmål on a Nynorsk page is a different written language.
        nb = BY_ID["fb9e8ca4fb40"]
        head, code, orig = card_headline(nb, "nn")
        self.assertEqual(code, "nn")
        self.assertNotEqual(head, nb["title"])
        self.assertEqual(orig, nb["title"])

    def test_bridge_stays_when_the_headline_is_translated(self):
        it = BY_ID[DUCT]
        build.LANG = "nn"
        _head, head_l, _attr, _html = build.story_heads(it)
        self.assertTrue(build.source_is_foreign(it, head_l))
        build.LANG = "en"
        _head, head_l, _attr, html = build.story_heads(it)
        self.assertFalse(build.source_is_foreign(it, head_l))
        self.assertIn(it["title"], html)

    def test_public_map_omits_a_headline_that_repeats_the_source(self):
        it = BY_ID["8ae149a20f5f"]  # "Pangstart …" is the same in nynorsk
        pub = public_title_i18n(it)
        self.assertNotIn("nn", pub)
        self.assertIn("sv", pub)
        head, _code, orig = card_headline(it, "nn")
        self.assertEqual(head, it["title"])
        self.assertEqual(orig, "")

    def test_needed_langs_skip_the_source_language(self):
        self.assertNotIn("sv", needed_langs("Swedish"))
        self.assertIn("nn", needed_langs("Swedish"))
        self.assertNotIn("nb", needed_langs("Norwegian"))
        self.assertEqual(needed_langs("English"), ["nn", "nb", "sv", "da", "fi", "is"])

    def test_item_translation_wins_and_a_stale_source_is_dropped(self):
        it = {"id": DUCT, "title": BY_ID[DUCT]["title"], "language": "Swedish", "title_en": "Reports",
              "title_i18n": {"nn": "Frå saka"}, "title_i18n_source": BY_ID[DUCT]["title"]}
        head, code, orig = card_headline(it, "nn")
        self.assertEqual((head, code, orig), ("Frå saka", "nn", it["title"]))
        it["title_i18n_source"] = "old headline"
        head, _code, orig = card_headline(it, "nn")
        self.assertNotEqual(head, "Frå saka")
        self.assertEqual(orig, it["title"])


if __name__ == "__main__":
    unittest.main()
