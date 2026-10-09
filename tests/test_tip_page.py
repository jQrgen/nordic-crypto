#!/usr/bin/env python3
"""/tip/: a private tip to tipworker's inbox, never a public GitHub issue. Closed (no form) until the Worker endpoint and a
Turnstile site key are both set. No network."""
import os, shutil, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build

ENV = ("TIP_ENDPOINT", "TIP_TURNSTILE_SITE_KEY", "CHAT_TURNSTILE_SITE_KEY", "TIP_PAGE_SERVER", "TIP_ONION")

class TipPage(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ENV}
        for k in ENV: os.environ.pop(k, None)
        os.environ["TIP_ENDPOINT"] = ""          # ignore whatever tipserver/config.json holds
        os.environ["TIP_TURNSTILE_SITE_KEY"] = ""
        os.environ["TIP_ONION"] = ""
        self.tmp = tempfile.mkdtemp(prefix="nc-tip-"); self.old_site = build.SITE; build.SITE = self.tmp

    def tearDown(self):
        build.SITE = self.old_site; shutil.rmtree(self.tmp, ignore_errors=True)
        for k, v in self.saved.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def page(self, lang):
        build.LANG = lang
        build.build_tip()
        with open(os.path.join(self.tmp, "" if lang == "en" else lang, "tip", "index.html"), encoding="utf-8") as fh:
            return fh.read()

    def assertNoGithub(self, html):
        self.assertNotIn("issues/new", html); self.assertNotIn("template=tip.yml", html)

    def test_closed_by_default(self):
        self.assertEqual(build.tip_intake(), (None, None))
        for lang in ("en", "nb", "da", "de"):
            html = self.page(lang)
            self.assertNotIn('id="tipform"', html); self.assertNoGithub(html)
            self.assertIn(build.i18n.t(lang, "tip_private_soon"), html)

    def test_endpoint_without_key_stays_closed(self):
        os.environ["TIP_ENDPOINT"] = "https://tips.nordiccrypto.no"
        self.assertEqual(build.tip_intake(), (None, None))
        self.assertNotIn('id="tipform"', self.page("en"))

    def test_quick_tunnel_never_opens_the_private_form(self):
        os.environ["TIP_PAGE_SERVER"] = "1"; os.environ["TIP_TURNSTILE_SITE_KEY"] = "1x00000000000000000000AA"
        self.assertNotIn('id="tipform"', self.page("en"))

    def test_open_with_endpoint_and_key(self):
        os.environ["TIP_ENDPOINT"] = "https://tips.nordiccrypto.no"
        os.environ["TIP_TURNSTILE_SITE_KEY"] = "1x00000000000000000000AA"
        self.assertEqual(build.tip_intake(), ("https://tips.nordiccrypto.no", "1x00000000000000000000AA"))
        html = self.page("en")
        self.assertIn('<form id="tipform"', html); self.assertNoGithub(html)
        self.assertIn('"https://tips.nordiccrypto.no"', html); self.assertIn("/api/private-tip", html)
        self.assertIn('class="cf-turnstile" data-sitekey="1x00000000000000000000AA"', html)
        self.assertIn("challenges.cloudflare.com/turnstile", html)
        for name in ('name="tip"', 'name="attachments"', 'name="contact"', 'name="website"'): self.assertIn(name, html)
        self.assertIn("artificial intelligence is not a human", html)
        nb = self.page("nb")
        self.assertIn("kunstig intelligens", nb); self.assertNoGithub(nb)

    def test_bad_endpoint_or_key_is_refused(self):
        os.environ["TIP_ENDPOINT"] = "http://tips.nordiccrypto.no"
        os.environ["TIP_TURNSTILE_SITE_KEY"] = "1x00000000000000000000AA"
        self.assertEqual(build.tip_intake(), (None, None))
        os.environ["TIP_ENDPOINT"] = "https://tips.nordiccrypto.no"; os.environ["TIP_TURNSTILE_SITE_KEY"] = "bad key\"><script>"
        self.assertEqual(build.tip_intake(), (None, None))

    def test_tor_named_without_an_address(self):
        html = self.page("en")
        self.assertIn(build.i18n.t("en", "tip_onion_pending"), html); self.assertNotIn("onion-location", html)
        self.assertIsNone(build.tip_onion())

    def test_onion_link_and_meta_when_address_exists(self):
        addr = "http://" + "a" * 56 + ".onion"
        os.environ["TIP_ONION"] = addr
        for lang in ("en", "sv"):
            html = self.page(lang)
            self.assertIn(f'<meta http-equiv="onion-location" content="{addr}/{lang}/">', html)
            self.assertIn(f'href="{addr}/{lang}/"', html); self.assertNoGithub(html)
        os.environ["TIP_ENDPOINT"] = "https://tips.nordiccrypto.no"; os.environ["TIP_TURNSTILE_SITE_KEY"] = "1x00000000000000000000AA"
        self.assertIn("onion-location", self.page("en"))

    def test_bad_onion_address_is_ignored(self):
        for bad in ("http://short.onion", "https://" + "a" * 56 + ".onion", "http://" + "A" * 56 + ".onion", 'http://x"><script>'):
            os.environ["TIP_ONION"] = bad
            self.assertIsNone(build.tip_onion(), bad)

    def test_retired_github_template(self):
        with open(os.path.join(ROOT, ".github", "ISSUE_TEMPLATE", "tip.yml"), encoding="utf-8") as fh:
            tpl = fh.read()
        self.assertIn("retired", tpl); self.assertNotIn("id: url", tpl)

if __name__ == "__main__":
    unittest.main()
