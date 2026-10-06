#!/usr/bin/env python3
"""The public signup form is ours: consent checkbox, Worker action, no third-party embed."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["NC_NEWSLETTER"] = "1"
os.environ["NEWSLETTER_ENDPOINT"] = "http://127.0.0.1:8789"
import build
import i18n

fails = 0
def ok(c, m):
    global fails
    print(("PASS  " if c else "FAIL  ") + m)
    fails += (not c)

build.LANG = "nb"
form = build.newsletter_form()
ok('action="http://127.0.0.1:8789/api/subscribe"' in form, "form posts to the Worker")
ok('name="consent"' in form and "required" in form, "consent checkbox is required")
ok("substack" not in form.lower() and "iframe" not in form.lower(), "form has no third-party embed")
ok("samtykker" in form, "bokmål consent text")
hdr = build.header_subscribe_button("../")
ok('href="../newsletter/#signup"' in hdr and "substack" not in hdr.lower(), "header subscribe link stays on this site")
for lang in ("en", "nn", "nb", "sv", "da", "fi", "is"):
    for key in ("nl_priv", "nl_consent", "nl_soon", "nl_btn"):
        s = i18n.t(lang, key)
        ok("substack" not in s.lower() and "substack.com" not in s.lower(), f"{lang} {key} has no third-party signup")
    if lang in ("nn", "nb"):
        ok("AI" not in i18n.t(lang, "nl_priv") and "KI" not in i18n.t(lang, "nl_priv"), f"{lang} privacy text avoids AI/KI")
print(f"---- newsletter form: {fails} failed")
sys.exit(1 if fails else 0)
