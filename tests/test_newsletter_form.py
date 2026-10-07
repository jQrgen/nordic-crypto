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
hdr = build.header_buttons("../")
ok('href="../newsletter/#signup"' in hdr and "substack" not in hdr.lower(), "header subscribe link stays on this site")
ok(hdr.find("newsletter/#signup") < hdr.find("t.me/nordiccryptochat") < hdr.find("x.com/xcryptonordic"), "header order is Subscribe, Telegram, X")
ok('class="hdrtg"' in hdr and "justify-content:flex-end" not in build.CSS, "Telegram uses the outline button and the header stays left-aligned")
ok("header.top,header.top .wrap{text-align:start}" in build.CSS, "header text starts at the left")
ok(".brandrow{display:flex;align-items:center;justify-content:flex-start;" in build.CSS, "brand row starts at the left")
ok(".hdrbtns{display:flex;align-items:center;justify-content:flex-start;" in build.CSS, "header buttons start at the left")
closed = build.newsletter_closed("../")
ok("<form" not in closed and 'type="email"' not in closed, "closed signup has no email field")
ok("rss.xml" in closed and "t.me/nordiccryptochat" in closed and "x.com/xcryptonordic" in closed, "closed signup points at RSS, Telegram and X")
ok("substack" not in closed.lower(), "closed signup has no third-party signup")
for lang in ("en", "nn", "nb", "sv", "da", "fi", "is"):
    build.LANG = lang
    label = i18n.t(lang, "tg_btn")
    btn = build.header_telegram_button()
    ok(label in btn and "t.me/nordiccryptochat" in btn, f"{lang} header Telegram label")
    sub = build.header_subscribe_button("")
    ok(i18n.t(lang, "nl_btn") in sub and "substack" not in sub.lower(), f"{lang} header Subscribe label")
    for key in ("nl_priv", "nl_consent", "nl_soon", "nl_soon_short", "nl_fallback", "nl_btn", "tg_btn"):
        s = i18n.t(lang, key)
        ok("substack" not in s.lower() and "substack.com" not in s.lower(), f"{lang} {key} has no third-party signup")
    if lang in ("nn", "nb"):
        blob = " ".join(i18n.t(lang, k) for k in ("nl_priv", "nl_soon", "nl_soon_short", "nl_fallback", "tg_btn"))
        ok("AI" not in blob and "KI" not in blob, f"{lang} new newsletter text avoids AI/KI")
print(f"---- newsletter form: {fails} failed")
sys.exit(1 if fails else 0)
