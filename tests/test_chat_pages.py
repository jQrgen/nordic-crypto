#!/usr/bin/env python3
"""Shoutbox pages: hidden while chat/config.json is off, one shared room when a test build turns it on."""
import json, os, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build
import i18n

KEYS = [k for k in i18n.strings("en") if k == "nav_chat" or k.startswith("chat_")]
CLIENT = os.path.join(ROOT, "assets", "chat", "client.js")


class ChatPages(unittest.TestCase):
    def setUp(self):
        self.site, self.lang = build.SITE, build.LANG
        self.env = {k: os.environ.get(k) for k in ("NC_CHAT", "CHAT_ENDPOINT", "CHAT_TURNSTILE_SITE_KEY")}
        os.environ.pop("NC_CHAT", None)
        os.environ.pop("CHAT_ENDPOINT", None)
        os.environ.pop("CHAT_TURNSTILE_SITE_KEY", None)

    def tearDown(self):
        build.SITE, build.LANG = self.site, self.lang
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_config_is_off(self):
        cfg = json.load(open(os.path.join(ROOT, "chat", "config.json"), encoding="utf-8"))
        self.assertIs(cfg["enabled"], False)
        self.assertIsNone(cfg["endpoint"])
        self.assertIsNone(cfg["turnstile_site_key"])

    def test_every_language_has_the_ui_strings(self):
        self.assertGreaterEqual(len(KEYS), 30)
        for lang in i18n.ALL_LANGS:
            for key in KEYS:
                self.assertIn(key, i18n.strings(lang), f"{lang} {key}")
            rules = i18n.t(lang, "chat_rules", ethics="../ethics/")
            self.assertIn("../ethics/", rules)
            self.assertIn("{n}", i18n.strings(lang)["chat_time_m"])
            self.assertNotIn("Crypto Nordic", i18n.t(lang, "chat_user"))

    def test_nothing_is_rendered_while_disabled(self):
        build.LANG = "en"
        self.assertIsNone(build.chat_endpoint())
        self.assertEqual(build.shoutbox_html("ethics/"), "")
        self.assertEqual(build.shout_script(), "")
        self.assertEqual(build.home_with_chat("<p>news</p>"), "<p>news</p>")
        self.assertNotIn("chat", [slug for slug, _k in build.nav_items()])
        with tempfile.TemporaryDirectory() as d:
            build.SITE = d
            build.page("ping", "Ping", "ping", "<p>x</p>", "d")
            html = open(os.path.join(d, "ping", "index.html"), encoding="utf-8").read()
        self.assertNotIn('class="shoutbox', html)
        self.assertNotIn("NC_SHOUT", html)
        self.assertNotIn('href="../chat/"', html)
        self.assertNotIn(">Chat</a>", html)

    def test_enabled_build_is_one_room_left_aligned_and_translated(self):
        os.environ["NC_CHAT"] = "1"
        os.environ["CHAT_ENDPOINT"] = "http://127.0.0.1:8791"
        self.assertEqual(build.chat_endpoint(), "http://127.0.0.1:8791")
        client = open(CLIENT, encoding="utf-8").read()
        self.assertIn("textContent", client)
        self.assertNotIn("innerHTML", client)
        self.assertIn('localStorage', client)
        self.assertIn("nc_shout_nick", client)
        self.assertNotIn("document.cookie", client)
        self.assertNotIn("?lang", client)
        self.assertNotIn("WebSocket", client)
        self.assertIn("/api/shouts?limit=50", client)
        self.assertIn("15000", client)
        block = build.CSS.split("/* shoutbox */", 1)[1].split("/* /shoutbox */", 1)[0]
        self.assertNotIn("center", block)
        self.assertIn("text-align:start", block)
        self.assertIn(".shout-toggle{display:none", block.replace(" ", ""))
        self.assertIn("max-width:959px", block)
        pages = {}
        with tempfile.TemporaryDirectory() as d:
            build.SITE = d
            for lang in ("en", "sv", "ar"):
                build.LANG = lang
                build.build_chat()
                rel = os.path.join(d, "" if lang == "en" else lang, "chat", "index.html")
                pages[lang] = open(rel, encoding="utf-8").read()
            build.LANG = "en"
            home = build.home_with_chat("<p id=news>news</p>")
        for lang, html in pages.items():
            self.assertIn("http://127.0.0.1:8791", html)
            self.assertNotIn("/api/shouts?lang", html)
            self.assertNotIn("?room=", html)
            self.assertIn('href="../ethics/"', html)
            self.assertIn("shout-user", html)
            self.assertIn("shout-privacy", html)
            self.assertIn("localStorage", html)
            self.assertIn("pollMs", html)
            self.assertIn("15000", html)
            self.assertIn('class="shoutbox shoutbox-full"', html)
            self.assertIn("Nordic Crypto", html)
            self.assertNotIn("Crypto Nordic", html)
        self.assertIn("Skicka", pages["sv"])
        self.assertIn("Husregler", pages["sv"])
        self.assertIn("القواعد", pages["ar"])
        self.assertIn('dir="rtl"', pages["ar"])
        self.assertIn("These messages are written by readers", pages["en"])
        self.assertIn("daily-rotated hash", pages["en"])
        self.assertIn("not in a cookie", pages["en"])
        self.assertIn('aria-current=page', pages["en"])
        self.assertIn(">Chat</a>", pages["en"])
        # The baked page language differs. The endpoint does not.
        self.assertIn('"lang": "en"', pages["en"])
        self.assertIn('"lang": "sv"', pages["sv"])
        self.assertIn('"lang": "ar"', pages["ar"])
        self.assertEqual(pages["en"].count("http://127.0.0.1:8791"), pages["sv"].count("http://127.0.0.1:8791"))
        self.assertIn("home-with-chat", home)
        self.assertIn("shout-toggle", home)
        self.assertIn("Show chat", home)
        self.assertIn("<p id=news>news</p>", home)
        self.assertIn('href="ethics/"', home)
        self.assertIn('href="chat/"', home)
        self.assertNotIn("text-align:center", home)


if __name__ == "__main__":
    unittest.main()
