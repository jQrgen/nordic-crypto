#!/usr/bin/env python3
"""python3 tipworker/tests/test_export.py – export_subscribers.py: only confirmed rows of the chosen site, deduped,
mode 600, no addresses on stdout."""
import csv, io, json, os, stat, sys, tempfile, contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import export_subscribers as X
rows = [{"email": "a@example.org", "site": "kryptonytt", "lang": "nn", "status": "confirmed", "confirmed_at": "2026-10-01T10:00:00+00:00"},
        {"email": "A@example.org", "site": "kryptonytt", "lang": "nb", "status": "confirmed", "confirmed_at": "2026-10-02T10:00:00+00:00"},
        {"email": "p@example.org", "site": "kryptonytt", "lang": "nn", "status": "pending"},
        {"email": "u@example.org", "site": "kryptonytt", "lang": "nn", "status": "unsubscribed"},
        {"email": "n@example.org", "site": "nordic-crypto", "lang": "sv", "status": "confirmed", "confirmed_at": "2026-10-03T10:00:00+00:00"},
        {"email": "b@example.org", "site": "kryptonytt", "lang": "en", "status": "confirmed", "confirmed_at": "2026-10-03T09:00:00+00:00"}]
d = tempfile.mkdtemp(); src = os.path.join(d, "rows.json"); json.dump(rows, open(src, "w")); fails = 0
def ok(c, m):
    global fails; print(("PASS  " if c else "FAIL  ") + m); fails += (not c)
buf = io.StringIO()
with contextlib.redirect_stdout(buf): p = X.main(["--site", "kryptonytt", "--from-json", src, "--out", os.path.join(d, "k.csv")])
got = list(csv.DictReader(open(p)))
ok([r["email"] for r in got] == ["a@example.org", "b@example.org"], "only confirmed kryptonytt rows, deduped, oldest first")
ok(list(got[0]) == ["email", "lang", "confirmed_at"], "header starts with email (Substack import)")
ok(stat.S_IMODE(os.stat(p).st_mode) == 0o600, "file mode 600")
ok("@" not in buf.getvalue().replace(p, ""), "no addresses printed")
with contextlib.redirect_stdout(io.StringIO()): p = X.main(["--site", "kryptonytt", "--lang", "en", "--from-json", src, "--out", os.path.join(d, "e.csv")])
ok([r["email"] for r in csv.DictReader(open(p))] == ["b@example.org"], "--lang filter")
with contextlib.redirect_stdout(io.StringIO()): p = X.main(["--site", "nordic-crypto", "--from-json", src, "--out", os.path.join(d, "n.csv")])
ok([r["email"] for r in csv.DictReader(open(p))] == ["n@example.org"], "other site separate")
print(f"---- export: {6 - fails} passed, {fails} failed"); sys.exit(1 if fails else 0)
