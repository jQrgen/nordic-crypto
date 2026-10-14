#!/usr/bin/env python3
"""The public data model: schema/*.schema.json matches the files, and /db/ is rendered from it.
  python3 -m unittest tests.test_schema
"""
import copy
import importlib
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import build
import i18n
import markets
import schema_db

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
FETCHED = "2026-10-14T12:00:00+00:00"


def _news_schema():
    for name, schema in schema_db.load_schemas():
        if name == "news.schema.json":
            return schema
    raise AssertionError("news schema missing")


def _markets_schema():
    for name, schema in schema_db.load_schemas():
        if name == "markets.schema.json":
            return schema
    raise AssertionError("markets schema missing")


class SchemaTests(unittest.TestCase):
    def test_repo_matches_schemas(self):
        errs = schema_db.validate_repo()
        self.assertEqual(errs, [], "\n".join(errs[:30]))

    def test_missing_id_fails(self):
        schema = _news_schema()
        data = schema_db.load_json(os.path.join(ROOT, "data", "news.json"))
        item = dict(data["items"][0])
        del item["id"]
        errs = schema_db.Validator(schema).check_against(item, schema["$defs"]["story"], "$")
        self.assertTrue(any("missing id" in err for err in errs), errs)

    def test_extra_property_fails(self):
        schema = _news_schema()
        data = schema_db.load_json(os.path.join(ROOT, "data", "news.json"))
        data = copy.deepcopy(data)
        data["items"][0]["not_a_field"] = True
        errs = schema_db.validate(data, schema)
        self.assertTrue(any("not_a_field" in err for err in errs), errs[:8])

    def test_markets_fixture(self):
        body = markets.empty_failure("fixture")
        body["tickers"] = markets.parse_firi(
            [{"id": "BTCNOK", "last": "827301.99", "high": "839994.22", "low": "813881.71", "volume": "3.13", "change": "-0.57"}],
            [{"market": "BTCNOK", "bid": "822000", "ask": "827756.56", "spread": "5756.56"}],
            FETCHED,
        )
        doc = markets.public_document(body, generated_at=FETCHED, preview=False)
        errs = schema_db.validate(doc, _markets_schema())
        self.assertEqual(errs, [], "\n".join(errs[:30]))

    def test_strings_and_page(self):
        info = schema_db.version_info()
        for lang in i18n.ALL_LANGS:
            row = i18n.strings(lang)
            for key in importlib.import_module("i18n.db_strings").KEYS:
                self.assertTrue(row.get(key), f"{lang} missing {key}")
            html = schema_db.page_body(lang)
            self.assertIn(i18n.t(lang, "db_h1"), html)
            self.assertIn('lang="en"', html)
            self.assertIn('dir="ltr"', html)
            self.assertIn("calendar_status", html)
            self.assertIn("upcoming", html)
            self.assertIn("ongoing", html)
            self.assertIn("past", html)
            self.assertIn("erDiagram", html)
            self.assertIn("<svg", html)
            self.assertIn('id="news"', html)
            self.assertIn('id="rules"', html)
            self.assertIn("/api/v1/news.json", html)
            self.assertIn("/api/v1/schema/news.schema.json", html)
            self.assertIn(i18n.t(lang, "db_private_h"), html)
            private = html.split('id="private"', 1)[1].split("<h2", 1)[0]
            self.assertNotIn("token_hash", private)
            self.assertIsNone(EMAIL.search(private))
            self.assertIsNone(EMAIL.search(html))
            self.assertNotIn("/workspace", html)
            self.assertNotIn("token_hash", html)
            if info.get("version"):
                self.assertIn(info["version"], html)
                self.assertIn(info["commit"], html)
            else:
                self.assertIn(i18n.t(lang, "db_no_history"), html)
        footer = build.site_footer("", "")
        self.assertIn('href="db/"', footer)
        self.assertLess(footer.index("api/"), footer.index('href="db/"'))

    def test_publish_keeps_field_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = schema_db.publish(tmp, "https://nordiccrypto.no/", generated_at=FETCHED)
            index = schema_db.load_json(os.path.join(tmp, "api", "v1", "schema", "index.json"))
            self.assertEqual(index["docs_url"], "https://nordiccrypto.no/db/")
            self.assertTrue(any(c["id"] == "news" for c in doc["collections"]))
            news = schema_db.load_json(os.path.join(tmp, "api", "v1", "schema", "news.schema.json"))
            props = news["$defs"]["story"]["properties"]
            self.assertIn("id", props)
            self.assertIn("approved_by", props)
            with open(os.path.join(tmp, "api", "v1", "schema", "index.json"), encoding="utf-8") as fh:
                blob = fh.read()
            self.assertNotIn("token_hash", blob)
            self.assertIsNone(EMAIL.search(blob))
            self.assertTrue(os.path.exists(os.path.join(tmp, "api", "v1", "schema", "erd.svg")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "api", "v1", "schema", "erd.mmd")))

    def test_history_reads_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.check_call(["git", "init", "-q"], cwd=tmp)
            os.makedirs(os.path.join(tmp, "schema"))
            with open(os.path.join(tmp, "schema", "demo.schema.json"), "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            env = os.environ.copy()
            env["GIT_AUTHOR_NAME"] = "Schema Test"
            env["GIT_AUTHOR_EMAIL"] = "schema@localhost"
            env["GIT_COMMITTER_NAME"] = "Schema Test"
            env["GIT_COMMITTER_EMAIL"] = "schema@localhost"
            subprocess.check_call(["git", "add", "schema"], cwd=tmp, env=env)
            subprocess.check_call(["git", "commit", "-q", "-m", "add schema"], cwd=tmp, env=env)
            old = schema_db.ROOT
            schema_db._HISTORY.pop(tmp, None)
            try:
                schema_db.ROOT = tmp
                rows = schema_db.history()
            finally:
                schema_db.ROOT = old
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["subject"], "add schema")
            self.assertEqual(len(rows[0]["date"]), 10)
            self.assertTrue(rows[0]["url"].endswith(rows[0]["sha"]))


if __name__ == "__main__":
    unittest.main()
