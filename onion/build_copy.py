#!/usr/bin/env python3
"""Write onion/app/copy.json from i18n. English is the fallback for languages without their own strings.
Run from the repo root: python3 onion/build_copy.py
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import i18n

KEYS = [
    "tip_title", "tip_lead", "tip_intro", "tip_privacy_h", "tip_privacy",
    "tip_label", "tip_required", "tip_hint", "tip_links", "tip_links_opt",
    "tip_contact", "tip_contact_opt", "tip_honeypot", "tip_send", "tip_thanks",
    "tip_fail", "tip_offline", "tip_rate", "tip_long", "tip_empty", "tip_bad_link",
    "tip_onion_page", "tip_onion_queued", "tip_lang", "about_title",
]
out = {}
for lang in i18n.ALL_LANGS:
    out[lang] = {k: i18n.t(lang, k) for k in KEYS}
    out[lang]["dir"] = "rtl" if i18n.rtl(lang) else "ltr"
    out[lang]["name"] = i18n.NATIVE[lang]
dest = os.path.join(ROOT, "onion", "app", "copy.json")
os.makedirs(os.path.dirname(dest), exist_ok=True)
with open(dest, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
    f.write("\n")
print(f"wrote {dest} ({len(out)} languages)")
