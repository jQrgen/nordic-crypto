#!/usr/bin/env python3
"""Reader tips -> editor queue (nightly step, routines/nightly-fetch.sh). Never publishes anything.
Sources:
  0. Cloudflare D1 (tipworker/, the public intake): pulled by tipworker/pull.py, which uses import_rows() below.
  1. tipserver/tips.db (SQLite, written by tipserver/server.py): rows with status 'pending' become pending stories with
     origin 'reader tip #<id>'; the row is then marked 'imported' (or 'duplicate' / 'invalid') with imported_at + queue_item_id.
  2. Fallback: open GitHub issues labelled 'tip' (form .github/ISSUE_TEMPLATE/tip.yml) -> origin 'reader tip (GitHub #<n>)'.
     Issues are left open and are never commented on or closed automatically.
Dedup: normalised-URL check from tools/crosssite_handoff.py against ALL stories (incl. rejected) and approved.json.
Page metadata (title/date) is read only where robots.txt allows (fetch.page_meta). The tipster's name is NEVER copied
(not to news.json, not to the queue); the note is kept only in the local queue (tip_note_local_only), never published.
Usage: python3 tools/reader_tips.py [--dry-run] [--no-github]"""
import datetime as dt, importlib.util, json, os, re, sqlite3, subprocess, sys, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = lambda *a: os.path.join(ROOT, *a)
REPO = "jQrgen/nordic-crypto"; DB = os.environ.get("TIP_DB", P("tipserver", "tips.db"))
sys.path.insert(0, P("tools")); from crosssite_handoff import norm_url, strip_tracking  # noqa: E402
NOW = dt.datetime.now(dt.timezone.utc)

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
def save(p, d):
    t = p + ".tips.tmp"; json.dump(d, open(t, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(t, p)
def field(body, label):
    m = re.search(rf"^###\s*{re.escape(label)}[^\n]*\n+(.*?)(?=^###\s|\Z)", body or "", re.S | re.M)
    v = (m.group(1).strip() if m else ""); return "" if v == "_No response_" else v
def clean_url(raw):
    m = re.search(r"https?://[^\s<>()\"']+", raw or "")
    if not m: return None
    u = m.group(0).rstrip(".,;)"); host = (urllib.parse.urlparse(u).hostname or "").lower()
    return None if not host or "." not in host or host.endswith(("github.com", "github.io")) else u
def code(c):
    m = re.search(r"\b(NO|SE|DK|FI|IS)\b", (c or "").upper()); return m.group(1) if m else None

class Queue:
    def __init__(self, dry):
        spec = importlib.util.spec_from_file_location("nc_fetch", P("fetch.py")); self.F = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.F)
        self.dry = dry; self.newsf, self.qf = P("data", "news.json"), P("queue", "review.json")
        self.news = load(self.newsf, {"items": []}); self.q = load(self.qf, {"items_needing_summary": [], "candidate_entities": []})
        ap = load(P("queue", "approved.json"), {})
        self.have = {norm_url(i["url"]): i for i in self.news["items"]}
        self.rej = {norm_url(r["url"]) for r in ap.get("rejected", []) if r.get("url")} | {norm_url(a["url"]) for a in ap.get("items", []) if a.get("url")}
        self.added = []; self.skipped = []
    def add(self, raw_url, country, note, origin, created, fallback_title="", link=None):
        """Returns ('imported', item_id) | ('duplicate', item_id or None) | ('invalid', None)."""
        F = self.F; u = clean_url(raw_url)
        if not u: self.skipped.append((origin, "no usable article URL")); return "invalid", None
        c = norm_url(u)
        if c in self.have or c in self.rej:
            ex = self.have.get(c)
            if ex is not None and origin not in ex.setdefault("tips", []): ex["tips"].append(origin)
            self.skipped.append((origin, "already known" + (f" ({ex['status']})" if ex else ""))); return "duplicate", (ex or {}).get("id")
        url = strip_tracking(u); title, desc, date, meta = "", "", None, "ok"
        try: title, desc, date = F.page_meta(url)
        except Exception as ex: meta = f"metadata not read: {type(ex).__name__}: {ex}"[:160]
        out, oname = F.outlet_for(url, urllib.parse.urlparse(url).netloc.lower().removeprefix("www."))
        country = code(country) or F.country_of_url(url, F.SRC.get(out, {}).get("country"))
        it = {"id": F.iid(url), "url": url, "title": title or fallback_title or oname, "title_en": None,
              "source": out, "source_name": oname, "country": country, "language": F.LANG.get(country),
              "via": "reader-tip", "seen_via": ["reader-tip"], "published": (date or created).isoformat(),
              "fetched": NOW.isoformat(timespec="seconds"), "topics": F.topics_of(f"{title}. {desc}"), "matched": F.matches(f"{title}. {desc}"),
              "paywall": bool(F.SRC.get(out, {}).get("paywall", False)), "status": "pending", "summary": None, "origin": origin}
        self.news["items"].append(it); self.have[c] = it; self.added.append(it)
        row = {"id": it["id"], "country": country, "language": it["language"], "title": it["title"], "source": oname, "url": url,
               "published": it["published"], "origin": origin, "tip_note_local_only": (note or "")[:1000], "teaser_local_only": desc[:600],
               "metadata": meta, "check": "Reader tip: check relevance, date, title and country against the source before approving."}
        if link: row["tip_link"] = link
        self.q.setdefault("items_needing_summary", []).append(row)
        return "imported", it["id"]
    def finish(self):
        orig = {i["id"]: i for i in self.news["items"] if (i.get("origin") or "").startswith("reader tip")}
        for r in self.q.get("items_needing_summary", []):  # fetch.py may rebuild queue rows without origin
            if r.get("id") in orig and not r.get("origin"): r["origin"] = orig[r["id"]]["origin"]
        if not self.dry: save(self.newsf, self.news); save(self.qf, self.q)

def import_rows(Q, rows):
    """Pending tip rows (dicts/rows with id, created_at, url, country, note; from tipserver/tips.db or the D1 database of
    tipworker/) -> Q.add with origin 'reader tip #<id>'. Returns [(status, imported_at, queue_item_id, id)] for marking."""
    marks = []
    for r in rows:
        st, item = Q.add(r["url"], r["country"], r["note"] or "", f"reader tip #{r['id']}", dt.datetime.fromisoformat(r["created_at"]))
        marks.append((st, NOW.isoformat(timespec="seconds"), item, r["id"]))
    return marks

def from_db(Q):
    if not os.path.exists(DB): print("reader tips: no tipserver/tips.db yet"); return 0
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row
    rows = c.execute("SELECT id, created_at, url, country, note FROM tips WHERE status = 'pending' ORDER BY id").fetchall()  # name is never read
    marks = import_rows(Q, rows)
    if not Q.dry:
        Q.finish()  # queue is saved before the rows are marked, so a crash can at worst re-import (dedupe catches it)
        with c: c.executemany("UPDATE tips SET status = ?, imported_at = ?, queue_item_id = ? WHERE id = ? AND status = 'pending'", marks)
    c.close(); return len(rows)

def from_github(Q):
    try:
        out = subprocess.run(["gh", "issue", "list", "-R", REPO, "--label", "tip", "--state", "open", "--limit", "200",
                              "--json", "number,title,body,createdAt"], check=True, capture_output=True, text=True, timeout=60).stdout
    except Exception as ex: print(f"reader tips: GitHub fallback skipped ({type(ex).__name__})"); return 0
    issues = sorted(json.loads(out), key=lambda t: t["number"])
    for t in issues:
        Q.add(field(t["body"], "Article URL") or t["body"], field(t["body"], "Country"), field(t["body"], "Short note"),
              f"reader tip (GitHub #{t['number']})", dt.datetime.fromisoformat(t["createdAt"].replace("Z", "+00:00")),
              t["title"].removeprefix("Tip:").strip(), f"https://github.com/{REPO}/issues/{t['number']}")
    return len(issues)

if __name__ == "__main__":
    Q = Queue("--dry-run" in sys.argv)
    n_db = from_db(Q); n_gh = 0 if "--no-github" in sys.argv else from_github(Q)
    Q.finish()
    print(f"reader tips: {n_db} from tip server, {n_gh} open GitHub tip issues; {len(Q.added)} added as pending, {len(Q.skipped)} skipped" + (" (dry-run)" if Q.dry else ""))
    for a in Q.added: print(f"   + {a['origin']}: {a['country']} {a['source_name']}: {a['title'][:90]}")
    for o, why in Q.skipped: print(f"   - {o}: {why}")
