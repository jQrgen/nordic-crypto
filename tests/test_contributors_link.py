#!/usr/bin/env python3
"""Footer link to the contributors page on GitHub (https://github.com/jQrgen/nordic-crypto/graphs/contributors).
  python3 tests/test_contributors_link.py
One link, label from i18n ("contributors") in every site language, no list of names on the site.
Renders the Books page into a temp directory to check the real footer. Does not publish."""
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build
import i18n

URL = "https://github.com/jQrgen/nordic-crypto/graphs/contributors"
REVERSED = "Crypto " + "Nordic"


def check(ok, msg, fails):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    fails = []
    check(build.REPO_CONTRIBUTORS == URL, "contributors URL", fails)
    labels = set()
    for lang in i18n.ALL_LANGS:
        label = i18n.strings(lang).get("contributors")
        check(bool(label) and "<" not in label, f"{lang} has its own label", fails)
        if lang != "en":
            labels.add(label)
        build.LANG = lang
        link = build.contributors_link()
        check(link == f'<a href="{URL}" rel="noopener">{build.E(label or "")}</a>', f"{lang} link markup", fails)
        footer = build.site_footer("", "")   # the link is in the footer's "About the site" column, after Data API
        check(footer.count(URL) == 1, f"{lang} footer has the link once", fails)
        check(footer.index("api/") < footer.index(URL), f"{lang} link sits after Data API", fails)
        check(REVERSED not in footer, f"{lang} brand", fails)
    check("Contributors" not in labels, "other languages are translated", fails)
    old = (build.SITE, build.PREVIEW, build.LANG)
    with tempfile.TemporaryDirectory() as tmp:
        build.SITE = tmp
        build.PREVIEW = False
        try:
            for lang in ("en", "nb", "ar"):
                build.LANG = lang
                build.build_books()
                html = open(os.path.join(tmp, build.lp(), "books", "index.html"), encoding="utf-8").read()
                foot = html[html.index("<footer>"):html.index("</footer>")]
                check(f'href="{URL}"' in foot, f"{lang} rendered footer links to contributors", fails)
                check(not re.search(r"github\.com/(?!jQrgen/nordic-crypto/)[\w-]+\"", foot), f"{lang} no personal profile links", fails)
                check("{contributors}" not in foot, f"{lang} placeholder filled", fails)
        finally:
            build.SITE, build.PREVIEW, build.LANG = old
    if fails:
        print(f"\n{len(fails)} failed")
        sys.exit(1)
    print("\nall ok")


if __name__ == "__main__":
    main()
