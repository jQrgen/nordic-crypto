#!/usr/bin/env python3
"""Diff for the post-publish push. No network, no imports of news."""
import importlib.util, json, os, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "push_notify.py")

def load_mod():
    spec = importlib.util.spec_from_file_location("push_notify", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def item(i, **kw):
    row = {"id": i, "url": f"https://example.no/{i}", "title": f"Title {i}", "title_en": f"English {i}",
           "summary": "A short summary of what the story says, in our own words.", "country": "NO",
           "language": "Norwegian", "status": "published", "summary_i18n": {"nn": "Eit kort samandrag."}}
    row.update(kw)
    return row

class DiffTest(unittest.TestCase):
    def test_only_new_ids(self):
        mod = load_mod()
        prev = {"items": [item("a")]}
        cur = {"items": [item("a"), item("b", country="SE", language="Swedish", url="https://example.se/b")]}
        out = mod.new_stories(prev, cur)
        self.assertEqual([s["url"] for s in out], ["https://example.se/b"])
        self.assertEqual(out[0]["country"], "SE")
        self.assertIn("nn", out[0]["summaries"])
        self.assertTrue(out[0]["url"].startswith("https://"))

    def test_relative_own_story(self):
        mod = load_mod()
        cur = {"items": [item("s", url="stories/hello/", own_story=True, summary="", title_en="Our piece")]}
        out = mod.new_stories({"items": []}, cur)
        self.assertEqual(out[0]["url"], "https://cryptonordic.no/stories/hello/")

    def test_pending_is_not_new(self):
        mod = load_mod()
        cur = {"items": [item("p", status="pending")]}
        self.assertEqual(mod.new_stories({"items": []}, cur), [])

    def test_dry_run_and_refuse_empty_archive(self):
        with tempfile.TemporaryDirectory() as d:
            prev = os.path.join(d, "old.json")
            cur = os.path.join(d, "new.json")
            with open(prev, "w", encoding="utf-8") as f: json.dump({"items": []}, f)
            with open(cur, "w", encoding="utf-8") as f: json.dump({"items": [item("a")]}, f)
            r = subprocess.run([sys.executable, SCRIPT, "--previous", prev, "--current", cur, "--dry-run"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertIn("full archive", r.stdout + r.stderr)
            self.assertNotIn("https://example.no/a", r.stdout)
            with open(prev, "w", encoding="utf-8") as f: json.dump({"items": [item("a")]}, f)
            with open(cur, "w", encoding="utf-8") as f: json.dump({"items": [item("a"), item("b")]}, f)
            r = subprocess.run([sys.executable, SCRIPT, "--previous", prev, "--current", cur, "--dry-run"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            body = json.loads(r.stdout)
            self.assertEqual(len(body["stories"]), 1)
            self.assertEqual(body["stories"][0]["title"], "English b")

    def test_panel_is_left_aligned_and_translated(self):
        sys.path.insert(0, ROOT)
        os.environ["PUSH_ENDPOINT"] = ""
        import build
        self.assertIn("text-align:start", build.CSS)
        self.assertNotIn(".pushopt{text-align:center", build.CSS.replace(" ", ""))
        build.LANG = "en"
        html = build.push_panel("./")
        self.assertIn("Turn on notifications", html)
        self.assertIn('id="notifications"', html)
        self.assertIn('value="ALL"', html)
        self.assertIn("Cloudflare Web Analytics", html)
        build.LANG = "nn"
        nn = build.push_panel("../")
        self.assertIn("Slå på varslingar", nn)
        self.assertNotIn(">AI<", nn)
        self.assertNotRegex(nn, r"(?<![\w-])(?:AI|KI)(?![\w])")
        build.LANG = "de"
        self.assertIn("Mitteilungen einschalten", build.push_panel("./"))
        with open(os.path.join(ROOT, "assets", "push", "sw.js"), encoding="utf-8") as f:
            sw = f.read()
        self.assertNotIn("caches.open", sw)
        self.assertIn("showNotification", sw)

if __name__ == "__main__":
    unittest.main()
