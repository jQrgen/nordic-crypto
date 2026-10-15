import io, json, os, sys, contextlib, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import x_newsletter as xn


class Splitting(unittest.TestCase):
    def test_url_counts_23(self):
        self.assertEqual(xn.x_len("a https://example.com/" + "x" * 200), 2 + 23)

    def test_compose_fits_and_keeps_url(self):
        url = "https://example.com/" + "p" * 150
        txt = xn.compose("Headline " * 10, "A sentence. " * 60, url)
        self.assertLessEqual(xn.x_len(txt), 280)
        self.assertTrue(txt.endswith(url))

    def test_clip_cuts_at_sentence_then_word(self):
        self.assertEqual(xn.clip("One two. Three four five.", 12), "One two.")
        out = xn.clip("alpha beta gamma delta", 14)
        self.assertTrue(out.endswith("…"))
        self.assertTrue(all(w in "alpha beta gamma delta" for w in out[:-1].split()))

    def test_long_headline_clipped(self):
        txt = xn.compose("H" * 400, "", "https://x.example/")
        self.assertLessEqual(xn.x_len(txt), 280)

    def test_parse_stories(self):
        h = ('<p style="m"><a href="https://a.example/1" style="font-weight:bold">T &amp; one</a> (original: x)<br>'
             'Sum one. Two. Three.<br><span>Src</span></p>')
        self.assertEqual(xn.parse_stories(h), [{"title": "T & one", "summary": "Sum one. Two. Three.", "url": "https://a.example/1"}])


class Thread(unittest.TestCase):
    def test_every_published_issue_fits(self):
        for meta in json.load(open(os.path.join(xn.PUBLISHED, "issues.json")))["issues"]:
            m = xn.load_issue(meta["id"])
            posts = xn.build_thread(m)
            self.assertEqual(len(posts), len(m["stories_list"]) + 2)
            self.assertIn(xn.issue_url(m), posts[0])
            self.assertTrue(posts[0].startswith(f"Nordic Crypto #{m['number']}"))
            for p in posts:
                self.assertLessEqual(xn.x_len(p), 280)
                self.assertNotIn("Crypto Nordic", p)
                self.assertNotIn("made with ai", p.lower())

    def test_dry_run_prints_and_never_posts(self):
        state = os.path.join(os.environ.get("TMPDIR", "/tmp"), "x_posted_test.json")
        if os.path.exists(state): os.remove(state)
        xn.create_post = xn.upload_video = lambda *a, **k: self.fail("dry run must not call X")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(xn.main(["--issue", "2", "--dry-run", "--state", state]), 0)
        out = buf.getvalue()
        self.assertIn("# Issue 002", out)
        self.assertIn("[+ video.mp4]", out)
        self.assertFalse(os.path.exists(state))

    def test_missing_secrets_skip(self):
        state = os.path.join(os.environ.get("TMPDIR", "/tmp"), "x_posted_test2.json")
        for k in xn.ENV: os.environ.pop(k, None)
        xn.create_post = lambda *a, **k: self.fail("must not post")
        self.assertEqual(xn.main(["--issue", "002", "--state", state]), 0)
        self.assertFalse(os.path.exists(state))

    def test_already_posted_is_skipped(self):
        state = os.path.join(os.environ.get("TMPDIR", "/tmp"), "x_posted_test3.json")
        xn.save_state(state, {"002": {"complete": True, "tweet_ids": ["1"]}})
        for k in xn.ENV: os.environ[k] = "x"
        xn.create_post = xn.is_live = lambda *a, **k: self.fail("must not touch X")
        try:
            self.assertEqual(xn.main(["--issue", "002", "--state", state]), 0)
        finally:
            for k in xn.ENV: os.environ.pop(k, None)



class LongPost(unittest.TestCase):
    H = ('<p>Hi there.</p><h2>Norway</h2><p style="m"><a href="https://a.example/1" style="font-weight:bold">T &amp; one</a>'
         ' (original: x)<br>Sum one.<br><span>Src · <a href="__SITE__/#country=NO">more</a></span></p>')
    META = {"id": "009", "number": 9, "title": "Nordic Crypto #9: Big week"}

    def test_issue_text(self):
        t = xn.issue_text(self.H)
        self.assertIn("NORWAY", t)
        self.assertIn("T & one\nhttps://a.example/1 (original: x)\nSum one.", t)
        self.assertIn("more (https://nordiccrypto.no/#country=NO)", t)

    def test_long_post_shape(self):
        p = xn.build_long_post(self.META, self.H)
        self.assertTrue(p.startswith("Nordic Crypto #9: Big week\n\nHi there."))
        self.assertTrue(p.endswith("https://nordiccrypto.no/newsletter/009/"))

    def test_long_post_clipped(self):
        p = xn.build_long_post(self.META, "<p>" + "word " * 3000 + "</p>" * 1 + ("<p>" + "x" * 4000 + "</p>") * 10)
        self.assertLessEqual(xn.x_len(p), xn.LONG_LIMIT)

    def test_length_error(self):
        self.assertTrue(xn.is_length_error(RuntimeError("X API POST /2/tweets -> 403: Your Tweet text is too long.")))
        self.assertFalse(xn.is_length_error(RuntimeError("X API POST /2/tweets -> 402: credits depleted")))

if __name__ == "__main__":
    unittest.main()
