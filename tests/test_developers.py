#!/usr/bin/env python3
"""Open-source developers page: data/developers.json, the /developers/ page, the links from Who's who and the footer,
and /api/v1/developers.json.
  python3 tests/test_developers.py
Renders into a temp directory. Does not publish and does not call the GitHub or GitLab APIs."""
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import api_feed
import build
import developers as dev_mod
import i18n
import markets

PAGE_KEYS = ("dev_nav", "dev_title", "dev_desc", "dev_h1", "dev_lead", "dev_rule", "dev_preview", "dev_empty", "dev_n", "dev_n1",
             "dev_whoswho", "dev_stars", "dev_prs", "dev_commits", "dev_nordic", "dev_org_link", "dev_notice")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def check(ok, msg, fails):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def render(tmp, preview, lang):
    build.SITE = tmp
    build.PREVIEW = preview
    build.LANG = lang
    os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
    i18n.MISSING.clear()
    build.build_developers()
    rel = "developers/index.html" if lang == "en" else lang + "/developers/index.html"
    html = open(os.path.join(tmp, rel), encoding="utf-8").read()
    return html, html.split("<main", 1)[1].split("</main>", 1)[0]


def main():
    fails = []
    for msg in dev_mod.problems():
        check(False, "data: " + msg, fails)
    raw = dev_mod.raw()
    every = dev_mod.all_rows()
    public = dev_mod.rows(preview=False)
    preview = dev_mod.rows(preview=True)
    check(len(every) >= 30, f"{len(every)} people in the data", fails)
    check(not EMAIL.search(json.dumps(raw, ensure_ascii=False)), "no email addresses in the data", fails)
    check(all(r["status"] == "published" for r in public), "public rows are all published", fails)
    check(len(preview) == sum(r["status"] in ("published", "pending") for r in every), "preview has published and pending rows", fails)
    for r in every:
        check(any(p["kind"] in ("github", "gitlab", "codeberg", "sourcehut") for p in r["profiles"]), r["id"] + " has a code profile", fails)
        check(1 <= len(r["notable"]) <= 3, r["id"] + " has 1-3 notable items", fails)
    owner = [r for r in every if r.get("review") == "ready_for_owner"]
    check(all(r.get("note") for r in owner), "rows for jQrgen say why they wait for him", fails)
    for lang in ("en", "nb", "nn"):
        table = i18n.strings(lang)
        for key in PAGE_KEYS:
            check(bool(table.get(key)), f"{lang} has {key}", fails)
        check("../about/#corrections" in table.get("dev_notice", ""), f"{lang} corrections link", fails)
    for lang in i18n.ALL_LANGS:
        check(bool(i18n.strings(lang).get("dev_nav")) and bool(i18n.strings(lang).get("dev_org_link")), f"{lang} has the footer and Who's who link text", fails)

    with tempfile.TemporaryDirectory() as tmp:
        for lang in ("en", "nb", "nn"):
            html, main_html = render(tmp, False, lang)
            n = main_html.count('<li id="')
            check(n == len(public), f"{lang} public page shows only published rows ({n})", fails)
            if not public:
                check(i18n.t(lang, "dev_empty") in main_html, f"{lang} public page says nothing is approved yet", fails)
            check("tag pend" not in main_html, f"{lang} public page has no pending marks", fails)
            check('href="../developers/"' in html or 'href="developers/"' in html or "/developers/" in html, f"{lang} footer links the page", fails)
            check(not i18n.MISSING, f"{lang} no missing strings {sorted(i18n.MISSING)}", fails)
            check("text-align:center" not in main_html, f"{lang} nothing centred", fails)
        pub_json = json.load(open(os.path.join(tmp, "data", "developers.json"), encoding="utf-8"))
        check(pub_json["preview"] is False and len(pub_json["people"]) == len(public), "site/data/developers.json is public rows only", fails)

    with tempfile.TemporaryDirectory() as tmp:
        html, main_html = render(tmp, True, "en")
        check(main_html.count('<li id="') == len(preview), f"preview page lists {len(preview)} rows", fails)
        check(main_html.count("tag pend") == sum(r["status"] == "pending" for r in preview), "preview marks every pending row", fails)
        for r in preview:
            for p in r["profiles"]:
                check(p["url"] in main_html, f"{r['id']} links {p['url']}", fails)
            for nb in r["notable"]:
                check(nb["url"].replace("&", "&amp;") in main_html, f"{r['id']} links {nb['url']}", fails)
            if r.get("whoswho_id"):
                check(f'href="../org-chart/#{r["whoswho_id"]}"' in main_html, f"{r['id']} links its who's who entry", fails)
        check('rel="noopener nofollow"' in main_html, "external links are nofollow", fails)
        check(all(f'data-c="{c}"' in main_html for c in {r["country"] for r in preview}), "a chip and group per country", fails)

    # Who's who links the page
    src = open(os.path.join(ROOT, "build.py"), encoding="utf-8").read()
    check('href="../developers/"' in src.split("def build_org", 1)[1].split("def ", 1)[0], "Who's who links /developers/", fails)
    check("build_developers()" in src.split("def build_lang", 1)[1].split("\ndef ", 1)[0], "build_lang builds the page", fails)

    with tempfile.TemporaryDirectory() as tmp:
        ctx = api_feed.repo_context(False)
        info = api_feed.write(
            tmp, preview=False, base=build.BASE,
            items=ctx["items"], events=ctx["events"][0], entities=ctx["ents"], relations=ctx["rels"],
            org_updated=ctx["org"].get("updated"), regulation=ctx["org"].get("regulation") or [],
            caveats=ctx["org"].get("caveats") or [], sources_cfg=ctx["cfg"],
            news_updated=ctx["news"].get("updated"), markets=markets.empty_failure("fixture"),
        )
        body = json.load(open(os.path.join(tmp, "api/v1/developers.json"), encoding="utf-8"))
        check(body["count"] == len(public) == len(body["people"]), "developers.json has the published rows only", fails)
        check(info["counts"]["developers"] == len(public), "index count", fails)
        spec = json.load(open(os.path.join(tmp, "api/v1/openapi.json"), encoding="utf-8"))
        check("/api/v1/developers.json" in spec["paths"] and "Developer" in spec["components"]["schemas"], "openapi", fails)
        meta = json.load(open(os.path.join(tmp, "api/v1/meta.json"), encoding="utf-8"))
        check(any(p["path"] == "/developers/" for p in meta["site_pages"]), "meta site_pages", fails)

    if fails:
        print(f"\n{len(fails)} failed")
        return 1
    print("developers ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
