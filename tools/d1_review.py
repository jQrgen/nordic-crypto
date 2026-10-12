#!/usr/bin/env python3
"""Approve or reject a story or an event in D1. No git commit.

The default reads and writes the remote database with wrangler d1 execute.
--api uses the Cloudflare HTTP API (CLOUDFLARE_API_TOKEN, CF_ACCOUNT_ID, CF_D1_DATABASE_ID).
--sqlite FILE applies the same decision to a local file (tests and a dry run).

  python3 tools/d1_review.py pending
  python3 tools/d1_review.py approve --id STORY --summary "Two to four sentences." --by "Nordic Crypto redaktør"
  python3 tools/d1_review.py reject --id STORY --reason "Not about crypto in the Nordics."
  python3 tools/d1_review.py approve-event --id EVENT --note "Paid entry."
  python3 tools/d1_review.py reject-event --id EVENT --reason "No Nordic link."
"""
import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import d1_store

WORKER = os.path.join(ROOT, "workers", "content")


def _actor(args):
    return args.by or os.environ.get("NC_EDITOR") or d1_store.DEFAULT_ACTOR


def _open(args):
    if args.sqlite:
        return d1_store.open_sqlite(args.sqlite)
    if args.api:
        return d1_store.open_remote()
    return None


def parse_wrangler_json(text):
    """Wrangler prints a JSON array. Log lines may sit above it."""
    raw = text or ""
    start = raw.find("[")
    brace = raw.find("{")
    if start < 0 or (brace >= 0 and brace < start):
        start = brace
    if start < 0:
        raise d1_store.D1Error("wrangler returned no JSON")
    try:
        data = json.loads(raw[start:])
    except json.JSONDecodeError:
        raise d1_store.D1Error("wrangler returned JSON that could not be read") from None
    if isinstance(data, list):
        if not data:
            return []
        first = data[0] or {}
        if isinstance(first, dict) and "results" in first:
            return first.get("results") or []
        return data
    if isinstance(data, dict):
        return data.get("results") or []
    return []


def run_wrangler(sql, cwd=None):
    """Execute SQL via wrangler d1. Returns stdout. The token stays in the environment."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8")
    path = handle.name
    try:
        handle.write(sql)
        handle.flush()
        os.fchmod(handle.fileno(), stat.S_IRUSR | stat.S_IWUSR)
        handle.close()
        cmd = d1_store.wrangler_command(path)
        proc = subprocess.run(cmd, cwd=cwd or WORKER, text=True, capture_output=True)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if proc.returncode != 0:
        err = proc.stderr or ""
        sys.stderr.write(err)
        if "not found" in err.lower() or "No such file" in err:
            sys.stderr.write(d1_store.SETUP_COMMANDS)
        raise d1_store.D1Error("wrangler d1 execute failed")
    return proc.stdout or ""


def wrangler_rows(sql):
    return parse_wrangler_json(run_wrangler(sql))


def _print_pending(stories, events):
    print(f"pending stories: {len(stories)}")
    for row in stories:
        print(f"  story {row['id']}  {row.get('country') or ''}  {row.get('title') or ''}")
    print(f"pending events: {len(events)}")
    for row in events:
        print(f"  event {row['id']}  {row.get('country') or ''}  {row.get('title') or ''}")


def _note_i18n(raw):
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise d1_store.D1Error("--note-i18n must be a JSON object") from None
    if not isinstance(data, dict):
        raise d1_store.D1Error("--note-i18n must be a JSON object")
    return data


def _load_story(store, story_id):
    if store is not None:
        row = d1_store.one(store, "SELECT * FROM stories WHERE id = ?", (story_id,))
    else:
        rows = wrangler_rows("SELECT * FROM stories WHERE id = " + d1_store.sql_quote(story_id) + ";\n")
        row = rows[0] if rows else None
    if not row:
        raise d1_store.D1Error("no story " + str(story_id))
    return row


def _load_event(store, event_id):
    if store is not None:
        row = d1_store.one(store, "SELECT * FROM events WHERE id = ?", (event_id,))
    else:
        rows = wrangler_rows("SELECT * FROM events WHERE id = " + d1_store.sql_quote(event_id) + ";\n")
        row = rows[0] if rows else None
    if not row:
        raise d1_store.D1Error("no event " + str(event_id))
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review a Nordic Crypto story or event in D1")
    parser.add_argument("command", choices=("pending", "approve", "reject", "approve-event", "reject-event"))
    parser.add_argument("--id", help="story id or event id")
    parser.add_argument("--summary", help="English summary, own words (required to approve a story)")
    parser.add_argument("--reason", help="why it was rejected")
    parser.add_argument("--by", help="who decided (default: Nordic Crypto redaktør, or NC_EDITOR)")
    parser.add_argument("--note", help="editor note stored on an event")
    parser.add_argument("--note-i18n", help="JSON object of language code to note text")
    parser.add_argument("--title-en", help="English headline when the source headline is in another language")
    parser.add_argument("--sqlite", help="apply to this SQLite file instead of wrangler")
    parser.add_argument("--api", action="store_true", help="use the Cloudflare HTTP API instead of wrangler")
    parser.add_argument("--print-sql", action="store_true", help="print the SQL and do not run the write")
    args = parser.parse_args(argv)
    store = _open(args)
    actor = _actor(args)

    if args.command == "pending":
        if store is not None:
            _print_pending(d1_store.pending_stories(store), d1_store.pending_events(store))
            return 0
        stories = wrangler_rows(
            "SELECT id, title, country, url, published_at FROM stories "
            "WHERE review_status = 'pending' AND item_status = 'pending' "
            "ORDER BY published_at DESC;\n"
        )
        events = wrangler_rows(
            "SELECT id, title, country, url, start_at FROM events "
            "WHERE review_status = 'pending' AND item_status = 'pending' "
            "ORDER BY start_at;\n"
        )
        _print_pending(stories, events)
        return 0

    if not args.id:
        print("d1 review: --id is required", file=sys.stderr)
        return 2

    if args.command in ("approve", "reject"):
        if args.command == "approve" and not (args.summary or "").strip():
            raise d1_store.D1Error("a story approval needs a summary")
        row = _load_story(store, args.id)
        extra = {"title_en": args.title_en} if args.title_en else None
        plan = d1_store.plan_story_review(
            row, "approve" if args.command == "approve" else "reject",
            args.summary, args.reason, actor, d1_store.now_iso(), extra,
        )
        sql = d1_store.story_sql(plan)
        if args.print_sql:
            print(sql)
            return 0
        if store is not None:
            d1_store.apply_story_plan(store, plan, actor, plan["reviewed_at"])
        else:
            run_wrangler(sql)
        print(f"d1 review: story {args.id} {plan['review_status']} by {plan['reviewed_by']} at {plan['reviewed_at']}")
        return 0

    note_i18n = _note_i18n(args.note_i18n)
    row = _load_event(store, args.id)
    plan = d1_store.plan_event_review(
        row, "approve" if args.command == "approve-event" else "reject",
        actor, d1_store.now_iso(), note=args.note, note_i18n=note_i18n, reason=args.reason,
    )
    sql = d1_store.event_sql(plan)
    if args.print_sql:
        print(sql)
        return 0
    if store is not None:
        d1_store.apply_event_plan(store, plan, actor, plan["reviewed_at"])
    else:
        run_wrangler(sql)
    print(f"d1 review: event {args.id} {plan['review_status']} by {plan['reviewed_by']} at {plan['reviewed_at']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except d1_store.D1Error as ex:
        print("d1 review: " + str(ex), file=sys.stderr)
        raise SystemExit(1)
