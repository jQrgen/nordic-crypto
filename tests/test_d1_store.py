#!/usr/bin/env python3
"""D1 import, review, backup and the NC_DATA_SOURCE switch.

  python3 -m unittest tests.test_d1_store
"""
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, ROOT)
from tools import d1_store
from tools import d1_review

SETUP = os.path.join(ROOT, "workers", "content", "setup.sh")
BACKUP = os.path.join(ROOT, "tools", "d1_backup.sh")
SECRET = "super-secret-term-xyz"


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


class ImportTwice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nc-d1-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = os.path.join(self.tmp, "content.sqlite")
        self.store = d1_store.open_sqlite(self.db)
        self.at = "2026-10-10T08:00:00+00:00"

    def test_real_json_round_trip_is_idempotent(self):
        first = d1_store.import_root(self.store, ROOT, self.at)
        self.assertGreater(first["stories"]["inserted"], 0)
        self.assertGreater(first["events"]["inserted"], 0)
        self.assertGreater(first["sources"]["inserted"], 0)
        audit_after_first = self.store.query("SELECT COUNT(*) AS n FROM review_audit")[0]["n"]

        second = d1_store.import_root(self.store, ROOT, "2026-10-10T09:00:00+00:00")
        self.assertEqual(second["stories"]["inserted"], 0)
        self.assertEqual(second["stories"]["updated"], 0)
        self.assertEqual(second["events"]["inserted"], 0)
        self.assertEqual(second["events"]["updated"], 0)
        self.assertEqual(second["sources"]["inserted"], 0)
        self.assertEqual(second["sources"]["updated"], 0)
        audit_after_second = self.store.query("SELECT COUNT(*) AS n FROM review_audit")[0]["n"]
        self.assertEqual(audit_after_first, audit_after_second)

        news = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8"))
        for item in news["items"]:
            row = d1_store.one(self.store, "SELECT payload, review_status, reviewed_by, reviewed_at FROM stories WHERE id = ?", (item["id"],))
            stored = json.loads(row["payload"])
            self.assertEqual(stored, item)
            if item["status"] == "published":
                self.assertEqual(row["review_status"], "approved")
                self.assertEqual(row["reviewed_by"], item["approved_by"])
                self.assertEqual(row["reviewed_at"], item["approved_at"])
            elif item["status"] == "rejected":
                self.assertEqual(row["review_status"], "rejected")

        archive_only = d1_store.one(self.store, "SELECT review_status, payload FROM events WHERE id = ?", ("71149f675741",))
        self.assertEqual(archive_only["review_status"], "approved")
        self.assertIn("title", json.loads(archive_only["payload"]))
        pending = d1_store.one(self.store, "SELECT review_status, item_status FROM events WHERE id = ?", ("2eaf3b36bda9",))
        self.assertEqual(pending["review_status"], "pending")
        self.assertEqual(pending["item_status"], "pending")

        data = {row["id"]: row for row in json.load(open(os.path.join(ROOT, "data", "events.json"), encoding="utf-8"))["events"]}
        archive = {row["id"]: row for row in json.load(open(os.path.join(ROOT, "archive", "events.json"), encoding="utf-8"))["events"]}
        for eid in set(data) | set(archive):
            payload = json.loads(d1_store.one(self.store, "SELECT payload FROM events WHERE id = ?", (eid,))["payload"])
            for key in data.get(eid, {}):
                self.assertIn(key, payload)
            for key in archive.get(eid, {}):
                if key == "status":
                    continue
                self.assertIn(key, payload)
        renamed = json.loads(d1_store.one(self.store, "SELECT payload FROM events WHERE id = ?", ("7adc8e1ede97",))["payload"])
        self.assertEqual(renamed["title_orig"], "Krypto-skatt v/ Reese Legal")
        self.assertEqual(renamed["title"], "Crypto tax with Reese Legal")

        names = [row["name"] for row in self.store.query("SELECT name FROM documents")]
        self.assertNotIn("private_terms", names)
        blob = open(self.db, "rb").read()
        self.assertNotIn(b"private_terms.json", blob)

    def test_a_later_d1_approval_survives_a_second_import(self):
        d1_store.import_root(self.store, ROOT, self.at)
        story = d1_store.one(
            self.store,
            "SELECT id FROM stories WHERE review_status = 'approved' ORDER BY id LIMIT 1",
        )
        d1_store.review_story(
            self.store, story["id"], "approve",
            summary="Rewritten in D1 after the import. The JSON file is older.",
            actor="Editor", at="2026-10-11T12:00:00+00:00",
        )
        d1_store.import_root(self.store, ROOT, "2026-10-10T08:00:00+00:00")
        row = d1_store.one(self.store, "SELECT summary, review_status, reviewed_by FROM stories WHERE id = ?", (story["id"],))
        self.assertEqual(row["summary"], "Rewritten in D1 after the import. The JSON file is older.")
        self.assertEqual(row["review_status"], "approved")
        self.assertEqual(row["reviewed_by"], "Editor")

    def test_fetch_keeps_archive_events_approved_before_the_import(self):
        root = os.path.join(self.tmp, "mini")
        os.makedirs(os.path.join(root, "data"))
        os.makedirs(os.path.join(root, "archive"))
        event = {
            "id": "arch01", "title": "Already on the calendar", "status": "pending",
            "url": "https://example.com/e", "start": "2026-11-01T18:00:00+02:00", "country": "NO",
        }
        with open(os.path.join(root, "data", "events.json"), "w", encoding="utf-8") as fh:
            json.dump({"events": [event]}, fh)
        with open(os.path.join(root, "data", "news.json"), "w", encoding="utf-8") as fh:
            json.dump({"items": []}, fh)
        with open(os.path.join(root, "archive", "events.json"), "w", encoding="utf-8") as fh:
            json.dump({"events": [dict(event, status="published", note="Paid entry.")]}, fh)
        d1_store.sync_root(self.store, root, self.at)
        row = d1_store.one(self.store, "SELECT review_status, payload FROM events WHERE id = ?", ("arch01",))
        self.assertEqual(row["review_status"], "approved")
        self.assertEqual(json.loads(row["payload"])["note"], "Paid entry.")

    def test_rows_are_not_deleted(self):
        d1_store.import_root(self.store, ROOT, self.at)
        story = d1_store.one(self.store, "SELECT id FROM stories LIMIT 1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.execute("DELETE FROM stories WHERE id = ?", (story["id"],))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.execute("DELETE FROM review_audit WHERE id = 1")


class FetchAndReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nc-d1-sync-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.store = d1_store.open_sqlite(os.path.join(self.tmp, "content.sqlite"))
        self.at = "2026-10-10T08:00:00+00:00"
        d1_store.import_root(self.store, ROOT, self.at)

    def test_fetch_does_not_reopen_an_approved_story(self):
        story = d1_store.one(self.store, "SELECT id, payload, summary FROM stories WHERE review_status = 'approved' LIMIT 1")
        payload = json.loads(story["payload"])
        payload["seen_via"] = list(payload.get("seen_via") or []) + ["nightly"]
        payload["summary"] = "fetch must not replace the editor summary"
        payload["status"] = "pending"
        self.assertEqual(d1_store.sync_story(self.store, payload, "2026-10-10T10:00:00+00:00"), "coverage")
        row = d1_store.one(self.store, "SELECT summary, review_status, payload FROM stories WHERE id = ?", (story["id"],))
        self.assertEqual(row["summary"], story["summary"])
        self.assertEqual(row["review_status"], "approved")
        self.assertIn("nightly", json.loads(row["payload"])["seen_via"])
        self.assertNotEqual(json.loads(row["payload"])["summary"], "fetch must not replace the editor summary")

    def test_new_fetch_row_is_pending_and_review_records_who(self):
        item = {
            "id": "newstory01",
            "url": "https://example.com/new-story",
            "title": "A new pending story",
            "status": "pending",
            "summary": None,
            "country": "NO",
            "published": "2026-10-10T07:00:00+00:00",
            "source": "example",
            "source_name": "Example",
        }
        self.assertEqual(d1_store.sync_story(self.store, item, self.at), "inserted")
        self.assertEqual(d1_store.sync_story(self.store, item, self.at), "skipped")
        pending = d1_store.pending_stories(self.store)
        self.assertIn("newstory01", [row["id"] for row in pending])
        plan = d1_store.review_story(
            self.store, "newstory01", "approve",
            summary="The example page says the thing. It is about Norway.",
            actor="Nordic Crypto redaktør", at="2026-10-10T11:00:00+00:00",
        )
        self.assertEqual(plan["review_status"], "approved")
        self.assertEqual(plan["reviewed_by"], "Nordic Crypto redaktør")
        again = d1_store.review_story(
            self.store, "newstory01", "approve",
            summary="The example page says the thing. It is about Norway.",
            actor="Nordic Crypto redaktør", at="2026-10-10T11:00:00+00:00",
        )
        self.assertEqual(again["content_hash"], plan["content_hash"])
        audits = self.store.query(
            "SELECT action FROM review_audit WHERE item_id = ? AND action = 'approve'",
            ("newstory01",),
        )
        self.assertEqual(len(audits), 1)
        with self.assertRaises(d1_store.D1Error):
            d1_store.review_story(self.store, "newstory01", "approve", summary="  ", actor="Editor")
        d1_store.review_event(
            self.store, "2eaf3b36bda9", "reject", actor="Editor",
            at="2026-10-10T11:00:00+00:00", reason="No Nordic link.",
        )
        event = d1_store.one(self.store, "SELECT review_status, reviewed_by, review_note FROM events WHERE id = ?", ("2eaf3b36bda9",))
        self.assertEqual(event["review_status"], "rejected")
        self.assertEqual(event["reviewed_by"], "Editor")
        self.assertEqual(event["review_note"], "No Nordic link.")

    def test_private_terms_are_refused_and_left_out_of_the_backup(self):
        with self.assertRaises(d1_store.D1Error):
            d1_store.put_document(self.store, "private_terms", {"secret": SECRET}, self.at)
        d1_store.put_document(self.store, "teasers", {"newstory01": "teaser " + SECRET}, self.at)
        dest = os.path.join(self.tmp, "backup")
        manifest = d1_store.write_backup(self.store, dest)
        d1_store.assert_backup_dir(dest)
        self.assertIn("teasers", manifest["omitted_documents"])
        blob = ""
        for name in os.listdir(dest):
            with open(os.path.join(dest, name), encoding="utf-8") as fh:
                blob += fh.read()
        self.assertNotIn(SECRET, blob)
        self.assertNotIn("teaser " + SECRET, blob)
        with self.assertRaises(d1_store.D1Error):
            bad = os.path.join(self.tmp, "bad")
            os.makedirs(bad)
            with open(os.path.join(bad, "teasers.json"), "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            d1_store.assert_backup_dir(bad)

    def test_materialize_keeps_pending_off_the_public_file(self):
        item = {
            "id": "pendingonly",
            "url": "https://example.com/pending-only",
            "title": "Still waiting",
            "status": "pending",
            "summary": None,
            "country": "SE",
            "published": "2026-10-10T06:00:00+00:00",
        }
        d1_store.sync_story(self.store, item, self.at)
        root = os.path.join(self.tmp, "checkout")
        os.makedirs(os.path.join(root, "archive"))
        shutil.copy(os.path.join(ROOT, "archive", "events.json"), os.path.join(root, "archive", "events.json"))
        approvals = d1_store.materialize(root, preview=False, store=self.store)
        news = json.load(open(os.path.join(root, "data", "news.json"), encoding="utf-8"))
        ids = [row["id"] for row in news["items"]]
        self.assertNotIn("pendingonly", ids)
        self.assertTrue(all(row["status"] != "pending" for row in news["items"]))
        self.assertIn("71149f675741", approvals["approve"])
        self.assertNotIn("2eaf3b36bda9", approvals["approve"])
        self.assertFalse(os.path.exists(os.path.join(root, "queue", "approved.json")))
        preview = os.path.join(self.tmp, "preview")
        os.makedirs(os.path.join(preview, "archive"))
        shutil.copy(os.path.join(ROOT, "archive", "events.json"), os.path.join(preview, "archive", "events.json"))
        d1_store.materialize(preview, preview=True, store=self.store)
        preview_ids = [row["id"] for row in json.load(open(os.path.join(preview, "data", "news.json"), encoding="utf-8"))["items"]]
        self.assertIn("pendingonly", preview_ids)

    def test_sql_quoting_and_the_review_cli(self):
        item = {
            "id": "quote01",
            "url": "https://example.com/quote",
            "title": "It's a title",
            "status": "pending",
            "summary": None,
            "country": "DK",
            "published": "2026-10-10T06:00:00+00:00",
        }
        d1_store.sync_story(self.store, item, self.at)
        sql_path = os.path.join(self.tmp, "content.sqlite")
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "d1_review.py"),
             "--sqlite", sql_path, "approve", "--id", "quote01",
             "--summary", "It's the editor's own summary. The page says so.",
             "--by", "Editor"],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = d1_store.one(self.store, "SELECT review_status, reviewed_by, summary FROM stories WHERE id = ?", ("quote01",))
        self.assertEqual(row["review_status"], "approved")
        self.assertEqual(row["reviewed_by"], "Editor")
        self.assertIn("It's the editor's", row["summary"])
        printed = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "d1_review.py"),
             "--sqlite", sql_path, "--print-sql", "reject", "--id", "quote01",
             "--reason", "O'Hara said no"],
            check=True, capture_output=True, text=True,
        )
        self.assertIn("O''Hara said no", printed.stdout)
        self.assertIn("review_status", printed.stdout)
        self.assertNotIn("private_terms", printed.stdout)
        still = d1_store.one(self.store, "SELECT review_status FROM stories WHERE id = ?", ("quote01",))
        self.assertEqual(still["review_status"], "approved")


class HttpAndCommands(unittest.TestCase):
    def test_http_query_api_round_trip(self):
        path = os.path.join(tempfile.mkdtemp(prefix="nc-d1-http-"), "local.sqlite")
        self.addCleanup(shutil.rmtree, os.path.dirname(path), True)
        local = d1_store.open_sqlite(path)

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("content-length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                if self.headers.get("authorization") != "Bearer secret-token":
                    self.send_response(401)
                    self.end_headers()
                    return
                try:
                    rows = local.query(body["sql"], body.get("params") or [])
                except Exception as ex:
                    payload = json.dumps({"success": False, "errors": [{"message": type(ex).__name__}]}).encode()
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                payload = json.dumps({"success": True, "result": [{"results": rows, "success": True}]}).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, fmt, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        port = server.server_address[1]
        remote = d1_store.HttpStore("account", "database", "secret-token", base=f"http://127.0.0.1:{port}/client/v4")
        item = {
            "id": "http01",
            "url": "https://example.com/http",
            "title": "Via the query API",
            "status": "pending",
            "summary": None,
            "country": "FI",
            "published": "2026-10-10T06:00:00+00:00",
        }
        self.assertEqual(d1_store.sync_story(remote, item, "2026-10-10T08:00:00+00:00"), "inserted")
        rows = remote.query("SELECT review_status, title FROM stories WHERE id = ?", ["http01"])
        self.assertEqual(rows[0]["review_status"], "pending")
        self.assertEqual(rows[0]["title"], "Via the query API")

    def test_wrangler_json_and_setup_script(self):
        rows = d1_review.parse_wrangler_json('log line\n[{"results": [{"id": "a"}], "success": true}]\n')
        self.assertEqual(rows, [{"id": "a"}])
        self.assertFalse(d1_store.enabled())
        env = os.environ.copy()
        env.pop("CLOUDFLARE_API_TOKEN", None)
        marker = os.path.join(tempfile.mkdtemp(prefix="nc-wrangler-"), "called")
        bindir = os.path.dirname(marker)
        with open(os.path.join(bindir, "npx"), "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\ntouch " + marker + "\nexit 99\n")
        os.chmod(os.path.join(bindir, "npx"), stat.S_IRWXU)
        env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
        proc = subprocess.run(["bash", SETUP], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("npx wrangler d1 create nordic-crypto-content", proc.stdout)
        self.assertIn("CLOUDFLARE_API_TOKEN", proc.stdout)
        self.assertIn("CF_D1_DATABASE_ID", proc.stdout)
        self.assertIn("NC_DATA_SOURCE", proc.stdout)
        self.assertFalse(os.path.exists(marker))
        env["CLOUDFLARE_API_TOKEN"] = "present"
        proc = subprocess.run(["bash", SETUP], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Nothing was created", proc.stderr)
        self.assertFalse(os.path.exists(marker))

    def test_backup_branch_and_workflow_switch(self):
        tmp = tempfile.mkdtemp(prefix="nc-d1-git-")
        self.addCleanup(shutil.rmtree, tmp, True)
        bare = os.path.join(tmp, "bare.git")
        work = os.path.join(tmp, "work")
        _git(tmp, "init", "--bare", "-b", "main", bare)
        _git(tmp, "clone", bare, work)
        _git(work, "config", "user.name", "Test")
        _git(work, "config", "user.email", "test@example.com")
        with open(os.path.join(work, "README"), "w", encoding="utf-8") as fh:
            fh.write("base\n")
        _git(work, "add", "README")
        _git(work, "commit", "-m", "base")
        _git(work, "push", "origin", "HEAD:main")
        staged = os.path.join(work, "staged")
        os.makedirs(staged)
        with open(os.path.join(staged, "news.json"), "w", encoding="utf-8") as fh:
            json.dump({"items": [{"id": "a", "title": "Public"}]}, fh)
        env = os.environ.copy()
        env["NC_BACKUP_REPO"] = work
        proc = subprocess.run(["bash", BACKUP, staged, "2026-10-10"], cwd=work, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        shown = _git(bare, "show", "d1-backup:backup/2026-10-10/news.json")
        self.assertIn("Public", shown.stdout)
        names = _git(bare, "ls-tree", "-r", "--name-only", "d1-backup").stdout.splitlines()
        self.assertTrue(all(name.startswith("backup/") for name in names))
        self.assertNotIn("state/private_terms.json", names)
        bad = os.path.join(work, "bad-stage")
        os.makedirs(bad)
        with open(os.path.join(bad, "private_terms.json"), "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        refused = subprocess.run(["bash", BACKUP, bad, "2026-10-11"], cwd=work, env=env, capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0)
        self.assertNotIn(SECRET, refused.stdout + refused.stderr)

        nightly = open(os.path.join(ROOT, ".github", "workflows", "nightly-fetch.yml"), encoding="utf-8").read()
        publish = open(os.path.join(ROOT, ".github", "workflows", "d1-publish.yml"), encoding="utf-8").read()
        backup = open(os.path.join(ROOT, ".github", "workflows", "d1-backup.yml"), encoding="utf-8").read()
        deploy = open(os.path.join(ROOT, ".github", "workflows", "deploy.yml"), encoding="utf-8").read()
        self.assertIn("vars.NC_DATA_SOURCE != 'd1'", nightly)
        self.assertIn("vars.NC_DATA_SOURCE == 'd1'", nightly)
        self.assertIn("tools/d1_sync.py push", nightly)
        self.assertIn("tools/privacy_gate.py", nightly)
        self.assertIn("fetch-queue", nightly)
        self.assertIn("NC_DATA_SOURCE: d1", publish)
        self.assertIn("tools/privacy_gate.py site", publish)
        self.assertIn("tools/text_gate.py", publish)
        self.assertIn("d1-approved", publish)
        self.assertIn("group: gh-pages-deploy", publish)
        self.assertNotIn("set -x", publish)
        self.assertIn("tools/d1_backup.sh", backup)
        self.assertIn("CF_R2_BUCKET", backup)
        self.assertNotIn("wrangler r2 bucket create", backup)
        self.assertIn("NC_DATA_SOURCE: ${{ vars.NC_DATA_SOURCE }}", deploy)
        build = open(os.path.join(ROOT, "build.py"), encoding="utf-8").read()
        self.assertIn('NC_DATA_SOURCE", "").strip().lower() == "d1"', build)
        self.assertIn("apply_approvals.py", build)


if __name__ == "__main__":
    unittest.main()
