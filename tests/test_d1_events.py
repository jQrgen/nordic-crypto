#!/usr/bin/env python3
"""Calendar events in D1 (0002_events.sql): translations, redirects, merged duplicates, approval carry-over.

  python3 -m unittest tests.test_d1_events
"""
import json, os, shutil, sqlite3, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import d1_store

AT = "2026-10-13T12:00:00+00:00"


def ev(i, title, **kw):
    return {"id": i, "title": title, "start": "2026-10-14T17:30:00+02:00", "end": "2026-10-14T18:30:00+02:00",
            "city": "Oslo", "country": "NO", "place": "Rosenkrantz' gate 7", "organiser": "PF",
            "url": "https://example.org/e", "status": "pending", **kw}


class EventsD1(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nc-d1ev-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.store = d1_store.open_sqlite(os.path.join(self.tmp, "c.sqlite"))

    def root(self, events, archive=None, items=None, redirects=None):
        r = os.path.join(self.tmp, "root"); shutil.rmtree(r, True)
        for d in ("data", "archive"): os.makedirs(os.path.join(r, d))
        d1_store.save_json(os.path.join(r, "data", "events.json"), {"events": events})
        d1_store.save_json(os.path.join(r, "archive", "events.json"), {"events": archive or []})
        d1_store.save_json(os.path.join(r, "data", "news.json"), {"items": []})
        d1_store.save_json(os.path.join(r, "data", "event_description_i18n.json"), {"items": items or {}})
        if redirects is not None: d1_store.save_json(os.path.join(r, "data", "event_redirects.json"), redirects)
        return r

    def test_schema_is_version_2_and_applies_twice(self):
        self.assertEqual(d1_store.schema_version(self.store), 2)
        d1_store.apply_schema(self.store)
        cols = {r["name"] for r in self.store.query("PRAGMA table_info(events)")}
        self.assertTrue({"end_at", "city", "merged_into", "origin", "submitted_by"} <= cols)
        tables = {r["name"] for r in self.store.query("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"event_translations", "event_redirects"} <= tables)

    def test_real_json_import_is_idempotent_and_keeps_translations_and_redirects(self):
        first = d1_store.import_root(self.store, ROOT, AT)
        self.assertGreater(first["event_translations"]["inserted"], 0)
        second = d1_store.import_root(self.store, ROOT, AT)
        self.assertEqual(second["event_translations"]["inserted"] + second["event_translations"]["updated"], 0)
        self.assertEqual(second["events"]["inserted"] + second["events"]["updated"], 0)
        self.assertEqual(second["event_redirects"]["inserted"], 0)
        items = json.load(open(os.path.join(ROOT, "data", "event_description_i18n.json"), encoding="utf-8"))["items"]
        self.assertEqual(d1_store.translations_items(self.store), {k: v for k, v in items.items() if any(l != "source" for l in v)})
        self.assertEqual(d1_store.redirects_map(self.store).get("89ced460e4ca"), "019f42a4506c")
        kept = d1_store.one(self.store, "SELECT origin, city, end_at FROM events WHERE id = '019f42a4506c'")
        self.assertEqual((kept["origin"], kept["city"]), ("import", "Oslo"))

    def test_merge_marks_old_row_and_carries_approval_and_note(self):
        old, new = ev("old111111111", "Crypto killer apps", note="Paid entry."), ev("new222222222", "Crypto killer apps: more")
        r = self.root([new], archive=[dict(old, status="published")])
        d1_store.import_root(self.store, r, AT)
        self.assertEqual(d1_store.one(self.store, "SELECT review_status FROM events WHERE id='old111111111'")["review_status"], "approved")
        d1_store.save_json(os.path.join(r, "data", "event_redirects.json"), {"old111111111": "new222222222"})
        d1_store.sync_root(self.store, r, AT)
        o = d1_store.one(self.store, "SELECT * FROM events WHERE id='old111111111'")
        n = d1_store.one(self.store, "SELECT * FROM events WHERE id='new222222222'")
        self.assertEqual((o["item_status"], o["merged_into"]), ("merged", "new222222222"))
        self.assertEqual(n["review_status"], "approved")
        self.assertEqual(json.loads(n["payload"])["note"], "Paid entry.")
        again = d1_store.sync_root(self.store, r, AT)
        self.assertEqual(again["event_redirects"]["merged"], 0)
        # build side: merged row is not published, kept row is approved, sidecars are written
        out = os.path.join(self.tmp, "build"); os.makedirs(os.path.join(out, "archive"))
        d1_store.save_json(os.path.join(out, "archive", "events.json"), {"events": []})
        self.store.execute("INSERT INTO stories (id, url, canonical_url, item_status, review_status, payload, content_hash, created_at, updated_at) VALUES ('s','u','u','published','approved','{}','h',?,?)", (AT, AT))
        approvals = d1_store.materialize(out, store=self.store, at=AT)
        ids = [e["id"] for e in json.load(open(os.path.join(out, "data", "events.json")))["events"]]
        self.assertEqual(ids, ["new222222222"])
        self.assertIn("new222222222", approvals["approve"]); self.assertNotIn("old111111111", approvals["approve"])
        self.assertEqual(json.load(open(os.path.join(out, "data", "event_redirects.json")))["old111111111"], "new222222222")

    def test_restore_does_not_bring_back_a_merged_row(self):
        r = self.root([ev("aaaaaaaaaaaa", "A"), ev("bbbbbbbbbbbb", "A: b")], redirects={"aaaaaaaaaaaa": "bbbbbbbbbbbb"})
        d1_store.import_root(self.store, r, AT)
        r2 = self.root([], redirects=None)
        d1_store.restore_root(self.store, r2)
        ids = [e["id"] for e in json.load(open(os.path.join(r2, "data", "events.json")))["events"]]
        self.assertEqual(ids, ["bbbbbbbbbbbb"])
        self.assertEqual(json.load(open(os.path.join(r2, "data", "event_redirects.json")))["aaaaaaaaaaaa"], "bbbbbbbbbbbb")

    def test_version_1_database_still_syncs(self):
        con = sqlite3.connect(os.path.join(self.tmp, "v1.sqlite")); con.executescript(open(d1_store.MIGRATION).read()); con.close()
        v1 = d1_store.SqliteStore(os.path.join(self.tmp, "v1.sqlite"))
        r = self.root([ev("cccccccccccc", "C")], redirects={"x": "cccccccccccc"})
        stats = d1_store.sync_root(v1, r, AT)
        self.assertEqual(stats["events"]["inserted"], 1)
        self.assertEqual(stats["event_redirects"]["inserted"], 0)

    def test_real_events_migrate_without_loss(self):
        d1_store.import_root(self.store, ROOT, AT)
        rows = {r["id"]: r for r in self.store.query("SELECT id, review_status FROM events")}
        data = json.load(open(os.path.join(ROOT, "data", "events.json"), encoding="utf-8"))["events"]
        archive = json.load(open(os.path.join(ROOT, "archive", "events.json"), encoding="utf-8"))["events"]
        self.assertEqual({e["id"] for e in data + archive} - set(rows), set())
        for e in archive:
            if e.get("status") == "published":
                self.assertEqual(rows[e["id"]]["review_status"], "approved", e["id"])

    def test_add_and_update_event_without_git(self):
        r = self.root([ev("dddddddddddd", "D")])
        d1_store.import_root(self.store, r, AT)
        fields = {"title": "Manual", "start": "2026-11-02T18:00:00+01:00", "place": "Vingtor",
                  "organiser": "KÅKÅ", "url": "https://example.org/m", "country": "NO"}
        plan = d1_store.plan_event_edit(None, fields, "Ed", AT, approve=True)
        d1_store.apply_event_edit(self.store, plan, "Ed", AT)
        row = d1_store.one(self.store, "SELECT * FROM events WHERE id = ?", (plan["id"],))
        self.assertEqual((row["review_status"], row["origin"]), ("approved", "manual"))
        upd = d1_store.plan_event_edit(row, {"end": "2026-11-02T19:00:00+01:00"}, "Ed", AT)
        d1_store.apply_event_edit(self.store, upd, "Ed", AT)
        row = d1_store.one(self.store, "SELECT * FROM events WHERE id = ?", (plan["id"],))
        self.assertEqual((row["review_status"], row["end_at"]), ("approved", "2026-11-02T19:00:00+01:00"))
        # an edit in D1 survives a re-import of the older git snapshot, and restore brings it back
        d1_store.apply_event_edit(self.store, d1_store.plan_event_edit(
            d1_store.one(self.store, "SELECT * FROM events WHERE id = 'dddddddddddd'"), {"title": "D edited"}, "Ed", AT), "Ed", AT)
        d1_store.import_root(self.store, r, AT)
        self.assertEqual(json.loads(d1_store.one(self.store, "SELECT payload FROM events WHERE id = 'dddddddddddd'")["payload"])["title"], "D edited")
        d1_store.restore_root(self.store, r)
        got = {e["id"]: e for e in json.load(open(os.path.join(r, "data", "events.json")))["events"]}
        self.assertEqual(got["dddddddddddd"]["title"], "D edited")
        self.assertIn(plan["id"], got)
        sql = d1_store.event_edit_sql(d1_store.plan_event_edit(None, dict(fields, title="Other"), "Ed", AT), "Ed")
        self.assertTrue(sql.startswith("INSERT INTO events"))
        self.store.executescript(sql)


if __name__ == "__main__":
    unittest.main()
