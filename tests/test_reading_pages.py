#!/usr/bin/env python3
"""Story pages and text pages: one outlet list, the latest stories under a story, the About jump list, and the
light/dark paragraph in the privacy section of every About template. No network."""
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build
import site_css

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    # About, 7 languages: the theme paragraph sits right after the one-cookie paragraph; the jump targets exist
    for lang in ("", ".nn", ".nb", ".sv", ".da", ".fi", ".is"):
        name = f"about{lang}.html"
        text = open(os.path.join(ROOT, "templates", name), encoding="utf-8").read()
        paras = [p for p in text.split("\n") if p.startswith("<p><b>")]
        cookie = [n for n, p in enumerate(paras) if "<code>nc_lang</code>" in p]
        theme = [n for n, p in enumerate(paras) if "<code>nc-theme</code>" in p]
        check(len(cookie) == 1 and theme == [cookie[0] + 1], name + ": theme paragraph follows the cookie paragraph")
        check(text.count("<code>nc-theme</code>") == 1, name + ": nc-theme named once")
        for anchor in ("privacy", "corrections", "columnist", "ios"):
            check(f'<h2 id="{anchor}">' in text, f"{name}: #{anchor}")
        check(text.index('<p class="lead">') < text.index('<div class="prose">'), name + ": lead above the text column")

    build.LANG = "en"
    about = build.lang_template("about")
    toc = build.page_toc(about)
    check('href="#privacy"' in toc and 'href="#corrections"' in toc, "about jump list")
    page = build.text_page(about)
    check('class="textpage has-toc"' in page and page.index('class="toc"') < page.index('class="tp-body"'), "jump list before the text")
    check(build.page_toc("<h2 id=a>x</h2>") == "", "short pages get no jump list")

    for mod in ("story", "textpage", "brand", "api-docs"):
        css = site_css.read(mod)
        check("text-align:center" not in css and "justify-content:flex-end" not in css and "justify-content:center" not in css,
              mod + ".css is start-aligned")
        check(mod not in site_css.SITE, mod + ".css is inlined only on its pages")

    news = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8"))
    items = sorted([i for i in news["items"] if i.get("status") == "published"], key=lambda i: i["published"], reverse=True)
    two = next((i for i in items if i["id"] == "1a95167a3af8"), None)
    one = next((i for i in items if not i.get("also_covered_by") and i is not two), None)
    build.PREVIEW = False
    with tempfile.TemporaryDirectory() as tmp:
        build.SITE = tmp
        build.LANG = "en"
        build.build_coverage_pages([one] + ([two] if two else []) + [i for i in items if i not in (one, two)][:6], {})
        html = open(os.path.join(tmp, "stories", one["id"], "index.html"), encoding="utf-8").read()
        body = html.split('<main class="wrap"', 1)[1].split(">", 1)[1].split("</main>", 1)[0]
        check('class="readat"' in body and 'class="coverage"' not in body, "one outlet: the Read at button, no outlet list")
        check('class="morenews"' in body and body.count("<li><a href=") == build.MORE_NEWS_N, "latest stories under the story")
        check(f'stories/{one["id"]}/' not in body.split('class="morenews"', 1)[1].split("</aside>", 1)[0], "the story is not in its own list")
        check("text-align:center" not in body, "story page not centred")
        if two:
            html2 = open(os.path.join(tmp, "stories", two["id"], "index.html"), encoding="utf-8").read()
            body2 = html2.split('<main class="wrap"', 1)[1].split(">", 1)[1].split("</main>", 1)[0]
            check('class="coverage"' in body2, "two outlets: the outlet list")
            for row in build.story_outlets(two):
                url = build.E(row["url"])
                check(len(re.findall('class="cov-title" href="' + re.escape(url), body2)) == 1, "each outlet listed once: " + row["outlet"])
            check('class="seg covsort"' not in body2, "one country: no sort toggle")
        build.LANG = "ar"
        build.build_coverage_pages([one], {})
        ar = open(os.path.join(tmp, "ar", "stories", one["id"], "index.html"), encoding="utf-8").read()
        check('dir="rtl"' in ar and re.search(r'<p class="sum lede" lang="en" dir="ltr">', ar) is not None, "English summary reads left to right on an RTL page")
        build.LANG = "en"

    if fails:
        print(f"{len(fails)} failed")
        sys.exit(1)
    print("reading pages ok")


if __name__ == "__main__":
    main()
