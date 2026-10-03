#!/usr/bin/env python3
"""Merges the editor's decisions in queue/approved.json into data/news.json. Run automatically by build.py.
Only what is approved here is published. Org-chart approvals (approved.json -> org) are applied by tools/import_orgchart.py,
events by build.py (events.*), academia by tools/import_academia.py (status column of the researcher's list).

queue/approved.json -> items: [{"url": ..., "summary": "1–2 sentences IN ENGLISH, own words", "title_en": optional English headline,
                                "topics": [optional], "approved_by": "Nordic Crypto editor", "approved_at": "YYYY-MM-DD"}]
                       rejected: [{"url": ... | "title_contains": ..., "reason": ...}]   # kept out even when a feed finds them again"""
import json, os, sys, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = lambda *a: os.path.join(ROOT, *a)
def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
def save(p, d): json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def canon(url):
    p = urllib.parse.urlparse(url.strip())
    q = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))])
    p = p._replace(query=q)
    return p.netloc.lower().removeprefix("www.") + (p.path.rstrip("/") or "/") + ("?" + p.query if p.query else "")
ap = load(P("queue", "approved.json"), {})
news = load(P("data", "news.json"), {"items": []})
by = {canon(i["url"]): i for i in news["items"]}
n_pub = n_rej = 0; missing = []
for a in ap.get("items", []):
    it = by.get(canon(a["url"]))
    if not it: missing.append(a["url"]); continue
    s = (a.get("summary") or "").strip()
    if not s: print(f"warning: no summary for {a['url']}", file=sys.stderr); continue
    it.update(status="published", summary=s, approved_by=a.get("approved_by", "Nordic Crypto editor"), approved_at=a.get("approved_at"))
    for k in ("topics", "title_en", "source_name", "links", "country"):
        if a.get(k): it[k] = a[k]
    n_pub += 1
for r in ap.get("rejected", []):
    for it in news["items"]:
        if (r.get("url") and canon(r["url"]) == canon(it["url"])) or (r.get("title_contains") and r["title_contains"].lower() in it["title"].lower()):
            it.update(status="rejected", summary=None, reject_reason=r.get("reason")); n_rej += 1
approved = {canon(a["url"]) for a in ap.get("items", [])}
for it in news["items"]:  # anything published that is no longer approved is withdrawn
    if it.get("status") == "published" and canon(it["url"]) not in approved: it["status"] = "pending"
save(P("data", "news.json"), news)
q = load(P("queue", "review.json"), None)
if q:
    q["items_needing_summary"] = [x for x in q.get("items_needing_summary", []) if any(i["id"] == x["id"] and i["status"] == "pending" for i in news["items"])]
    save(P("queue", "review.json"), q)
print(f"approvals: {n_pub} stories published, {n_rej} rejected" + (f"; {len(missing)} approved URLs missing from news.json (run ./fetch.sh --add URL --country XX): {missing}" if missing else ""))
