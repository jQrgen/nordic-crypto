#!/usr/bin/env python3
"""Visitor stats: weeks and months derived from daily rows, merging, the pending state and the API file.
No network and no Cloudflare token.
  python3 tests/test_stats.py
"""
import datetime as dt
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["NC_STATS_LIVE"] = "0"
import fetch_stats as F  # noqa: E402

D = dt.date


def main():
    fails = []
    days = {D(2026, 9, 28): (3, 5), D(2026, 10, 6): (20, 21)}
    doc = F.derive(days, generated_at="2026-10-08T03:00:00Z", until=D(2026, 10, 8))
    if doc["status"] != "ok" or doc["first_date"] != "2026-09-28" or doc["last_date"] != "2026-10-08":
        fails.append(f"range {doc['first_date']}..{doc['last_date']} {doc['status']}")
    if len(doc["daily"]) != 11 or doc["daily"][-2] != {"date": "2026-10-07", "visits": 0, "pageviews": 0}:
        fails.append("missing days are not zero-filled")
    if not doc["daily"][-1].get("partial") or doc["daily"][-3].get("partial"):
        fails.append("only the running UTC day is partial")
    w = {r["week"]: r for r in doc["weekly"]}
    if w["2026-W40"]["visits"] != 3 or w["2026-W40"]["partial"] or w["2026-W41"]["pageviews"] != 21 or not w["2026-W41"]["partial"]:
        fails.append(f"weeks {doc['weekly']}")
    if w["2026-W41"]["start"] != "2026-10-05" or w["2026-W41"]["end"] != "2026-10-11":
        fails.append("ISO week bounds")
    m = {r["month"]: r for r in doc["monthly"]}
    if m["2026-09"]["visits"] != 3 or not m["2026-09"]["partial"] or m["2026-10"]["visits"] != 20:
        fails.append(f"months {doc['monthly']}")
    if sum(r["visits"] for r in doc["daily"]) != sum(r["visits"] for r in doc["monthly"]):
        fails.append("monthly sums differ from daily")

    allowed = {"date", "visits", "pageviews", "partial"}
    if any(set(r) - allowed for r in doc["daily"]):
        fails.append("daily rows carry more than aggregate counts")

    pending = F.derive({}, None)
    if pending["status"] != "pending" or pending["daily"] or pending["updated_at"] is not None:
        fails.append("pending document")

    if F.clean_daily([{"date": "bad"}, {"date": "2026-10-01", "visits": "-4", "pageviews": "7"}]) != {D(2026, 10, 1): (0, 7)}:
        fails.append("clean_daily")

    newer = dict(doc, generated_at="2026-10-09T03:00:00Z")
    if F.newest(doc, newer, None, F.empty()) is not newer:
        fails.append("newest picks the latest generated_at")

    old = os.environ.pop("CF_ANALYTICS_TOKEN", None)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "stats.json")
        if F.main(["--out", out]) != 0 or os.path.exists(out):
            fails.append("unconfigured run must write nothing")
        import api_feed
        feed = api_feed.Feed(tmp, False, "https://nordiccrypto.no/")
        body = api_feed._stats(feed, doc)
        on_disk = json.load(open(os.path.join(tmp, "api", "v1", "stats.json"), encoding="utf-8"))
        if on_disk["generated_at"] != "2026-10-08T03:00:00Z" or on_disk["daily"] != doc["daily"] or body["status"] != "ok":
            fails.append("api/v1/stats.json")
        if [e["id"] for e in feed.endpoints] != ["stats"]:
            fails.append("stats endpoint not registered")
    if old is not None:
        os.environ["CF_ANALYTICS_TOKEN"] = old

    if fails:
        print("FAIL:\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("stats: OK")


if __name__ == "__main__":
    main()
