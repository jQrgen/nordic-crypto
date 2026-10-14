import contextlib, io, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import weibo_newsletter as m

ENV = ("WEIBO_ACCESS_TOKEN",)


class Copy(unittest.TestCase):
    def test_translation_matches_issue(self):
        meta = m.load_issue("002")
        tr, why = m.load_social(meta, "zh")
        self.assertIsNotNone(tr, why)
        self.assertEqual(len(tr["stories"]), len(meta["stories_list"]))

    def test_brand_rules(self):
        meta = m.load_issue("002"); tr, _ = m.load_social(meta, "zh")
        p = m.build_post(meta, tr)
        text = json.dumps(p, ensure_ascii=False) if isinstance(p, dict) else p
        self.assertIn("Nordic Crypto", text)
        self.assertIn(m.issue_url(meta), text)
        self.assertNotIn("Crypto Nordic", text)
        self.assertNotIn("made with ai", text.lower())
        self.assertNotIn("sponsor", text.lower())

    def test_missing_translation_skips(self):
        meta = dict(m.load_issue("002"), id="999")
        tr, why = m.load_social(meta, "zh")
        self.assertIsNone(tr); self.assertIn("social.zh.json", why)


class Run(unittest.TestCase):
    def setUp(self):
        self.state = os.path.join(tempfile.mkdtemp(), "s.json")
        self._h = m.http_json
        m.http_json = lambda *a, **k: self.fail("must not call the API")
        for k in ENV: os.environ.pop(k, None)

    def tearDown(self):
        m.http_json = self._h
        for k in ENV: os.environ.pop(k, None)

    def test_dry_run(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(m.main(["--issue", "2", "--dry-run", "--state", self.state]), 0)
        self.assertIn("# Issue 002", buf.getvalue())
        self.assertFalse(os.path.exists(self.state))

    def test_missing_secrets(self):
        self.assertEqual(m.main(["--issue", "002", "--state", self.state]), 0)
        self.assertFalse(os.path.exists(self.state))

    def test_already_posted(self):
        m.save_state(self.state, {"002": {"weibo_id": "1", "post_id": 1}})
        for k in ENV: os.environ[k] = "1"
        self.assertEqual(m.main(["--issue", "002", "--state", self.state]), 0)

    def test_length_and_cover_fallback(self):
        meta = m.load_issue("002"); tr, _ = m.load_social(meta, "zh")
        self.assertLessEqual(m.weibo_len(m.build_post(meta, tr)), m.LIMIT)
        for k in ENV: os.environ[k] = "t"
        os.environ.pop("WEIBO_VIDEO_UPLOAD_URL", None)
        calls = []
        m.http_json = lambda url, data=None, ct=None, **k: calls.append((url, data)) or {"idstr": "42"}
        live, m.is_live = m.is_live, lambda u: True
        try:
            m.main(["--issue", "002", "--state", self.state]); m.main(["--issue", "002", "--state", self.state])
        finally:
            m.is_live = live
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], m.SHARE)
        self.assertIn(b'name="pic"', calls[0][1])
        self.assertEqual(json.load(open(self.state))["002"]["weibo_id"], "42")


if __name__ == "__main__":
    unittest.main()
