#!/usr/bin/env python3
"""Pulls pending reader tips from the Cloudflare D1 database (tipworker/) into the editor queue. Never publishes anything.
Each pending row goes through tools/reader_tips.py (Queue.add via import_rows: dedupe, page metadata, queue/review.json)
with origin 'reader tip #<id>', then the row is marked imported / duplicate / invalid in D1 (imported_at, queue_item_id).
The queue is saved BEFORE the rows are marked, so a crash can at worst re-import a tip (the URL dedupe catches it).
The tipster's name is never selected. Uses `wrangler d1 execute` (env CLOUDFLARE_API_TOKEN; --local = wrangler dev's local D1).
Usage: .venv/bin/python tipworker/pull.py [--local] [--dry-run]"""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools")); import reader_tips  # noqa: E402
DB = "nordic-crypto-tips"; LOCAL = "--local" in sys.argv; DRY = "--dry-run" in sys.argv

def d1(sql):
    env = dict(os.environ, WRANGLER_SEND_METRICS="false")
    node22 = os.path.expanduser("~/.local/node22/bin")
    if os.path.isdir(node22): env["PATH"] = node22 + os.pathsep + env.get("PATH", "")
    cmd = ["npx", "--no-install", "wrangler", "d1", "execute", DB, "--local" if LOCAL else "--remote", "--json", "--command", sql]
    p = subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True, timeout=180)
    if p.returncode != 0:  # print only wrangler's error line(s), never row data
        raise SystemExit("tip worker pull: wrangler d1 execute failed: " + " ".join(l.strip() for l in (p.stdout + p.stderr).splitlines() if "ERROR" in l or "rror" in l)[:300])
    out = json.loads(p.stdout); out = out if isinstance(out, list) else [out]
    return [r for part in out for r in (part.get("results") or [])]
def q(v): return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"

def main():
    if not LOCAL and not os.environ.get("CLOUDFLARE_API_TOKEN"): print("tip worker pull: skipped (no CLOUDFLARE_API_TOKEN)"); return
    if not LOCAL and re.search(r'database_id = "0{8}-', open(os.path.join(HERE, "wrangler.toml")).read()):
        print("tip worker pull: skipped (not deployed yet – run tipworker/deploy.sh)"); return
    rows = d1("SELECT id, created_at, url, country, note FROM tips WHERE status = 'pending' ORDER BY id LIMIT 500")  # name never read
    Q = reader_tips.Queue(DRY)
    marks = reader_tips.import_rows(Q, rows)
    Q.finish()  # saves data/news.json + queue/review.json (not in --dry-run)
    if not DRY and marks:
        for i in range(0, len(marks), 50):
            d1(" ".join(f"UPDATE tips SET status = {q(st)}, imported_at = {q(at)}, queue_item_id = {q(item)} WHERE id = {int(i_)} AND status = 'pending';"
                        for st, at, item, i_ in marks[i:i + 50]))
    print(f"tip worker pull: {len(rows)} pending in D1{' (local)' if LOCAL else ''}; {len(Q.added)} added as pending, {len(Q.skipped)} skipped" + (" (dry-run)" if DRY else ""))
    for a in Q.added: print(f"   + {a['origin']}: {a['country']} {a['source_name']}: {a['title'][:90]}")
    for o, why in Q.skipped: print(f"   - {o}: {why}")

if __name__ == "__main__": main()
