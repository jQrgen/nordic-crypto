#!/usr/bin/env python3
"""newsletter/send_issue.py: confirmed rows only, unsubscribe HMAC, left-aligned mail, no addresses on stdout."""
import hashlib, hmac, io, json, os, sys, tempfile, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "newsletter"))
import send_issue as S

fails = 0
def ok(c, m):
    global fails
    print(("PASS  " if c else "FAIL  ") + m)
    fails += (not c)

secret = "test-unsub-secret"
msg = "7|a@example.org|nordic-crypto"
want = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:40]
ok(S.unsub_sig(secret, 7, "a@example.org") == want, "unsubscribe HMAC matches the Worker (first 40 hex chars)")
ok(len(S.unsub_sig(secret, 7, "a@example.org")) == 40, "sig length 40")

rows = [
    {"id": 1, "email": "A@example.org", "site": "nordic-crypto", "lang": "nb", "status": "confirmed"},
    {"id": 2, "email": "a@example.org", "site": "nordic-crypto", "lang": "en", "status": "confirmed"},
    {"id": 3, "email": "p@example.org", "site": "nordic-crypto", "lang": "en", "status": "pending"},
    {"id": 4, "email": "u@example.org", "site": "nordic-crypto", "lang": "en", "status": "unsubscribed"},
    {"id": 5, "email": "k@example.org", "site": "kryptonytt", "lang": "nn", "status": "confirmed"},
]
got = S.confirmed_rows(rows)
ok([r["email"] for r in got] == ["a@example.org"], "confirmed nordic-crypto only, deduped, lower-cased")
ok([r["lang"] for r in S.confirmed_rows(rows, lang="nb")] == ["nb"], "lang filter keeps the bokmål row")

html_body, text = S.compose("<p>Hei</p>", "nb", "https://nordiccrypto.no/nb/newsletter/001/", "https://worker.test/unsub", "Emne")
ok("margin:0 auto" not in html_body and "text-align:left" in html_body, "mail is left-aligned")
ok(html_body.count("The Nordic Crypto team") == 1, "sign-off once")
ok("https://nordiccrypto.no/nb/newsletter/001/" in html_body and "https://worker.test/unsub" in html_body, "issue link and unsubscribe link")
ok("Kaupr" not in html_body, "no Kaupr sponsor line added")
ok("Meld deg av" in html_body and "kunstig intelligens" not in html_body and "AI" not in text, "Norwegian wrapper has no AI")
html2, _ = S.compose("<p>Until next week,<br>The Nordic Crypto team</p>", "en", "https://nordiccrypto.no/newsletter/001/", "https://worker.test/u", "Issue")
ok(html2.count("The Nordic Crypto team") == 1, "existing sign-off is not repeated")

d = tempfile.mkdtemp()
src = os.path.join(d, "rows.json")
json.dump([
    {"id": 9, "email": "one@example.org", "site": "nordic-crypto", "lang": "en", "status": "confirmed"},
    {"id": 8, "email": "two@example.org", "site": "nordic-crypto", "lang": "nb", "status": "confirmed"},
    {"id": 7, "email": "nope@example.org", "site": "nordic-crypto", "lang": "en", "status": "pending"},
], open(src, "w"))
box = []
def fake(env, msg):
    box.append(msg)
    return True, ""
env = {"MAIL_SEND_ENABLED": "1", "UNSUB_SECRET": secret, "NEWSLETTER_WORKER_ORIGIN": "https://worker.test",
       "MAIL_FROM_NORDIC_CRYPTO": "Nordic Crypto <FROM-ADDRESS>", "MAIL_PROVIDER": "resend"}
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = S.main(["--issue", "001", "--from-json", src, "--sleep", "0"], sender=fake, env=env)
ok(rc == 0 and len(box) == 2, "sends one mail per confirmed address")
ok("@" not in buf.getvalue(), "stdout has no addresses")
ok(all("List-Unsubscribe" not in (m.get("html") or "") for m in box), "header is separate from the body check")
ok(all(m["unsubscribe"].startswith("https://worker.test/api/unsubscribe?") for m in box), "unsubscribe URL on the Worker")
ok(all("nordiccrypto.no" in m["html"] for m in box), "each mail links to the site")
ok(any("The Nordic Crypto team" in m["html"] for m in box), "English issue keeps The Nordic Crypto team")
ok(any("Nordic Crypto-teamet" in m["html"] for m in box), "bokmål issue keeps its own sign-off")
nb = [m for m in box if "nb/newsletter/001/" in m["html"]]
ok(len(nb) == 1 and "Meld deg av" in nb[0]["html"], "bokmål subscriber gets the bokmål issue link and unsubscribe label")
buf2 = io.StringIO()
with contextlib.redirect_stdout(buf2):
    rc = S.main(["--issue", "001", "--from-json", src, "--sleep", "0"], sender=fake, env=env)
ok(rc == 0 and len(box) == 2 and "skipped 2" in buf2.getvalue(), "second run skips ids already recorded")
led = os.path.join(ROOT, "state", "newsletter", "sent-issue-001.json")
ok(os.path.exists(led) and oct(os.stat(led).st_mode & 0o777) == "0o600", "ledger is mode 600 and stores ids, not shown here")
raw = open(led, encoding="utf-8").read()
ok("example.org" not in raw and "9" in raw, "ledger keeps ids only")
os.remove(led)

buf3 = io.StringIO()
with contextlib.redirect_stdout(buf3):
    rc = S.main(["--issue", "001", "--from-json", src, "--dry-run"], sender=fake, env=env)
ok(rc == 0 and len(box) == 2 and buf3.getvalue().startswith("send: dry-run"), "dry-run sends nothing")
try:
    S.main(["--issue", "001", "--from-json", src, "--sleep", "0"], sender=fake, env={"MAIL_SEND_ENABLED": "1"})
    ok(False, "refuses to send without from-address and unsubscribe secret")
except SystemExit as e:
    ok("MAIL_FROM" in str(e) or "UNSUB_SECRET" in str(e), "refuses to send without from-address and unsubscribe secret")

print(f"---- send_issue: {fails} failed")
sys.exit(1 if fails else 0)
