#!/usr/bin/env python3
"""Front-page cards use a 2–4 sentence blurb when the editorial summary is a single sentence."""
import json, os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.frontpage_blurbs import LANGS, card_text, check, load, opening_sentences, sentences, substantive

class FrontPageBlurbs(unittest.TestCase):
    def test_catalogue(self):
        self.assertEqual(check(), 0)

    def test_card_prefers_a_real_summary(self):
        item = {"id": "x", "summary": "One fact. Another fact.", "summary_i18n": {"sv": "Ett. Två."}}
        text, lang = card_text(item, "sv", {})
        self.assertEqual((text, lang), ("Ett. Två.", "sv"))
        text, lang = card_text(item, "de", {})
        self.assertEqual(lang, "en")
        self.assertTrue(text.startswith("One fact."))

    def test_card_uses_blurb_when_the_summary_is_one_sentence(self):
        blurbs = load()
        news = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8"))
        sample = next(i for i in news["items"] if i.get("status") == "published")
        self.assertEqual(len(sentences(sample["summary"])), 1)
        for lang in ("en", "nn", "nb", "sv", "da", "fi", "is"):
            text, code = card_text(sample, lang, blurbs)
            self.assertEqual(code, lang)
            n = len(sentences(text))
            self.assertGreaterEqual(n, 2, text)
            self.assertLessEqual(n, 4, text)
            self.assertNotEqual(text, sample["summary"])
        text, code = card_text(sample, "de", blurbs)
        self.assertEqual(code, "en")
        self.assertGreaterEqual(len(sentences(text)), 2)
        text, code = card_text(sample, "ar", blurbs)
        self.assertEqual(code, "en")

    def test_every_published_story_and_language(self):
        blurbs = load()
        news = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8"))
        published = [i for i in news["items"] if i.get("status") == "published" and (i.get("summary") or "").strip()]
        self.assertGreaterEqual(len(published), 1)
        for it in published:
            self.assertEqual(set((blurbs.get(it["id"]) or {})), set(LANGS))
            for lang in list(LANGS) + ["zh", "ur"]:
                text, _ = card_text(it, lang, blurbs)
                self.assertTrue(substantive(text), it["id"] + " " + lang)

    def test_opening_of_our_own_story_is_scannable(self):
        text = opening_sentences("Alpha happens. Beta follows. Gamma too. Delta next. Epsilon is the rest of the piece.")
        self.assertEqual(len(sentences(text)), 4)
        self.assertFalse(text.endswith("Epsilon is the rest of the piece."))

    def test_layout_stays_left(self):
        import site_css
        css = site_css.bundle()
        self.assertIn("ol.news{list-style:none;margin:0;padding:0;text-align:left}", css)
        self.assertIn(".sum{margin:6px 0 0;max-width:72ch;line-height:1.55;text-align:left}", css)
        self.assertIn(".bridge{margin:6px 0 0;font-weight:500;text-align:left}", css)

    def test_blurbs_do_not_call_kaupr_a_sponsor(self):
        raw = open(os.path.join(ROOT, "data", "frontpage_blurbs.json"), encoding="utf-8").read().lower()
        self.assertNotIn("sponsored by kaupr", raw)
        self.assertNotIn("kaupr sponsors", raw)
        self.assertNotIn("made with ai", raw)
        self.assertNotIn("made with artificial", raw)

if __name__ == "__main__":
    unittest.main()
