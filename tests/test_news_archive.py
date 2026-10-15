#!/usr/bin/env python3
"""Historical archive: year files, academia theses and papers in the same feed, and the /archive/ page.

Renders into a temp directory. Does not publish and does not import tools/import_academia.py
(importing that module rewrites data/academia.json).
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import api_feed
import build
import i18n
import news_archive
from i18n.archive_strings import KEYS

MASTER_URL = "https://hdl.handle.net/11250/2625939"
PROJECT_URL = "https://doi.org/10.13140/rg.2.2.22304.58886"
MASTER_ID = "ac-2625939"
PROJECT_ID = "ac-10-13140-rg-2-2-22304-58886"
MASTER_EN = "The Minimum Hybrid Contract (MHC): Combining Legal and Blockchain Smart Contracts"
PROJECT_TITLE = "Blockchain enabled Trust & Transparency in supply chains"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _main(html):
    return html.split("<main", 1)[1].split("</main>", 1)[0]


def test_schema_and_year_files_are_empty():
    assert news_archive.problems() == []
    assert news_archive.academic_problems() == []
    assert news_archive.news_rows() == []
    news_dir = news_archive.NEWS_DIR
    for name in os.listdir(news_dir):
        if not name.endswith(".json"):
            continue
        blob = _read(os.path.join(news_dir, name))
        assert MASTER_URL not in blob
        assert PROJECT_URL not in blob
        assert "2625939" not in blob


def test_theses_are_approved_in_academia_and_the_catalogue():
    academia = json.load(open(news_archive.ACADEMIA, encoding="utf-8"))
    works = json.load(open(os.path.join(ROOT, "research", "academia", "works.json"), encoding="utf-8"))
    for blob in (academia["publications"], works):
        by_url = {row.get("url"): row for row in blob}
        master = by_url[MASTER_URL]
        project = by_url[PROJECT_URL]
        assert master["status"] == "approved"
        assert master["type"] == "master"
        assert master["year"] == 2019
        assert master["authors"] == ["Jørgen Svennevik Notland"]
        assert master["title_en"] == MASTER_EN
        assert project["status"] == "approved"
        assert project["type"] == "project"
        assert project["year"] == 2017
        assert project["authors"] == ["Jørgen Svennevik Notland", "Anders Viet Hua"]
        assert project["doi"] == "10.13140/rg.2.2.22304.58886"
        assert project["title"] == PROJECT_TITLE


def test_public_feed_merges_the_two_theses_newest_first():
    rows = news_archive.public_items()
    assert [row["type"] for row in rows] == ["academic", "academic"]
    assert [row["id"] for row in rows] == [MASTER_ID, PROJECT_ID]
    assert rows[0]["work_type"] == "master"
    assert rows[1]["work_type"] == "project"
    assert rows[0]["url"] == MASTER_URL
    assert rows[1]["url"] == PROJECT_URL
    assert rows[0]["published"] == "2019-01-01T00:00:00+00:00"
    assert rows[1]["published"] == "2017-01-01T00:00:00+00:00"
    assert rows[0]["published_precision"] == "year"
    assert rows[0]["archive_url"] is None
    assert all(row["type"] in ("news", "academic") for row in rows)
    pages = news_archive.paginate(rows, 1)
    assert len(pages) == 2
    assert pages[0][0]["id"] == MASTER_ID
    assert pages[1][0]["id"] == PROJECT_ID
    assert news_archive.paginate(rows) == [rows]


def test_papers_join_the_feed_and_phd_rows_stay_on_academia(tmp_path):
    news = tmp_path / "news"
    news.mkdir()
    (news / "schema.json").write_text("{}\n", encoding="utf-8")
    (news / "2019.json").write_text(json.dumps({
        "year": 2019,
        "articles": [{
            "id": "n-2019",
            "title": "A sourced headline",
            "source": "Example",
            "url": "https://example.invalid/story",
            "archive_url": None,
            "published": "2019-06-01T12:00:00+00:00",
            "country": "NO",
            "language": "English",
            "summary": "A summary.",
        }],
    }), encoding="utf-8")
    academia = tmp_path / "academia.json"
    academia.write_text(json.dumps({"publications": [
        {"status": "approved", "type": "paper", "year": 2019, "country": "SE", "title": "A paper",
         "url": "https://example.invalid/paper", "about": "Paper.", "authors": ["A"]},
        {"status": "approved", "type": "conference", "year": 2016, "country": "DK", "title": "A conference paper",
         "url": "https://example.invalid/conf", "about": "Conference."},
        {"status": "approved", "type": "phd", "year": 2020, "country": "NO", "title": "A dissertation",
         "url": "https://example.invalid/phd", "about": "PhD."},
        {"status": "pending", "type": "master", "year": 2018, "country": "NO", "title": "Not approved",
         "url": "https://example.invalid/pending", "about": "Pending."},
    ]}), encoding="utf-8")
    rows = news_archive.public_items(str(news), str(academia))
    assert [(row["type"], row["work_type"], row["id"]) for row in rows] == [
        ("news", None, "n-2019"),
        ("academic", "paper", "ac-example-invalid-paper"),
        ("academic", "conference", "ac-example-invalid-conf"),
    ]
    assert rows[0]["published"] > rows[1]["published"]
    assert news_archive.problems(str(news)) == []
    blob = (news / "2019.json").read_text(encoding="utf-8")
    assert "example.invalid/paper" not in blob
    assert "example.invalid/conf" not in blob


def test_import_keeps_project_theses_and_approved_status_without_running_it():
    src = _read(os.path.join(ROOT, "tools", "import_academia.py"))
    assert '"project"' in src
    assert 'w.get("status") == "approved"' in src
    assert "Project thesis" in src


def test_every_language_has_archive_strings():
    for lang in i18n.ALL_LANGS:
        table = i18n.strings(lang)
        for key in KEYS:
            assert table.get(key), f"{lang} missing {key}"
        assert "{n}" in table["arc_n"]
        assert "{n}" in table["arc_page"] and "{m}" in table["arc_page"]


def test_api_page_json_and_docs():
    rows = news_archive.public_items()
    with tempfile.TemporaryDirectory() as tmp:
        feed = api_feed.Feed(tmp, False, build.BASE, now="2026-10-15T12:00:00+00:00")
        written, pages = api_feed.write_news_archive(feed)
        assert pages == 1
        assert len(written) == len(rows) == 2
        doc = json.load(open(os.path.join(tmp, "api/v1/archive/news/page-1.json"), encoding="utf-8"))
        assert doc["page"] == 1 and doc["pages"] == 1 and doc["page_size"] == 20
        assert doc["count"] == 2 and doc["newest_first"] is True
        assert [item["id"] for item in doc["items"]] == [MASTER_ID, PROJECT_ID]
        assert doc["items"][0]["type"] == "academic"
        assert doc["items"][0]["html_url"].endswith("archive/#" + MASTER_ID)
        assert doc["items"][0]["url"] == MASTER_URL
        assert "editor_note" not in json.dumps(doc)
    fragment = api_feed.docs_fragment({
        "bases": {"github_pages": build.BASE},
        "counts": {},
        "generated_at": "2026-10-15T00:00:00+00:00",
        "endpoints": [],
    })
    assert "/api/v1/archive/news/page-1.json" in fragment


def test_archive_page_lists_both_theses_with_filters():
    old = (build.SITE, build.LANG, build.PREVIEW)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            build.SITE = tmp
            build.PREVIEW = False
            for lang in ("en", "nn", "ar"):
                build.LANG = lang
                i18n.MISSING.clear()
                build.build_archive()
                assert not i18n.MISSING, sorted(i18n.MISSING)
            en = _read(os.path.join(tmp, "archive", "index.html"))
            main = _main(en)
            assert MASTER_EN in main
            assert "Minimum Hybrid Kontrakt" in main
            assert "Trust &amp; Transparency" in main
            assert "Jørgen Svennevik Notland" in main
            assert "Anders Viet Hua" in main
            assert MASTER_URL in main and PROJECT_URL in main
            assert 'data-type="academic"' in main
            assert 'id="y2019"' in main and 'id="y2017"' in main
            assert 'href="../archive/#y2019"' in main and 'href="../archive/#y2017"' in main
            assert 'href="../archive/country/NO/"' in main
            assert 'href="../archive/type/news/"' in main
            assert 'href="../archive/type/academic/"' in main
            assert "No historical news articles yet" in main
            assert "text-align:center" not in main
            assert 'class="nav-more" href="../archive/" aria-current=page' in en
            nn = _read(os.path.join(tmp, "nn", "archive", "index.html"))
            assert "Masteroppgåve" in _main(nn)
            assert 'dir="rtl"' in _read(os.path.join(tmp, "ar", "archive", "index.html"))
            news = _main(_read(os.path.join(tmp, "archive", "type", "news", "index.html")))
            assert "No historical news articles yet" in news
            assert MASTER_EN not in news
            academic = _main(_read(os.path.join(tmp, "archive", "type", "academic", "index.html")))
            assert MASTER_EN in academic
            assert "No historical news articles yet" not in academic
    finally:
        build.SITE, build.LANG, build.PREVIEW = old


def test_infinite_scroll_and_pager_when_a_view_has_another_page():
    old = (build.SITE, build.LANG, build.PREVIEW)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            build.SITE = tmp
            build.LANG = "en"
            build.PREVIEW = False
            i18n.MISSING.clear()
            build.build_archive(page_size=1)
            first = _read(os.path.join(tmp, "archive", "index.html"))
            main = _main(first)
            assert "IntersectionObserver" in first
            assert 'id="arc-sentinel"' in first
            assert 'data-pages="2"' in first
            assert 'data-api="../api/v1/archive/news/page-"' in first
            assert 'data-type=""' in first
            assert 'rel="next" href="../archive/page/2/"' in main
            assert MASTER_EN in main
            assert "Trust &amp; Transparency" not in main
            second = _main(_read(os.path.join(tmp, "archive", "page", "2", "index.html")))
            assert "Trust &amp; Transparency" in second
            assert "IntersectionObserver" not in _read(os.path.join(tmp, "archive", "page", "2", "index.html"))
            assert 'rel="prev"' in second
            typed = _read(os.path.join(tmp, "archive", "type", "academic", "index.html"))
            assert 'data-type="academic"' in typed
            assert "IntersectionObserver" in typed
    finally:
        build.SITE, build.LANG, build.PREVIEW = old
