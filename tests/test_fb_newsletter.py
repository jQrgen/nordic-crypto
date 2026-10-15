import contextlib, io, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import fb_newsletter as fb


class Post(unittest.TestCase):
    def test_every_issue(self):
        for meta in json.load(open(os.path.join(fb.PUBLISHED, "issues.json")))["issues"]:
            m = fb.load_issue(meta["id"]); p = fb.build_post(m)
            self.assertTrue(p["title"].startswith(f"Nordic Crypto #{m['number']}: "))
            self.assertIn(fb.issue_url(m), p["description"])
            for s in m["stories_list"]:
                self.assertIn(s["url"], p["description"]); self.assertIn(s["title"], p["description"])
            text = p["title"] + p["description"]
            self.assertNotIn("Crypto Nordic", text); self.assertNotIn("made with ai", text.lower())
            self.assertNotIn("sponsor", text.lower())

    def test_parse_stories(self):
        h = '<p><a href="https://a.example/1" style="font-weight:bold">T</a> (o)<br>S one. Two. Three.<br><span>x</span></p>'
        self.assertEqual(fb.parse_stories(h), [{"title": "T", "summary": "S one. Two. Three.", "url": "https://a.example/1"}])


class Run(unittest.TestCase):
    def setUp(self):
        self.state = os.path.join(tempfile.mkdtemp(), "fb.json")
        self._gp = fb.graph_post
        fb.graph_post = lambda *a, **k: self.fail("must not call Graph API")
        for k in fb.ENV: os.environ.pop(k, None)

    def tearDown(self):
        fb.graph_post = self._gp
        for k in fb.ENV: os.environ.pop(k, None)

    def test_dry_run(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(fb.main(["--issue", "2", "--dry-run", "--state", self.state]), 0)
        self.assertIn("Title: Nordic Crypto #2", buf.getvalue())
        self.assertFalse(os.path.exists(self.state))

    def test_missing_secrets(self):
        self.assertEqual(fb.main(["--issue", "002", "--state", self.state]), 0)
        self.assertFalse(os.path.exists(self.state))

    def test_already_posted(self):
        fb.save_state(self.state, {"002": {"video_id": "1"}})
        for k in fb.ENV: os.environ[k] = "x"
        self.assertEqual(fb.main(["--issue", "002", "--state", self.state]), 0)

    def test_posts_once_with_file_url(self):
        for k in fb.ENV: os.environ[k] = "x"
        calls = []
        fb.graph_post = lambda url, fields, path=None: calls.append((url, fields, path)) or {"id": "99"}
        live, fb.is_live = fb.is_live, lambda u: True
        try:
            fb.main(["--issue", "002", "--state", self.state]); fb.main(["--issue", "002", "--state", self.state])
        finally:
            fb.is_live = live
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][0].endswith("/x/videos")); self.assertIn("file_url", calls[0][1])
        self.assertEqual(json.load(open(self.state))["002"]["video_id"], "99")


if __name__ == "__main__":
    unittest.main()
