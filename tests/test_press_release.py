#!/usr/bin/env python3
"""tools/press_release.py: review-first, one recipient per email, unsubscribe, suppression, idempotent ledger, brand rules.

  python3 -m unittest tests.test_press_release
No network: the sender is a fake. The ledger and output live in a tempdir.
"""
import csv, os, re, shutil, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
import press_release as P

ENV = {"RESEND_API_KEY": "re_test", "PRESS_UNSUB_ORIGIN": "https://worker.test", "PRESS_UNSUB_SECRET": "s3cret"}
C = [{"name": "A", "outlet": "X", "country": "NO", "email": "a@x.no", "language": "no", "source_url": "https://x.no/kontakt"},
     {"name": "B", "outlet": "Y", "country": "SE", "email": "b@y.se", "language": "sv", "source_url": "https://y.se/kontakt"},
     {"name": "C", "outlet": "Z", "country": "FI", "email": "c@z.fi", "language": "en", "source_url": "https://z.fi/"}]


class Press(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ledger = os.path.join(self.tmp, "sent.json"); self.out = os.path.join(self.tmp, "out"); self.calls = []

    def fake(self, key, msg):
        self.calls.append(msg); return True, ""

    def go(self, **kw):
        return P.run("002", self.out, env=kw.pop("env", ENV), sender=self.fake, sleep_s=0, contacts=kw.pop("contacts", C),
                     suppressed=kw.pop("suppressed", set()), ledger=self.ledger, **kw)

    def test_default_is_drafts_only(self):
        s = self.go()
        self.assertEqual(self.calls, []); self.assertEqual(s["sent"], 0); self.assertIn("drafts only", s["mode"])
        for lang in ("no", "sv", "en"):
            self.assertTrue(os.path.exists(os.path.join(self.out, f"press-002-{lang}.txt")))

    def test_missing_key_skips(self):
        s = self.go(send=True, env={})
        self.assertEqual(self.calls, []); self.assertIn("RESEND_API_KEY missing", s["mode"])

    def test_send_needs_unsub(self):
        with self.assertRaises(SystemExit): self.go(send=True, env={"RESEND_API_KEY": "k"})

    def test_individual_unsub_and_idempotent(self):
        s = self.go(send=True)
        self.assertEqual(s["sent"], 3)
        for m in self.calls:
            self.assertIsInstance(m["to"], str); self.assertNotIn(",", m["to"])
            self.assertTrue(m["unsubscribe"].startswith("https://worker.test/api/press-unsubscribe?"))
            self.assertIn(m["unsubscribe"], m["text"]); self.assertIn(m["unsubscribe"].replace("&", "&amp;"), m["html"])
            self.assertEqual(m["from"], "Nordic Crypto <jqrgen@nordiccrypto.no>")
        self.calls.clear()
        s = self.go(send=True)
        self.assertEqual(self.calls, []); self.assertEqual(s["already_sent"], 3)

    def test_suppressed_never_sent(self):
        s = self.go(send=True, suppressed={P.email_hash("B@Y.se ")})
        self.assertEqual(s["suppressed"], 1); self.assertNotIn("b@y.se", [m["to"] for m in self.calls])

    def test_suppression_file(self):
        p = os.path.join(self.tmp, "supp.csv")
        self.assertTrue(P.add_suppression("Q@x.no", "asked", p)); self.assertFalse(P.add_suppression("q@x.no", "asked", p))
        self.assertIn(P.email_hash("q@x.no"), P.load_suppressed(p))

    def test_payload_headers(self):
        seen = {}
        class R:
            status = 200
            def __enter__(s): return s
            def __exit__(s, *a): return False
        def fake_open(req, timeout=0):
            import json; seen["p"] = json.loads(req.data); seen["h"] = dict(req.header_items()); return R()
        orig = P.urllib.request.urlopen; P.urllib.request.urlopen = fake_open
        try:
            ok, _ = P.resend_send("k", {"from": "f", "to": "a@x.no", "subject": "s", "text": "t", "html": "h", "unsubscribe": "https://u", "idempotency_key": "i"})
        finally: P.urllib.request.urlopen = orig
        self.assertTrue(ok); p = seen["p"]
        self.assertEqual(p["to"], ["a@x.no"]); self.assertNotIn("cc", p); self.assertNotIn("bcc", p)
        self.assertIn("<https://u>", p["headers"]["List-Unsubscribe"])
        self.assertEqual(p["headers"]["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_content_and_brand(self):
        for lang in P.LANGS:
            r = P.release("002", lang)
            self.assertTrue(3 <= len(r["stories"]) <= 5)
            self.assertIn("jqrgen@nordiccrypto.no", r["text"]); self.assertIn(r["issue_url"], r["text"]); self.assertIn("youtube.com", r["text"])
            self.assertIn("Nordic Crypto", r["text"]); self.assertEqual(P.brand_errors(r["subject"], r["text"]), [])
            self.assertNotRegex(r["text"], r"[«»“”\"]")  # quote-free
        rev = "Crypto" + " Nordic"
        self.assertTrue(P.brand_errors(rev + " #2", "x")); self.assertTrue(P.brand_errors("s", "Made with AI\nhello"))
        self.assertTrue(P.brand_errors("s", "Kaupr is our sponsor"))

    def test_contacts_csv(self):
        rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "press", "contacts.csv"), encoding="utf-8")))
        self.assertEqual(list(rows[0].keys()), ["name", "outlet", "country", "role/beat", "email", "source_url", "verified_date", "language"])
        emails = [r["email"].lower() for r in rows]
        self.assertEqual(len(emails), len(set(emails)))
        for r in rows:
            self.assertTrue(r["source_url"].startswith("https://"), r["email"])
            self.assertIn(r["country"], {"NO", "SE", "DK", "FI", "IS"}); self.assertIn(r["language"], P.LANGS)
            self.assertRegex(r["verified_date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertRegex(r["email"], r"^[^@\s]+@[^@\s]+\.[a-z]+$")


if __name__ == "__main__":
    unittest.main()
