#!/usr/bin/env python3
"""Import data/news.json, data/events.json, archive/events.json and sources.json into D1.

Safe to run more than once. A second run with the same files writes nothing.
An approval already stored in D1, with a later reviewed_at, is not overwritten
by the older JSON.

  python3 tools/d1_import.py                  # remote, needs the token and ids
  python3 tools/d1_import.py --sqlite FILE    # local file, for a dry run
  python3 tools/d1_import.py --print-setup    # the commands, and nothing is created

Does not create the Cloudflare database. workers/content/README.md has that step.
Does not read or write state/private_terms.json.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import d1_store


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import Nordic Crypto JSON into D1")
    parser.add_argument("--sqlite", help="write a local SQLite file instead of D1")
    parser.add_argument("--root", default=ROOT, help="checkout to read (default: this repo)")
    parser.add_argument("--print-setup", action="store_true", help="print the Cloudflare commands and exit")
    parser.add_argument("--apply-schema", action="store_true", help="run the migration SQL on the remote database")
    args = parser.parse_args(argv)
    if args.print_setup:
        print(d1_store.SETUP_COMMANDS)
        return 0
    if args.sqlite:
        store = d1_store.open_sqlite(args.sqlite)
    else:
        missing = d1_store.missing_remote()
        if missing:
            print(d1_store.SETUP_COMMANDS, file=sys.stderr)
            print("missing " + ", ".join(missing), file=sys.stderr)
            return 2
        store = d1_store.open_remote()
        if args.apply_schema:
            d1_store.apply_schema(store)
    stats = d1_store.import_root(store, args.root)
    print(
        "d1 import: "
        f"stories {stats['stories']}, events {stats['events']}, "
        f"sources {stats['sources']}, event sources {stats['event_sources']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except d1_store.D1Error as ex:
        print("d1 import: " + str(ex), file=sys.stderr)
        raise SystemExit(1)
