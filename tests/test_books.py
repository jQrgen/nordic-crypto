#!/usr/bin/env python3
"""Books page: data/books.json, the /books/ page, the Books nav tab and /api/v1/books.json.
  python3 tests/test_books.py
Renders into a temp directory. Does not publish."""
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import api_feed
import books as books_mod
import build
import i18n
import markets

KEYS = ("nav_books", "books_title", "books_desc", "books_h1", "books_lead", "books_note", "books_n",
        "books_eds", "books_source", "books_empty", "books_notice")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def check(ok, msg, fails):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    fails = []
    for msg in books_mod.problems():
        check(False, "data: " + msg, fails)
    rows = books_mod.rows()
    check(len(rows) >= 10, f"{len(rows)} books", fails)
    check(any(r["title"] == "Svalbard! Pengar!" and r["authors"] == ["Morten Søberg"] for r in rows), "Svalbard! Pengar! by Morten Søberg", fails)
    blob = json.dumps(books_mod.raw(), ensure_ascii=False)
    check(not EMAIL.search(blob), "no email addresses in the data", fails)
    check("Crypto" + " Nordic" not in blob, "brand order in the data", fails)
    for r in rows:
        check(len(r["about"]) <= 200, r["id"] + " short description", fails)
        check(1990 <= r["year"] <= 2026, r["id"] + " year", fails)

    check(("books", "nav_books") in build.NAV, "Books is a nav tab", fails)
    order = [n for n, _k in build.NAV]
    check(order.index("books") == order.index("academia") + 1, "Books sits after Academia", fails)
    for lang in i18n.ALL_LANGS:
        table = i18n.strings(lang)
        for key in KEYS:
            check(bool(table.get(key)), f"{lang} has {key}", fails)
        check("{n}" in table.get("books_n", ""), f"{lang} books_n has {{n}}", fails)
        check("../about/#corrections" in table.get("books_notice", ""), f"{lang} corrections link", fails)

    with tempfile.TemporaryDirectory() as tmp:
        build.SITE = tmp
        build.PREVIEW = False
        for lang in ("en", "nn", "sv"):
            build.LANG = lang
            i18n.MISSING.clear()
            build.build_books()
            rel = "books/index.html" if lang == "en" else lang + "/books/index.html"
            html = open(os.path.join(tmp, rel), encoding="utf-8").read()
            main_html = html.split("<main", 1)[1].split("</main>", 1)[0]
            check("<img" not in main_html, f"{lang} no images in the list", fails)
            check("Svalbard! Pengar!" in main_html and "Morten Søberg" in main_html, f"{lang} lists Svalbard! Pengar!", fails)
            check(main_html.count("<li id=") == len(rows), f"{lang} one item per book", fails)
            check(all(r["source"].replace("&", "&amp;") in main_html for r in rows), f"{lang} every title links its source", fails)
            check("text-align:center" not in main_html and "center" not in main_html.split("<script", 1)[0], f"{lang} nothing centred", fails)
            check('aria-current=page>' + i18n.t(lang, "nav_books") in html.replace('"', ""), f"{lang} Books tab is current", fails)
            check("Nordic Crypto" in html and ("Crypto" + " Nordic") not in html, f"{lang} brand", fails)
            check(not i18n.MISSING, f"{lang} no missing strings {sorted(i18n.MISSING)}", fails)
    # Books and academic works are separate tabs: the academia builder does not read the books.
    import inspect
    check("books" not in inspect.getsource(build.build_academia), "academia page does not list the books", fails)

    with tempfile.TemporaryDirectory() as tmp:
        ctx = api_feed.repo_context(False)
        info = api_feed.write(
            tmp, preview=False, base=build.BASE,
            items=ctx["items"], events=ctx["events"][0], entities=ctx["ents"], relations=ctx["rels"],
            org_updated=ctx["org"].get("updated"), regulation=ctx["org"].get("regulation") or [],
            caveats=ctx["org"].get("caveats") or [], sources_cfg=ctx["cfg"],
            news_updated=ctx["news"].get("updated"), markets=markets.empty_failure("fixture"),
        )
        body = json.load(open(os.path.join(tmp, "api/v1/books.json"), encoding="utf-8"))
        check(body["count"] == len(rows) == len(body["books"]), "books.json count", fails)
        check(all(b["html_url"].endswith("/books/#" + b["id"]) for b in body["books"]), "books.json html_url", fails)
        check(info["counts"]["books"] == len(rows), "index count", fails)
        spec = json.load(open(os.path.join(tmp, "api/v1/openapi.json"), encoding="utf-8"))
        check("/api/v1/books.json" in spec["paths"] and "Book" in spec["components"]["schemas"], "openapi", fails)
        docs = open(os.path.join(tmp, "api/index.html"), encoding="utf-8").read()
        check("/api/v1/books.json" in docs, "human api docs", fails)
        meta = json.load(open(os.path.join(tmp, "api/v1/meta.json"), encoding="utf-8"))
        check(any(p["path"] == "/books/" for p in meta["site_pages"]), "meta site_pages", fails)

    if fails:
        print(f"\n{len(fails)} failed")
        return 1
    print("books ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
