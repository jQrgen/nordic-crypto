#!/usr/bin/env python3
"""Fetch health: fail when most sources error. No network."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import fetch_health

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    rows = {f"s{i}": {"ok": False, "error": "FeatureNotFound: lxml parser not found"} for i in range(12)}
    ok, text = fetch_health.assess(rows)
    check(not ok and "12/12" in text and "FeatureNotFound: lxml parser not found" in text, "every source in error fails")

    mixed = {f"s{i}": {"ok": True, "error": None} for i in range(50)}
    mixed["bad"] = {"ok": False, "error": "HTTP 500"}
    ok, text = fetch_health.assess(mixed)
    check(ok and "1/51" in text, "one failure does not fail the run")

    ok, text = fetch_health.assess({})
    check(not ok and "no source results" in text, "empty status fails")

    if fails:
        print(f"{len(fails)} failed")
        sys.exit(1)
    print("fetch health ok")


if __name__ == "__main__":
    main()
