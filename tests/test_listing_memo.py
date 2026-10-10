#!/usr/bin/env python3
"""One fetch per listing URL and per article page in a run. No network, and no writes to data/, state/ or queue/.
python3 -m unittest tests.test_listing_memo
"""
import collections
import datetime as dt
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch

HOST = "https://memo.example"
SITEMAP = HOST + "/sitemap.xml"
TITLED = HOST + "/nyheter/bitcoin-titled"
UNTITLED = HOST + "/nyheter/bitcoin-untitled"


def sitemap_xml():
    when = (fetch.NOW - dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
 <url><loc>{TITLED}</loc><news:news><news:publication_date>{when}</news:publication_date><news:title>Bitcoin i kommunen</news:title></news:news></url>
 <url><loc>{UNTITLED}</loc><news:news><news:publication_date>{when}</news:publication_date></news:news></url>
</urlset>"""


def article_html():
    when = (fetch.NOW - dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f'<html><head><title>x</title><meta property="og:title" content="Kryptovaluta på rådhuset">'
            f'<meta property="article:published_time" content="{when}"></head><body><p>Bitcoin.</p></body></html>')


class Response:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text
        self.content = text.encode()
        self.headers = {"ETag": '"v1"'} if status == 200 else {}


class FakeNet:
    """Counts every get(url, conditional). A conditional get of the sitemap answers 304."""

    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def get(self, url, conditional=True):
        with self.lock:
            self.calls.append((url, conditional))
        time.sleep(0.05)  # long enough for the other worker to ask for the same URL
        if url == SITEMAP:
            return Response(304) if conditional else Response(200, sitemap_xml())
        return Response(404)

    def per_url(self):
        return collections.Counter(u for u, _ in self.calls)


def source(sid):
    return {"id": sid, "name": f"Memo {sid}", "type": "sitemap", "method": "sitemap", "enabled": True,
            "url": HOST + "/", "feed": SITEMAP, "country": "DK", "language": "Danish", "all_relevant": True}


class ListingMemoTest(unittest.TestCase):
    def setUp(self):
        fetch._reset_run_memo()
        self.addCleanup(fetch._reset_run_memo)
        self.net = FakeNet()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.saved = {}
        self.pages = collections.Counter()

        def read_html(url):
            self.pages[url] += 1
            time.sleep(0.05)
            return article_html()

        for target, value in (
            ("get", self.net.get),
            ("robots_ok", lambda url: True),
            ("read_html", read_html),
            ("load", lambda path, default: default),
            ("save", lambda path, data: self.saved.__setitem__(os.path.relpath(path, self.tmp.name), data)),
            ("P", lambda *a: os.path.join(self.tmp.name, *a)),
            ("DELAY", 0),
        ):
            p = mock.patch.object(fetch, target, value)
            p.start()
            self.addCleanup(p.stop)
        self.remember = mock.patch.object(fetch, "remember_response").start()
        self.addCleanup(mock.patch.stopall)

    def run_main(self, ids):
        sources = [source(i) for i in ids]
        with mock.patch.dict(fetch.CFG, {"sources": sources, "fetch_workers": 4}), \
             mock.patch.object(sys, "argv", ["fetch.py", "--only", ",".join(ids), "--no-events"]):
            fetch.main()

    def test_two_sources_share_one_fetch_per_url(self):
        self.run_main(["memo-a", "memo-b"])
        self.assertTrue(self.net.calls)
        self.assertEqual(max(self.net.per_url().values()), 1, self.net.calls)
        self.assertEqual(self.net.per_url()[SITEMAP], 1)
        self.assertEqual(self.pages[UNTITLED], 1, "page_meta read the article once for both sources")
        status = self.saved[os.path.join("state", "source_status.json")]
        for sid in ("memo-a", "memo-b"):
            self.assertIn(sid, status)
            self.assertTrue(status[sid]["ok"], status[sid])
            self.assertEqual(status[sid]["entries"], 2, status[sid])
            self.assertIsNone(status[sid]["error"])
        items = {i["url"]: i for i in self.saved[os.path.join("data", "news.json")]["items"]}
        self.assertEqual(set(items), {TITLED, UNTITLED})
        for it in items.values():
            self.assertEqual(sorted(it["seen_via"]), ["memo-a", "memo-b"])
        # Only the mocked save wrote anything; nothing reached data/, state/ or queue/.
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_304_is_never_asked_for(self):
        self.run_main(["memo-a", "memo-b"])
        self.assertTrue(all(cond is False for _, cond in self.net.calls), self.net.calls)
        self.remember.assert_not_called()

    def test_listing_get_does_not_refetch_a_304(self):
        calls = []
        def get(url, conditional=True):
            calls.append(conditional)
            return Response(304)
        fetch.get = get  # setUp's patch restores the real get
        self.assertEqual(fetch.listing_get(SITEMAP), (304, ""))
        self.assertEqual(fetch.listing_get(SITEMAP), (304, ""))
        self.assertEqual(calls, [False])

    def test_listing_get_failure_reaches_every_caller_once(self):
        calls = []
        def get(url, conditional=True):
            calls.append(url)
            time.sleep(0.05)
            raise requests.Timeout("read timed out")
        fetch.get = get
        raised = []
        def worker():
            try:
                fetch.listing_get(SITEMAP)
            except requests.Timeout as ex:
                raised.append(ex)
        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(calls, [SITEMAP])
        self.assertEqual(len(raised), 3)

    def test_page_meta_failure_is_not_kept(self):
        attempts = []
        def read_html(url):
            attempts.append(url)
            if len(attempts) == 1:
                raise requests.ConnectionError("reset")
            return article_html()
        fetch.read_html = read_html
        with self.assertRaises(requests.ConnectionError):
            fetch.page_meta(UNTITLED)
        title, _desc, date = fetch.page_meta(UNTITLED)
        self.assertEqual(title, "Kryptovaluta på rådhuset")
        self.assertIsNotNone(date)
        fetch.page_meta(UNTITLED)
        self.assertEqual(len(attempts), 2)

    def test_outlet_feed_time_is_unconditional(self):
        feed = HOST + "/rss"
        calls = []
        def get(url, conditional=True):
            calls.append((url, conditional))
            return Response(200, "<rss><channel></channel></rss>")
        fetch.get = get
        with mock.patch.dict(fetch.SRC, {"memo-rss": {"id": "memo-rss", "type": "rss", "feed": feed, "country": "DK"}}):
            fetch.outlet_feed_time(TITLED, "memo-rss")
            fetch.outlet_feed_time(UNTITLED, "memo-rss")
        self.assertEqual(calls, [(feed, False)])
        self.remember.assert_not_called()


if __name__ == "__main__":
    unittest.main()
