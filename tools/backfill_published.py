#!/usr/bin/env python3
"""Re-check publish times that were taken from a feed, an updated time, or another fallback.

For each story in data/news.json (including other outlets on the same story) and each row in
archive/articles.json, fetch the article page when robots.txt allows it and the host delay has
elapsed. Where the page's own publish time differs, store that UTC time. A page with no
publish time leaves the stored value as it is. Does not publish the site.

  python3 tools/backfill_published.py
  python3 tools/backfill_published.py --dry-run
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import fetch
import published_time as pub

NEWS = os.path.join(ROOT, "data", "news.json")
ARCHIVE = os.path.join(ROOT, "archive", "articles.json")
QUEUE = os.path.join(ROOT, "queue", "review.json")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def main():
    dry = "--dry-run" in sys.argv
    news = load(NEWS)
    archive = load(ARCHIVE) if os.path.exists(ARCHIVE) else {"articles": []}
    queue = load(QUEUE) if os.path.exists(QUEUE) else None
    # canon url -> first fetchable url, country, and the records that store this article's time
    groups = {}

    def add(url, country, obj, key, where, ident, title):
        if not url or not str(url).startswith("http"):
            return
        cu = fetch.canon(url)
        g = groups.setdefault(cu, {"url": url, "country": country, "rows": []})
        if country and not g.get("country"):
            g["country"] = country
        g["rows"].append({"obj": obj, "key": key, "where": where, "id": ident, "title": title})

    for item in news.get("items") or []:
        add(item.get("url"), item.get("country"), item, "published", "news", item.get("id"), item.get("title"))
        for ex in item.get("also_covered_by") or []:
            if isinstance(ex, dict):
                add(ex.get("url"), ex.get("country"), ex, "published", "also_covered_by", item.get("id"), ex.get("title"))
    for art in archive.get("articles") or []:
        add(art.get("url"), art.get("country"), art, "published_at", "archive", art.get("id"), art.get("title"))

    corrections = []
    skipped = {"robots": 0, "error": 0, "no_page_time": 0, "same": 0}
    for cu, g in groups.items():
        url, country = g["url"], g.get("country")
        zone = pub.zone_for(country=country, url=url)
        if not fetch.robots_ok(url):
            skipped["robots"] += 1
            fetch.log("BACKFILL robots", url[:110])
            continue
        try:
            html = fetch.read_html(url)
        except Exception as ex:
            skipped["error"] += 1
            fetch.log("BACKFILL err", type(ex).__name__, url[:110])
            continue
        page = pub.published_from_html(html, zone)
        if page is None:
            skipped["no_page_time"] += 1
            continue
        changed_here = False
        for row in g["rows"]:
            old = row["obj"].get(row["key"])
            stored = pub.parse_instant(old, zone) if old else None
            if stored:
                stored.source = "stored"
            chosen = pub.choose_published(page, stored)
            new = pub.utc_iso(chosen)
            old_norm = pub.utc_iso(stored) if stored else old
            if not new or new == old_norm:
                continue
            changed_here = True
            corrections.append({
                "id": row["id"],
                "where": row["where"],
                "title": row["title"],
                "url": url,
                "old": old,
                "new": new,
                "source": page.source,
            })
            if not dry:
                row["obj"][row["key"]] = new
            fetch.log(f"BACKFILL {old} -> {new} ({page.source}) {row['id']} {url[:90]}")
        if not changed_here:
            skipped["same"] += 1

    if corrections and not dry:
        news["items"].sort(key=lambda i: i.get("published") or "", reverse=True)
        save(NEWS, news)
        if os.path.exists(ARCHIVE):
            save(ARCHIVE, archive)
        if queue:
            by_id = {c["id"]: c["new"] for c in corrections if c["where"] == "news"}
            for q in queue.get("items_needing_summary") or []:
                if q.get("id") in by_id:
                    q["published"] = by_id[q["id"]]
            save(QUEUE, queue)
    print(json.dumps({"dry_run": dry, "corrected": corrections, "skipped": skipped}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
