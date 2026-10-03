#!/usr/bin/env python3
"""Append-only article archive (rows are never deleted) of every story Nordic Crypto has ever published.
  archive/articles.db    SQLite (gitignored). Schema: archive/schema.sql – shared with Kryptonytt (site column tells them apart),
                         plus the additive v2 column `country`. Mirrors to Cloudflare D1 via tipworker/migrations/0002_articles.sql.
  archive/articles.json  export committed to the repo as a backup (the internal `origin` note is left out).
A story that later disappears from the site gets removed = 1, removed_at and (if known) removal_reason – the row stays.
Summary variants: summaries {lang: text} – "en" (written first) plus the editor-approved translations (nn, nb, sv, da, fi, is);
an older variant is kept if it later falls away. Only stories with status "published" are recorded (never preview/pending).
Usage:
  python3 tools/article_archive.py record [--at ISO]   # morning routine, after a successful publish: reads site/data/news.json
  python3 tools/article_archive.py backfill            # gh-pages history (origin/gh-pages, else .publish/) + queue/approved.json
  python3 tools/article_archive.py export
  python3 tools/article_archive.py count
"""
import json, os, sqlite3, subprocess, sys, urllib.parse, datetime as dt
from zoneinfo import ZoneInfo
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = lambda *a: os.path.join(ROOT, *a)
SITE_ID = "nordic-crypto"; DB = P("archive", "articles.db"); OSLO = ZoneInfo("Europe/Oslo")
LANGS = ["en", "nn", "nb", "sv", "da", "fi", "is"]
TRACK = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref_src", "_hsenc", "_hsmi", "yclid", "msclkid")
def canon(u):  # same normalisation as Kryptonytt, so the two archives can be joined on canonical_url
    p = urllib.parse.urlsplit(u.strip()); host = (p.hostname or "").lower().removeprefix("www.")
    q = sorted((k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith(TRACK))
    return urllib.parse.urlunsplit(("https", host, p.path.rstrip("/") or "/", urllib.parse.urlencode(q), ""))
def now(): return dt.datetime.now(OSLO).isoformat(timespec="seconds")
def db():
    os.makedirs(P("archive"), exist_ok=True); c = sqlite3.connect(DB); c.executescript(open(P("archive", "schema.sql"), encoding="utf-8").read())
    if "country" not in {r[1] for r in c.execute("PRAGMA table_info(articles)")}: c.execute("ALTER TABLE articles ADD COLUMN country TEXT")
    return c
def variants(it):
    s = {}
    if (it.get("summary") or "").strip(): s["en"] = it["summary"]
    for k, v in (it.get("summary_i18n") or {}).items():
        if k in LANGS and (v or "").strip(): s[k] = v
    t = {"en": it["title_en"]} if it.get("title_en") else {}
    return s, t
def topics(it):
    tp = it.get("topics") or []
    return tp if isinstance(tp, list) else []
def published(it): return it.get("status", "published") == "published" and it.get("summary")
def upsert(c, it, at, origin=None, ev="published"):
    s, t = variants(it); langs = sorted(s, key=LANGS.index)
    row = c.execute("SELECT removed, summaries FROM articles WHERE site=? AND id=?", (SITE_ID, it["id"])).fetchone()
    if row is None:
        c.execute("""INSERT INTO articles (site,id,url,canonical_url,title,source,source_name,published_at,first_published_on_site,last_seen_on_site,languages,summaries,titles,topics,origin,updated_at,country)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (SITE_ID, it["id"], it["url"], canon(it["url"]), it["title"], it.get("source"), it.get("source_name"), it.get("published"), at, at,
                   json.dumps(langs), json.dumps(s, ensure_ascii=False), json.dumps(t, ensure_ascii=False), json.dumps(topics(it)), origin, now(), it.get("country")))
        c.execute("INSERT INTO article_events (site,id,at,event) VALUES (?,?,?,?)", (SITE_ID, it["id"], at, ev)); return "new"
    old = json.loads(row[1]); merged = {**old, **s}
    c.execute("""UPDATE articles SET url=?, canonical_url=?, title=?, source=?, source_name=?, published_at=COALESCE(?, published_at), last_seen_on_site=?,
                 languages=?, summaries=?, titles=?, topics=?, origin=COALESCE(?, origin), country=COALESCE(?, country), removed=0, updated_at=? WHERE site=? AND id=?""",
              (it["url"], canon(it["url"]), it["title"], it.get("source"), it.get("source_name"), it.get("published"), at,
               json.dumps(sorted(merged, key=LANGS.index)), json.dumps(merged, ensure_ascii=False), json.dumps(t, ensure_ascii=False), json.dumps(topics(it)),
               origin, it.get("country"), now(), SITE_ID, it["id"]))
    if row[0]: c.execute("INSERT INTO article_events (site,id,at,event) VALUES (?,?,?,?)", (SITE_ID, it["id"], at, "republished"))
    elif merged != old: c.execute("INSERT INTO article_events (site,id,at,event,detail) VALUES (?,?,?,?,?)", (SITE_ID, it["id"], at, "updated", "summaries"))
    return "updated"
def mark_removed(c, live_ids, at, reason=None):
    n = 0
    for (aid,) in c.execute("SELECT id FROM articles WHERE site=? AND removed=0", (SITE_ID,)).fetchall():
        if aid not in live_ids:
            c.execute("UPDATE articles SET removed=1, removed_at=?, removal_reason=COALESCE(?, removal_reason), updated_at=? WHERE site=? AND id=?", (at, reason, now(), SITE_ID, aid))
            c.execute("INSERT INTO article_events (site,id,at,event,detail) VALUES (?,?,?,?,?)", (SITE_ID, aid, at, "removed", reason)); n += 1
    return n
def approved():
    try: return json.load(open(P("queue", "approved.json"), encoding="utf-8"))
    except FileNotFoundError: return {}
def origins():  # internal note (e.g. "reader tip"): stored in the db, never exported
    return {i["url"]: i.get("origin") for i in approved().get("items", []) if i.get("origin")}
def reasons():
    return {r["url"]: r.get("reason") for r in approved().get("rejected", []) if r.get("url")}
def finish(c, label):
    by_url = {r[1]: r[0] for r in c.execute("SELECT id, url FROM articles WHERE site=?", (SITE_ID,))}
    for u, o in origins().items():
        if u in by_url: c.execute("UPDATE articles SET origin=COALESCE(origin, ?) WHERE site=? AND id=?", (o, SITE_ID, by_url[u]))
    for u, why in reasons().items():
        if u in by_url: c.execute("UPDATE articles SET removal_reason=COALESCE(removal_reason, ?) WHERE site=? AND id=? AND removed=1", (why, SITE_ID, by_url[u]))
    c.commit(); export(c); print(f"archive {label}: {c.execute('SELECT COUNT(*) FROM articles WHERE site=?', (SITE_ID,)).fetchone()[0]} rows "
                              f"({c.execute('SELECT COUNT(*) FROM articles WHERE site=? AND removed=1', (SITE_ID,)).fetchone()[0]} marked removed)")
def record(path, at):
    data = json.load(open(path, encoding="utf-8"))
    if data.get("preview") or os.path.exists(P("site", ".preview")): sys.exit("archive: refusing to record a preview build")
    items = [i for i in data["items"] if published(i)]; c = db(); stats = {"new": 0, "updated": 0}
    for it in items: stats[upsert(c, it, at)] += 1
    rem = mark_removed(c, {i["id"] for i in items}, at)
    print(f"archive: {stats['new']} new, {stats['updated']} updated, {rem} marked removed"); finish(c, "after record")
def backfill():
    c = db(); src = None
    for repo, ref in ((ROOT, "origin/gh-pages"), (P(".publish"), "HEAD")):
        try: subprocess.check_output(["git", "-C", repo, "rev-parse", "--verify", ref], stderr=subprocess.DEVNULL); src = (repo, ref); break
        except (subprocess.CalledProcessError, FileNotFoundError): pass
    if src:
        repo, ref = src
        log = subprocess.check_output(["git", "-C", repo, "log", "--reverse", "--format=%H %cI", ref, "--", "data/news.json"], text=True).split("\n")
        for line in filter(None, log):
            sha, at = line.split(" ", 1)
            try: data = json.loads(subprocess.check_output(["git", "-C", repo, "show", f"{sha}:data/news.json"], text=True, stderr=subprocess.DEVNULL))
            except subprocess.CalledProcessError: continue
            if data.get("preview"): continue
            at = dt.datetime.fromisoformat(at).astimezone(OSLO).isoformat(timespec="seconds")
            items = [i for i in data["items"] if published(i)]
            for it in items: upsert(c, it, at, None, "backfill")
            mark_removed(c, {i["id"] for i in items}, at)
            print(f"gh-pages {sha[:7]} {at}: {len(items)} published stories")
    finish(c, "after backfill")
def export(c=None):
    c = c or db(); c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute("SELECT * FROM articles WHERE site=? ORDER BY first_published_on_site, id", (SITE_ID,))]
    for r in rows:
        for k in ("languages", "summaries", "titles", "topics"): r[k] = json.loads(r[k])
        r.pop("origin", None)
    ev = [dict(r) for r in c.execute("SELECT * FROM article_events WHERE site=? ORDER BY seq", (SITE_ID,))]
    json.dump({"schema": 2, "site": SITE_ID, "exported_at": now(), "articles": rows, "events": ev}, open(P("archive", "articles.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "record"
    if cmd == "record": record(P("site", "data", "news.json"), sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "--at" else now())
    elif cmd == "backfill": backfill()
    elif cmd == "export": export(); print("exported")
    elif cmd == "count": print(db().execute("SELECT COUNT(*) FROM articles WHERE site=?", (SITE_ID,)).fetchone()[0])
