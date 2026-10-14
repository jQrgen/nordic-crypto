#!/usr/bin/env python3
"""The GitHub source-code line belongs at the bottom of the site footer, in every language.
It is not part of a page body (event, story, newsletter or any other page). No network."""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build
import i18n

REPO = "https://github.com/nordic-crypto-org/nordic-crypto"
PATH_TEXT = "github.com/nordic-crypto-org/nordic-crypto"
fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def line_for(lang):
    label = i18n.t(lang, "foot_source")
    return (f'<p class="footsource"><span class="footsource-label">{build.E(label)}:</span> '
            f'<a href="{REPO}" rel="noopener"><bdi dir="ltr">{PATH_TEXT}</bdi></a></p>')


def main():
    for lang in ("en", "nb", "sv", "ar"):
        raw = subprocess.check_output(
            ["node", os.path.join(ROOT, "tools", "snippets.js"), "https://nordiccrypto.no/calendar/x/", "Title", lang],
            text=True)
        top = json.loads(raw)["top"]
        check("social-source" not in top and PATH_TEXT not in top, f"{lang} share snippet has no source line")
        check('class="share"' in top and "Share:" in top, f"{lang} share snippet still has the share bar")

    for lang in i18n.ALL_LANGS:
        label = i18n.strings(lang).get("foot_source")
        check(bool(label) and "<" not in label, f"{lang} has a source-code label")
        build.LANG = lang
        foot = build.site_footer("../", "../../", "calendar/abc")
        expect = line_for(lang)
        check(foot.endswith(expect + "</div></footer>"), f"{lang} source line is the last line of the footer")
        colophon = foot.index('class="colophon"')
        check(foot.index('class="footsource"') > colophon, f"{lang} source line sits under the colophon")
        columns = foot[foot.index('class="foot-grid"'):colophon]
        # The closing quote keeps this from matching the longer contributors URL in the same column.
        check(columns.count(f'href="{REPO}"') == 0, f"{lang} footer columns do not repeat the repo link")
        check(foot.count(expect) == 1, f"{lang} source line appears once")

    old = (build.SITE, build.LANG, build.PREVIEW)
    with tempfile.TemporaryDirectory() as tmp:
        build.SITE = tmp
        build.PREVIEW = False
        try:
            pages = (
                ("nb", "calendar/ccc2eea6b213", True),
                ("en", "stories/1a95167a3af8", True),
                ("sv", "newsletter/001", True),
                ("fi", "about", False),
                ("ar", "", False),
            )
            for lang, slug, share in pages:
                build.LANG = lang
                build.page(slug, "Title", "calendar" if slug.startswith("calendar") else "news", "<p>Body text.</p>", "A description")
                html = open(os.path.join(tmp, build.lp(lang), slug, "index.html"), encoding="utf-8").read()
                main = html.split("<main", 1)[1].split("</main>", 1)[0]
                check("social-source" not in main and PATH_TEXT not in main, f"{lang} {slug or 'home'}: page body has no source line")
                check(('class="share"' in main) is share, f"{lang} {slug or 'home'}: share bar {'present' if share else 'absent'}")
                foot = html[html.index("<footer>"):html.index("</footer>")]
                check(line_for(lang) in foot and foot.index(line_for(lang)) > foot.index('class="colophon"'), f"{lang} {slug or 'home'}: footer ends with the source line")
        finally:
            build.SITE, build.LANG, build.PREVIEW = old

    if fails:
        print(f"\n{len(fails)} failed")
        sys.exit(1)
    print("\nall ok")


if __name__ == "__main__":
    main()
