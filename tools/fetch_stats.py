#!/usr/bin/env python3
"""Visitor stats for the public /stats/ page and /api/v1/stats.json.

Source: Cloudflare Web Analytics (the cookie-free JS beacon), read through the GraphQL Analytics API
(rumPageloadEventsAdaptiveGroups, filtered by the site tag). Only aggregate counts per UTC day are kept:
visits and page views. No IP addresses, no user agents, no paths, no referrers, no countries.

Weeks (ISO, Monday first) and calendar months are derived from the daily rows. Days are UTC dates,
because that is how Cloudflare groups the `date` dimension.

Cloudflare keeps Web Analytics data for about six months, so each run merges the new days into the
rows already saved. The monthly table keeps growing after old days have expired at Cloudflare.

  python3 tools/fetch_stats.py                      # update data/stats.json
  python3 tools/fetch_stats.py --pages gh-pages     # also update gh-pages/api/v1/stats.json (scheduled job)
  python3 tools/fetch_stats.py --check              # print aggregate totals only, write nothing

Configuration (environment):
  CF_ANALYTICS_TOKEN   API token with Account > Account Analytics > Read (a secret; never printed)
  CF_ACCOUNT_ID        Cloudflare account id
  CF_WA_SITE_TAG       Web Analytics site tag of nordiccrypto.no (not the public beacon token)
Without all three the script prints "not configured" and exits 0 without touching any file.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "stats.json")
API_REL = os.path.join("api", "v1", "stats.json")
GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"
SOURCE = "Cloudflare Web Analytics"
SCHEMA = 1
NOTE = ("Aggregate counts from Cloudflare Web Analytics, which uses no cookies. visits is Cloudflare's visit count "
        "(a page view that arrives from another site or with no referrer); pageviews counts every page load. "
        "Days are UTC dates. Weeks are ISO weeks (Monday to Sunday). partial is true for a period that is not finished "
        "or that starts before the first day with data.")
DAILY_SHOWN = 30
WEEKLY_SHOWN = 26

QUERY = """query Stats($account: String!, $site: String!, $since: Date!, $until: Date!) {
  viewer { accounts(filter: {accountTag: $account}) {
    rumPageloadEventsAdaptiveGroups(limit: 1000, orderBy: [date_ASC],
      filter: {siteTag: $site, date_geq: $since, date_leq: $until}) {
      count
      sum { visits }
      dimensions { date }
    }
  } }
}"""
SETTINGS = """query Limits($account: String!) {
  viewer { accounts(filter: {accountTag: $account}) {
    settings { rumPageloadEventsAdaptiveGroups { notOlderThan maxDuration } }
  } }
}"""


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso_z(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty(status="pending"):
    return {"api_version": "1", "name": "Nordic Crypto", "generated_at": None, "preview": False,
            "source": SOURCE, "status": status, "timezone": "UTC", "note": NOTE, "schema": SCHEMA,
            "first_date": None, "last_date": None, "updated_at": None, "daily": [], "weekly": [], "monthly": []}


def _int(v):
    try:
        return max(0, int(v or 0))
    except (TypeError, ValueError):
        return 0


def clean_daily(rows):
    """{date: (visits, pageviews)} from any list of daily rows. Bad rows are dropped."""
    out = {}
    for r in rows or []:
        try:
            d = dt.date.fromisoformat(str(r.get("date")))
        except (TypeError, ValueError, AttributeError):
            continue
        out[d] = (_int(r.get("visits")), _int(r.get("pageviews")))
    return out


def derive(days, generated_at=None, until=None):
    """The public document from {date: (visits, pageviews)}. Missing days between the first day with data and
    `until` (the last day the query covered) are zero. Weeks and months are sums of the daily rows.
    The day of generated_at is still running, so that day, its week and its month are marked partial."""
    doc = empty("ok" if days else "pending")
    doc["generated_at"] = doc["updated_at"] = generated_at
    if not days:
        return doc
    try:
        today = dt.datetime.fromisoformat(str(generated_at).replace("Z", "+00:00")).astimezone(dt.timezone.utc).date()
    except ValueError:
        today = max(days) + dt.timedelta(days=1)
    first = min(days)
    last = max([max(days)] + ([until] if until else []))
    daily, weeks, months = [], {}, {}
    d = first
    while d <= last:
        v, p = days.get(d, (0, 0))
        daily.append({"date": d.isoformat(), "visits": v, "pageviews": p, **({"partial": True} if d >= today else {})})
        y, w, _ = d.isocalendar()
        wk = weeks.setdefault((y, w), {"week": f"{y}-W{w:02d}", "start": (d - dt.timedelta(days=d.weekday())).isoformat(),
                                        "days": 0, "visits": 0, "pageviews": 0})
        mo = months.setdefault((d.year, d.month), {"month": f"{d.year}-{d.month:02d}", "days": 0, "visits": 0, "pageviews": 0})
        for agg in (wk, mo):
            agg["days"] += 1
            agg["visits"] += v
            agg["pageviews"] += p
        d += dt.timedelta(days=1)
    for (y, w), wk in weeks.items():
        start = dt.date.fromisoformat(wk["start"])
        wk["end"] = (start + dt.timedelta(days=6)).isoformat()
        wk["partial"] = start < first or start + dt.timedelta(days=6) >= today
    for (y, m), mo in months.items():
        start = dt.date(y, m, 1)
        nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
        mo["partial"] = start < first or nxt > today
    doc.update(first_date=first.isoformat(), last_date=last.isoformat(), daily=daily,
               weekly=[weeks[k] for k in sorted(weeks)], monthly=[months[k] for k in sorted(months)])
    return doc


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def newest(*docs):
    """The document with the latest generated_at (None when none has data)."""
    have = [d for d in docs if d and d.get("daily")]
    return max(have, key=lambda d: d.get("generated_at") or "") if have else None


_LIVE = {}


def published(base, timeout=6):
    """The copy on the live site (refreshed on gh-pages by the scheduled job). None offline or with NC_STATS_LIVE=0."""
    if os.environ.get("NC_STATS_LIVE") == "0" or not base:
        return None
    url = base.rstrip("/") + "/api/v1/stats.json"
    if url not in _LIVE:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nordic-crypto-build", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                _LIVE[url] = json.load(r)
        except Exception:
            _LIVE[url] = None
    return _LIVE[url]


def current(base=None):
    """What the build shows: the newer of data/stats.json and the published copy, re-derived from its daily rows
    so weeks and months always match the days. A pending document when neither has data."""
    doc = newest(load(DATA), published(base))
    if not doc:
        return empty()
    try:
        until = dt.date.fromisoformat(str(doc.get("last_date")))
    except ValueError:
        until = None
    return derive(clean_daily(doc.get("daily")), generated_at=doc.get("generated_at"), until=until)


def _post(token, query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(GRAPHQL, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"stats: Cloudflare GraphQL HTTP {e.code}")
    if res.get("errors"):
        msgs = "; ".join(str(x.get("message"))[:200] for x in res["errors"])
        raise SystemExit(f"stats: Cloudflare GraphQL error: {msgs}")
    accounts = ((res.get("data") or {}).get("viewer") or {}).get("accounts") or []
    if not accounts:
        raise SystemExit("stats: the token cannot see that account")
    return accounts[0]


def fetch(token, account, site, days=400, today=None):
    """{date: (visits, pageviews)} for as many of the last `days` days as Cloudflare still keeps."""
    today = today or utc_now().date()
    lim = (_post(token, SETTINGS, {"account": account}).get("settings") or {}).get("rumPageloadEventsAdaptiveGroups") or {}
    keep_days = max(1, int(lim.get("notOlderThan") or 15552000) // 86400 - 1)
    span = max(1, int(lim.get("maxDuration") or 2678400) // 86400 - 1)
    since = max(today - dt.timedelta(days=days), today - dt.timedelta(days=keep_days))
    out = {}
    start = since
    while start <= today:
        end = min(today, start + dt.timedelta(days=span - 1))
        acc = _post(token, QUERY, {"account": account, "site": site, "since": start.isoformat(), "until": end.isoformat()})
        for r in acc.get("rumPageloadEventsAdaptiveGroups") or []:
            d = dt.date.fromisoformat(r["dimensions"]["date"])
            out[d] = (_int((r.get("sum") or {}).get("visits")), _int(r.get("count")))
        start = end + dt.timedelta(days=1)
    return out, since


def write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=DATA, help="daily file to merge into (default data/stats.json)")
    ap.add_argument("--pages", help="gh-pages checkout: also merge into and write <dir>/api/v1/stats.json")
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--check", action="store_true", help="print aggregate totals only; write nothing")
    a = ap.parse_args(argv)
    token = os.environ.get("CF_ANALYTICS_TOKEN", "").strip()
    account = os.environ.get("CF_ACCOUNT_ID", "").strip()
    site = os.environ.get("CF_WA_SITE_TAG", "").strip()
    if not (token and account and site):
        missing = [n for n, v in (("CF_ANALYTICS_TOKEN", token), ("CF_ACCOUNT_ID", account), ("CF_WA_SITE_TAG", site)) if not v]
        print(f"stats: not configured (missing {', '.join(missing)}); nothing written")
        return 0
    fresh, since = fetch(token, account, site, a.days)
    print(f"stats: {len(fresh)} days with data since {since}, visits {sum(v for v, _ in fresh.values())}, "
          f"page views {sum(p for _, p in fresh.values())}")
    if a.check:
        return 0
    targets = [a.out] + ([os.path.join(a.pages, API_REL)] if a.pages else [])
    days = {}
    for path in targets:          # keep days Cloudflare has already expired
        old = load(path) or {}
        days.update(clean_daily(old.get("daily")))
    for d in [d for d in days if d >= since]:
        days.pop(d)              # the fresh query is authoritative for the window it covered
    days.update(fresh)
    now = utc_now()
    doc = derive(days, generated_at=iso_z(now), until=now.date())
    for path in targets:
        write(path, doc)
        print(f"stats: wrote {os.path.relpath(path)} ({len(doc['daily'])} days, {len(doc['monthly'])} months)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
