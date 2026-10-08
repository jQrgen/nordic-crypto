#!/usr/bin/env python3
"""The public name is Nordic Crypto. Domains and handles that contain the old
spelling without a space stay as they are. No network."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import site_url
import api_feed

fails = []
# Built from parts so this file does not contain the reversed name.
REVERSED = "Crypto" + " Nordic"
REVERSED_FI = REVERSED + "in"
CAMEL = "Crypto" + "Nordic"
SPACED = re.compile("crypto" + r"\s+" + "nordic", re.IGNORECASE)
CAMEL_RE = re.compile(CAMEL)
MEETUP = "a1ea7afabcb0"
SKIP_DIRS = {".git", "node_modules", ".venv", "site", ".publish", "__pycache__"}


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    check(site_url.brand("publisher of " + REVERSED + ".") == "publisher of Nordic Crypto.", "english prose")
    check(site_url.brand("on " + REVERSED_FI + " julkaisija.") == "on Nordic Crypton julkaisija.", "finnish genitive")
    check(site_url.brand(CAMEL + "/0.1") == "NordicCrypto/0.1", "camel-case token")
    check(site_url.brand(REVERSED + " redaktør") == "Nordic Crypto redaktør", "editor byline")
    approvals = open(os.path.join(ROOT, "tools", "apply_approvals.py"), encoding="utf-8").read()
    check('or "Nordic Crypto redaktør"' in approvals, "default byline is Nordic Crypto redaktør")
    for keep in (
        "https://cryptonordic.no/about/",
        "@xcryptonordic",
        "https://x.com/xcryptonordic",
        "https://cryptonordic.substack.com",
        "github.com/jQrgen/nordic-crypto",
        "https://t.me/nordiccryptochat",
    ):
        check(site_url.brand(keep) == keep, "kept " + keep)

    event = {"note": "publisher of " + REVERSED, "note_i18n": {"fi": REVERSED_FI, "en": "Nordic Crypto"}}
    site_url.brand_note(event)
    check(event["note"] == "publisher of Nordic Crypto", "note field")
    check(event["note_i18n"]["fi"] == "Nordic Crypton", "note translation")
    check(event["note_i18n"]["en"] == "Nordic Crypto", "already correct translation")

    hits = []
    # Only files git would commit: gitignored local state (logs/, queue/) is not the repo.
    import subprocess
    try:
        ignored = set(subprocess.run(["git", "-C", ROOT, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
                                     capture_output=True, text=True, check=True).stdout.split("\0"))
    except (OSError, subprocess.CalledProcessError):
        ignored = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.relpath(path, ROOT) in ignored:
                continue
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            if SPACED.search(text) or CAMEL_RE.search(text):
                hits.append(os.path.relpath(path, ROOT))
    check(hits == [], "no reversed brand in the repo" + (": " + ", ".join(hits) if hits else ""))

    wordmark = open(os.path.join(ROOT, "newsletter", "make_brand_assets.py"), encoding="utf-8").read()
    check("Nordic&nbsp;" in wordmark and "Crypto&nbsp;" not in wordmark, "newsletter wordmark order")

    evs = [e for e in api_feed.public_events(False) if e.get("id") == MEETUP]
    check(len(evs) == 1, "Oslo Blockchain Meetup is on the public calendar")
    if evs:
        note = evs[0].get("note") or ""
        i18n = evs[0].get("note_i18n") or {}
        check("Nordic Crypto" in note and REVERSED not in note, "meetup disclosure")
        expect = {
            "nn": "Nordic Crypto",
            "nb": "Nordic Crypto",
            "sv": "Nordic Crypto",
            "da": "Nordic Crypto",
            "fi": "Nordic Crypton",
            "is": "Nordic Crypto",
        }
        for lang, needle in expect.items():
            text = i18n.get(lang) or ""
            check(needle in text and REVERSED not in text, f"meetup note {lang}")

    if fails:
        print(f"\n{len(fails)} failed")
        sys.exit(1)
    print("all brand checks passed")


if __name__ == "__main__":
    main()
