#!/usr/bin/env python3
"""Write a JSON backup of D1. Stories, events, sources, the review audit and source health.

Teasers, the HTML cache and the private term list are not written.
The privacy gate should be run on the output before it is committed.

  python3 tools/d1_export.py DEST
  python3 tools/d1_export.py DEST --sqlite FILE
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import d1_store


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export D1 to JSON")
    parser.add_argument("dest")
    parser.add_argument("--sqlite")
    args = parser.parse_args(argv)
    store = d1_store.open_sqlite(args.sqlite) if args.sqlite else d1_store.open_remote()
    manifest = d1_store.write_backup(store, args.dest)
    d1_store.assert_backup_dir(args.dest)
    print(
        "d1 export: "
        f"{manifest['stories']} stories, {manifest['events']} events, "
        f"{manifest['sources']} sources -> {args.dest}"
    )
    if manifest.get("omitted_documents"):
        print("omitted documents: " + ", ".join(manifest["omitted_documents"]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except d1_store.D1Error as ex:
        print("d1 export: " + str(ex), file=sys.stderr)
        raise SystemExit(1)
