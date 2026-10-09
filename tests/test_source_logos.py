#!/usr/bin/env python3
"""Source id → outlet logo. No network. python3 tests/test_source_logos.py"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build
import source_logos

def main():
    fails = []
    def check(cond, msg):
        if not cond:
            fails.append(msg)

    check(source_logos.canonical_id("kaupr") == "kaupr", "kaupr id")
    check(source_logos.canonical_id("kaupr-no") == "kaupr", "outlet kaupr-no")
    check(source_logos.canonical_id("fi-se") == "se-fi", "alias fi-se")
    check(source_logos.canonical_id("bofbulletin") == "fi-suomen-pankki", "outlet then alias")
    check(source_logos.canonical_id("digi-krypto") == "digi", "alias digi-krypto")
    check(source_logos.canonical_id("nordic-crypto") is None, "own brand has no generated mark")
    check(source_logos.for_source("no-such-outlet", preview=False) is None, "unknown is text only")
    check(source_logos.for_source("nve", preview=False) is None, "pending hidden on the public site")
    pend = source_logos.for_source("nve", preview=True)
    check(pend and pend["file"].endswith("nve.svg") and pend.get("pending"), "preview shows pending")

    kaup = source_logos.for_source("kaupr", preview=False)
    check(kaup and kaup["file"].endswith("kaupr.webp") and kaup["id"] == "kaupr", "kaupr file")
    fi = source_logos.for_source("fi-se", preview=False)
    check(fi and fi["file"].endswith("se-fi.svg") and fi["id"] == "se-fi", "fi-se file")
    check(source_logos.for_source("nbx-ir", preview=False)["id"] == "nbx", "nbx-ir uses the NBX logo")

    build.LANG = "en"
    build.PREVIEW = False
    html = build.source_mark({"source": "kaupr", "source_name": "Kaupr", "source_logo": kaup})
    check('class="src-logo"' in html and "kaupr.webp" in html and "<b>Kaupr</b>" in html, "mark with logo")
    check('class="src-logo-link"' in html and "kaupr.io" in html, "logo links to the outlet")
    check("text-align:center" not in html and "justify-content:center" not in html, "logo row is not centered")
    plain = build.source_mark({"source": "missing-paper", "source_name": "Missing Paper"})
    check("src-logo" not in plain and "<b>Missing Paper</b>" in plain, "text fallback")
    own = build.source_mark({"source": "nordic-crypto", "source_name": "Nordic Crypto"})
    check("src-logo" not in own and "Nordic Crypto" in own, "own stories stay text")
    rule = re.search(r"\.src\{[^}]+\}", build.CSS)
    check(rule and "inline-flex" in rule.group(0) and "flex-start" in rule.group(0), "css starts at the inline start")
    check(rule and "text-align:center" not in rule.group(0) and "justify-content:center" not in rule.group(0), "css is not a centered layout")
    screen = open(os.path.join(ROOT, "templates", "screen.html"), encoding="utf-8").read()
    check("source_logo" in screen and 'class="src"' in screen, "screen template")

    ids = {j["id"] for j in source_logos.outlets_to_fetch()}
    check("kaupr" not in ids and "se-fi" not in ids, "checked logos are not refetched")
    check(not any(i.startswith("bing-") for i in ids), "bing search is not an outlet")
    check(source_logos.canonical_id("sydsvenskan.se") == "sydsvenskan.se", "one-off source id")
    if source_logos.for_source("sydsvenskan.se", preview=True) is None:
        check("sydsvenskan.se" in ids, "one-off outlet queued for fetch")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("source logos ok")

if __name__ == "__main__":
    main()
