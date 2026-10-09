#!/usr/bin/env python3
"""Front page: no filter bar, no story picture, lead plus a left-aligned grid."""
import json, os, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build

class FrontLayout(unittest.TestCase):
    def test_css_is_a_left_aligned_grid(self):
        # The latest stories are one column of rows at every width (headlines line up and read top to bottom);
        # the events and the newsletter sit in a rail beside them from 1024px (home.css).
        css = build.CSS
        self.assertIn(".storygrid{display:grid;grid-template-columns:1fr;", css)
        self.assertNotIn(".storygrid{grid-template-columns:1fr 1fr", css)
        self.assertIn(".leadstory h2{font-size:36px;", css)
        self.assertIn(".home{display:grid;grid-template-columns:minmax(0,1fr);", css)
        home = css.split("/* Front page layout.")[1].split(".home-note{")[0]
        for centred in ("text-align:center", "justify-content:center", "margin:0 auto"):
            self.assertNotIn(centred, home)
        block = css.split(".leadstory,.latest,.storygrid")[1].split(".orig{")[0]
        self.assertNotIn("text-align:center", block)
        self.assertNotIn("justify-content:center", block)
        self.assertNotIn("margin:0 auto", block)

    def test_home_source_has_no_filter_bar(self):
        with open(os.path.join(ROOT, "build.py"), encoding="utf-8") as fh:
            src = fh.read()
        home = src.split("def build_lang", 1)[1].split("def map_category", 1)[0]
        self.assertNotIn('id="fsrc"', home)
        self.assertNotIn("tchip", home)
        self.assertNotIn('aria-label="{E(t("filters"))}"', home)
        self.assertIn("front_events_block", home)
        self.assertIn("front_card", home)

    def test_card_has_no_picture_and_keeps_the_logo(self):
        with open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8") as fh:
            news = json.load(fh)
        item = next(i for i in news["items"] if i.get("status") == "published" and i.get("source_name"))
        build.LANG = "en"
        with tempfile.TemporaryDirectory() as tmp:
            old = build.SITE
            build.SITE = tmp
            try:
                html = build.front_card(item, {}, "", lead=True)
            finally:
                build.SITE = old
        self.assertIn('class="leadstory"', html)
        self.assertNotIn("<figure", html)
        self.assertNotIn('class="ill"', html)
        self.assertNotIn("<img", html[:html.find('class="src"')] if 'class="src"' in html else html)
        self.assertIn('class="src"', html)
        self.assertIn(item["source_name"], html)
        self.assertLess(html.find("<h2>"), html.find('class="sum"'))
        self.assertLess(html.find('class="sum"'), html.find('class="meta"'))
        self.assertNotIn("text-align:center", html)

if __name__ == "__main__":
    unittest.main()
