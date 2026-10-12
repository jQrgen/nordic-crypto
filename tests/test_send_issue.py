#!/usr/bin/env python3
"""newsletter/send_issue.py: confirmed rows only, unsubscribe HMAC, left-aligned mail, no addresses on stdout.

  python3 -m unittest tests.test_send_issue

The skip ledger is redirected into a tempdir: ROOT/state/newsletter/sent-issue-001.json
is the real record of who already got issue 001, and the test must never touch it.
"""
import contextlib, hashlib, hmac, io, json, os, re, shutil, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "newsletter"))
import send_issue as S

STATE = os.path.join(ROOT, "state", "newsletter")
SECRET = "test-unsub-secret"
ENV = {"MAIL_SEND_ENABLED": "1", "UNSUB_SECRET": SECRET, "NEWSLETTER_WORKER_ORIGIN": "https://worker.test",
       "MAIL_FROM_NORDIC_CRYPTO": "Nordic Crypto <FROM-ADDRESS>", "MAIL_PROVIDER": "resend"}


def snapshot():
    """Whether the real ledger dir exists, and each file's (mtime_ns, size, bytes)."""
    if not os.path.isdir(STATE):
        return False, {}
    files = {}
    for name in sorted(os.listdir(STATE)):
        p = os.path.join(STATE, name)
        st = os.stat(p)
        files[name] = (st.st_mtime_ns, st.st_size, open(p, "rb").read() if os.path.isfile(p) else None)
    return True, files


class SendIssue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        orig = S.ledger_path
        self.addCleanup(setattr, S, "ledger_path", orig)

        def ledger_path(key):
            safe = re.sub(r"[^A-Za-z0-9._-]", "-", key)[:80]
            return os.path.join(self.tmp, "state", "newsletter", f"sent-{safe}.json")
        S.ledger_path = ledger_path
        self.led = S.ledger_path("issue-001")

        self.src = os.path.join(self.tmp, "rows.json")
        with open(self.src, "w") as f:
            json.dump([
                {"id": 9, "email": "one@example.org", "site": "nordic-crypto", "lang": "en", "status": "confirmed"},
                {"id": 8, "email": "two@example.org", "site": "nordic-crypto", "lang": "nb", "status": "confirmed"},
                {"id": 7, "email": "nope@example.org", "site": "nordic-crypto", "lang": "en", "status": "pending"},
            ], f)
        self.box = []

    def fake(self, env, msg):
        self.box.append(msg)
        return True, ""

    def run_main(self, *extra, env=ENV):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = S.main(["--issue", "001", "--from-json", self.src, *extra], sender=self.fake, env=env)
        return rc, buf.getvalue()

    def test_unsubscribe_hmac(self):
        msg = "7|a@example.org|nordic-crypto"
        want = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()[:40]
        self.assertEqual(S.unsub_sig(SECRET, 7, "a@example.org"), want, "unsubscribe HMAC matches the Worker (first 40 hex chars)")
        self.assertEqual(len(S.unsub_sig(SECRET, 7, "a@example.org")), 40, "sig length 40")

    def test_confirmed_rows(self):
        rows = [
            {"id": 1, "email": "A@example.org", "site": "nordic-crypto", "lang": "nb", "status": "confirmed"},
            {"id": 2, "email": "a@example.org", "site": "nordic-crypto", "lang": "en", "status": "confirmed"},
            {"id": 3, "email": "p@example.org", "site": "nordic-crypto", "lang": "en", "status": "pending"},
            {"id": 4, "email": "u@example.org", "site": "nordic-crypto", "lang": "en", "status": "unsubscribed"},
            {"id": 5, "email": "k@example.org", "site": "kryptonytt", "lang": "nn", "status": "confirmed"},
        ]
        self.assertEqual([r["email"] for r in S.confirmed_rows(rows)], ["a@example.org"], "confirmed nordic-crypto only, deduped, lower-cased")
        self.assertEqual([r["lang"] for r in S.confirmed_rows(rows, lang="nb")], ["nb"], "lang filter keeps the bokmål row")

    def test_compose(self):
        html_body, text = S.compose("<p>Hei</p>", "nb", "https://nordiccrypto.no/nb/newsletter/001/", "https://worker.test/unsub", "Emne")
        self.assertTrue("margin:0 auto" not in html_body and "text-align:left" in html_body, "mail is left-aligned")
        self.assertEqual(html_body.count("The Nordic Crypto team"), 1, "sign-off once")
        self.assertTrue("https://nordiccrypto.no/nb/newsletter/001/" in html_body and "https://worker.test/unsub" in html_body, "issue link and unsubscribe link")
        self.assertNotIn("Kaupr", html_body, "no Kaupr sponsor line added")
        self.assertTrue("Meld deg av" in html_body and "kunstig intelligens" not in html_body and "AI" not in text, "Norwegian wrapper has no AI")
        html2, _ = S.compose("<p>Until next week,<br>The Nordic Crypto team</p>", "en", "https://nordiccrypto.no/newsletter/001/", "https://worker.test/u", "Issue")
        self.assertEqual(html2.count("The Nordic Crypto team"), 1, "existing sign-off is not repeated")

    def test_send_and_ledger(self):
        # One sequence: the second run and the dry run rely on the ledger and box from the first send.
        rc, out = self.run_main("--sleep", "0")
        box = self.box
        self.assertTrue(rc == 0 and len(box) == 2, "sends one mail per confirmed address")
        self.assertNotIn("@", out, "stdout has no addresses")
        self.assertTrue(all("List-Unsubscribe" not in (m.get("html") or "") for m in box), "header is separate from the body check")
        self.assertTrue(all(m["unsubscribe"].startswith("https://worker.test/api/unsubscribe?") for m in box), "unsubscribe URL on the Worker")
        self.assertTrue(all("nordiccrypto.no" in m["html"] for m in box), "each mail links to the site")
        self.assertTrue(any("The Nordic Crypto team" in m["html"] for m in box), "English issue keeps The Nordic Crypto team")
        self.assertTrue(any("Nordic Crypto-teamet" in m["html"] for m in box), "bokmål issue keeps its own sign-off")
        nb = [m for m in box if "nb/newsletter/001/" in m["html"]]
        self.assertTrue(len(nb) == 1 and "Meld deg av" in nb[0]["html"], "bokmål subscriber gets the bokmål issue link and unsubscribe label")

        rc, out = self.run_main("--sleep", "0")
        self.assertTrue(rc == 0 and len(box) == 2 and "skipped 2" in out, "second run skips ids already recorded")
        self.assertTrue(os.path.exists(self.led) and oct(os.stat(self.led).st_mode & 0o777) == "0o600", "ledger is mode 600 and stores ids, not shown here")
        raw = open(self.led, encoding="utf-8").read()
        self.assertTrue("example.org" not in raw and "9" in raw, "ledger keeps ids only")
        os.remove(self.led)

        rc, out = self.run_main("--dry-run")
        self.assertTrue(rc == 0 and len(box) == 2 and out.startswith("send: dry-run"), "dry-run sends nothing")

    def test_refuses_without_secret(self):
        with self.assertRaises(SystemExit) as e:
            self.run_main("--sleep", "0", env={"MAIL_SEND_ENABLED": "1"})
        self.assertTrue("MAIL_FROM" in str(e.exception) or "UNSUB_SECRET" in str(e.exception), "refuses to send without from-address and unsubscribe secret")

    def test_real_ledger_untouched(self):
        # Runs the send flow itself, so it proves something whatever order the methods run in.
        before = snapshot()
        self.run_main("--sleep", "0")
        self.run_main("--sleep", "0")
        self.run_main("--dry-run")
        self.assertEqual(len(self.box), 2)
        self.assertTrue(os.path.exists(self.led), "the send wrote to the tempdir ledger")
        self.assertEqual(snapshot(), before, "ROOT/state/newsletter is unchanged (and not created)")


if __name__ == "__main__":
    unittest.main()
