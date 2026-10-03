#!/usr/bin/env python3
"""Reader tips: open GitHub issues labelled 'tip' (form: .github/ISSUE_TEMPLATE/tip.yml) -> editor queue.
  default         : each tip URL is added to data/news.json + queue/review.json as status 'pending' with origin 'reader tip #N'.
                    Dedup with the normalised-URL check from tools/crosssite_handoff.py against ALL stories (also rejected)
                    and approved.json (items + rejected). Never publishes; issues stay open – the editor decides.
                    Page metadata (title/date) is read only where robots.txt allows (fetch.page_meta). The reader's name is
                    never copied; the note is kept in the queue only (never published).
  --close-decided : after the morning publish: comment (neutral text, no personal data) and close open tips whose story the
                    editor has published or rejected. Undecided tips are left alone.
Uses the gh CLI (same login as publish.sh).  Usage: python3 tools/reader_tips.py [--dry-run] [--close-decided]"""
import datetime as dt, importlib.util, json, os, re, subprocess, sys, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = lambda *a: os.path.join(ROOT, *a)
REPO = "jQrgen/nordic-crypto"; SITE = "https://jqrgen.github.io/nordic-crypto/"
sys.path.insert(0, P("tools")); from crosssite_handoff import norm_url, strip_tracking  # noqa: E402
NOW = dt.datetime.now(dt.timezone.utc)
CODES = {"NO", "SE", "DK", "FI", "IS"}

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
def save(p, d):
    t = p + ".tips.tmp"; json.dump(d, open(t, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(t, p)
def gh(*a): return subprocess.run(["gh", *a], check=True, capture_output=True, text=True).stdout
def open_tips():
    return json.loads(gh("issue", "list", "-R", REPO, "--label", "tip", "--state", "open", "--limit", "200", "--json", "number,title,body,createdAt"))
def field(body, label):
    m = re.search(rf"^###\s*{re.escape(label)}[^\n]*\n+(.*?)(?=^###\s|\Z)", body or "", re.S | re.M)
    v = (m.group(1).strip() if m else "")
    return "" if v == "_No response_" else v
def tip_url(t):
    raw = field(t["body"], "Article URL") or (t["body"] or "")
    m = re.search(r"https?://[^\s<>()\"']+", raw)
    if not m: return None
    u = m.group(0).rstrip(".,;)")
    host = (urllib.parse.urlparse(u).hostname or "").lower()
    return None if not host or host.endswith(("github.com", "github.io")) else u

def import_tips(dry):
    spec = importlib.util.spec_from_file_location("nc_fetch", P("fetch.py")); F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
    newsf, qf = P("data", "news.json"), P("queue", "review.json")
    news = load(newsf, {"items": []}); q = load(qf, {"items_needing_summary": [], "candidate_entities": []}); ap = load(P("queue", "approved.json"), {})
    have = {norm_url(i["url"]): i for i in news["items"]}
    rej = {norm_url(r["url"]) for r in ap.get("rejected", []) if r.get("url")}
    added, skipped = [], []
    for t in sorted(open_tips(), key=lambda t: t["number"]):
        n = t["number"]; origin = f"reader tip #{n}"; u = tip_url(t)
        if not u: skipped.append((n, "no usable article URL")); continue
        c = norm_url(u)
        if c in have or c in rej:
            ex = have.get(c)
            if ex is not None and origin not in ex.setdefault("tips", []): ex["tips"].append(origin)  # remember the tip on the existing story
            skipped.append((n, "already known" + (f" ({ex['status']})" if ex else " (rejected)"))); continue
        url = strip_tracking(u); title, desc, date, meta = "", "", None, "ok"
        try: title, desc, date = F.page_meta(url)
        except Exception as ex: meta = f"metadata not read: {type(ex).__name__}: {ex}"[:160]
        cfield = field(t["body"], "Country"); cm = re.search(r"\((NO|SE|DK|FI|IS)\)", cfield)
        out, oname = F.outlet_for(url, urllib.parse.urlparse(url).netloc.lower().removeprefix("www."))
        country = cm.group(1) if cm else F.country_of_url(url, F.SRC.get(out, {}).get("country"))
        it = {"id": F.iid(url), "url": url, "title": title or (t["title"].removeprefix("Tip:").strip() or oname), "title_en": None,
              "source": out, "source_name": oname, "country": country, "language": F.LANG.get(country),
              "via": "reader-tip", "seen_via": ["reader-tip"], "published": (date or dt.datetime.fromisoformat(t["createdAt"].replace("Z", "+00:00"))).isoformat(),
              "fetched": NOW.isoformat(timespec="seconds"), "topics": F.topics_of(f"{title}. {desc}"), "matched": F.matches(f"{title}. {desc}"),
              "paywall": bool(F.SRC.get(out, {}).get("paywall", False)), "status": "pending", "summary": None,
              "origin": origin, "tip_issue": n}
        news["items"].append(it); have[c] = it; added.append(it)
        q.setdefault("items_needing_summary", []).append({"id": it["id"], "country": country, "language": it["language"], "title": it["title"],
            "source": oname, "url": url, "published": it["published"], "origin": origin, "tip_issue_url": f"https://github.com/{REPO}/issues/{n}",
            "tip_note_local_only": field(t["body"], "Short note")[:500], "teaser_local_only": desc[:600], "metadata": meta,
            "check": "Reader tip: check relevance, date and title against the source; no country/date guess is trusted."})
    # fetch.py may rebuild queue rows without origin: restore it from news.json
    orig = {i["id"]: i for i in news["items"] if (i.get("origin") or "").startswith("reader tip")}
    for r in q.get("items_needing_summary", []):
        if r.get("id") in orig and not r.get("origin"): r["origin"] = orig[r["id"]]["origin"]
    if not dry: save(newsf, news); save(qf, q)
    print(f"reader tips: {len(added)} added as pending, {len(skipped)} skipped" + (" (dry-run)" if dry else ""))
    for a in added: print(f"   + #{a['tip_issue']} {a['country']} {a['source_name']}: {a['title'][:90]}")
    for n, why in skipped: print(f"   - #{n}: {why}")

def close_decided(dry):
    news = load(P("data", "news.json"), {"items": []}); ap = load(P("queue", "approved.json"), {})
    by = {norm_url(i["url"]): i for i in news["items"]}; rej = {norm_url(r["url"]) for r in ap.get("rejected", []) if r.get("url")}
    for t in open_tips():
        u = tip_url(t)
        if not u: continue
        c = norm_url(u); it = by.get(c); st = it.get("status") if it else ("rejected" if c in rej else None)
        if st == "published":
            msg, reason = f"Thank you for the tip. Our editor has reviewed it and the story is now listed on Nordic Crypto: {SITE}", "completed"
        elif st == "rejected":
            msg, reason = f"Thank you for the tip. Our editor has reviewed it and decided not to include it on Nordic Crypto. See how we choose stories: {SITE}about/", "not planned"
        else: continue
        print(f"tip #{t['number']}: {st} -> comment and close" + (" (dry-run)" if dry else ""))
        if not dry:
            gh("issue", "comment", str(t["number"]), "-R", REPO, "--body", msg)
            gh("issue", "close", str(t["number"]), "-R", REPO, "--reason", reason)

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    close_decided(dry) if "--close-decided" in sys.argv else import_tips(dry)
