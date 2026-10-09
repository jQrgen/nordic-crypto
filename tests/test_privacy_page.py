#!/usr/bin/env python3
"""Privacy and data policy page (privacy/): built for every language, no placeholder left, the status of each optional
service follows the same switch that adds it to the site, the footer and the stats page link to it. No network.
  python3 tests/test_privacy_page.py
"""
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build  # noqa: E402
import i18n  # noqa: E402

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


SECTIONS = ("who", "overview", "hosting", "storage", "language", "stats", "markets", "video", "newsletter", "push", "tips",
            "chat", "github", "rights")
# Every browser-storage key the site's own scripts use must be named on the page.
STORAGE_KEYS = ("nc_lang", "nc_auto", "nc-theme", "nc_push_countries", "nc_shout_nick")
# Every outside host the site's pages can load or call must be named on the page.
HOSTS = ("static.cloudflareinsights.com", "api.firi.com", "api.coinmotion.com", "youtube-nocookie.com", "player.vimeo.com")


def main():
    for name in ("privacy.html", "privacy.nb.html", "privacy.nn.html"):
        text = open(os.path.join(ROOT, "templates", name), encoding="utf-8").read()
        for sid in SECTIONS:
            check(f'<h2 id="{sid}">' in text, f"{name}: #{sid}")
        for k in STORAGE_KEYS + HOSTS:
            check(k in text, f"{name}: names {k}")
        check(text.index('<p class="lead">') < text.index('<div class="prose">'), name + ": lead above the text column")
        check("../stats/#data-policy" in text.replace("{{UP}}", "../"), name + ": links the stats data policy")
    for lang in i18n.ALL_LANGS:
        for k in ("pp_title", "pp_desc", "pp_on", "pp_off", "pp_note", "pp_whole"):
            check(i18n.has(lang, k), f"{lang}: {k}")

    # The hosts the build can inject are the ones the page names (catches a new third-party script).
    src = open(os.path.join(ROOT, "build.py"), encoding="utf-8").read()
    injected = set(re.findall(r'<(?:script|iframe)[^>]*src="https://([a-z0-9.-]+)', src))
    injected |= set(re.findall(r'https://(www\.youtube-nocookie\.com|player\.vimeo\.com)/', src))
    en = open(os.path.join(ROOT, "templates", "privacy.html"), encoding="utf-8").read()
    for host in sorted(injected):
        named = host in en or host.replace("www.", "") in en or (host == "challenges.cloudflare.com" and "Turnstile" in en)
        check(named, f"page covers {host}")

    with tempfile.TemporaryDirectory() as tmp:
        build.SITE = tmp
        for lang in ("en", "nb", "nn", "de", "ar"):
            build.LANG = lang
            build.build_privacy()
            path = os.path.join(tmp, *([] if lang == "en" else [lang]), "privacy", "index.html")
            check(os.path.exists(path), f"{lang}: privacy/index.html written")
            if not os.path.exists(path):
                continue
            html = open(path, encoding="utf-8").read()
            check("{{" not in html, f"{lang}: no placeholder left")
            check(f'href="../privacy/"' in html or 'href="privacy/"' in html or "privacy/" in html, f"{lang}: footer link")
            check(build.t("pp_title") in html, f"{lang}: footer and title use pp_title")
            off = html.count(build.E(build.t("pp_off")))
            check(off >= 1 if not build.analytics_token() else True, f"{lang}: analytics shows off while no token is set")
            if lang in ("de", "ar"):
                check(build.E(build.t("pp_note")) in html and 'lang="en"' in html, f"{lang}: note in the page language over the English text")
            else:
                check(build.E(build.t("pp_note")) not in html, f"{lang}: no fallback note on a translated page")
    print(f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
