#!/usr/bin/env python3
"""Exit 1 when the last fetch left most sources in error.

Reads state/source_status.json written by fetch.py. Does not import fetch.py.
A run with no rows is a failure. A run where 80% or more of the sources
errored is a failure. The grouped error lines are the summary.
"""
import json
import os
import sys

THRESHOLD = 0.8
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def assess(status, threshold=THRESHOLD):
    """Return (ok, summary). ok is false when there are no rows or the failure ratio is at least the threshold."""
    rows = []
    if isinstance(status, dict):
        for key, row in status.items():
            if isinstance(row, dict) and ("ok" in row or "error" in row):
                rows.append((str(key), row))
    if not rows:
        return False, "fetch health: no source results"
    failed = []
    for key, row in rows:
        err = str(row.get("error") or "").strip()
        if err or row.get("ok") is False:
            failed.append((key, err or "not ok"))
    ratio = len(failed) / len(rows)
    lines = [f"fetch health: {len(failed)}/{len(rows)} sources failed ({ratio:.0%})"]
    groups = {}
    for _key, err in failed:
        label = err.split("\n", 1)[0][:160]
        groups[label] = groups.get(label, 0) + 1
    for label, count in sorted(groups.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"  {count}  {label}")
    ok = ratio < threshold
    if not ok:
        lines.append(f"fetch health: failed ({ratio:.0%} >= {threshold:.0%})")
    return ok, "\n".join(lines)


def main():
    path = os.path.join(ROOT, "state", "source_status.json")
    try:
        with open(path, encoding="utf-8") as fh:
            status = json.load(fh)
    except FileNotFoundError:
        status = {}
    ok, text = assess(status)
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
