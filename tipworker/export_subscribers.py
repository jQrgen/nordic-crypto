#!/usr/bin/env python3
"""Exports CONFIRMED newsletter subscribers from D1 (table subscribers) as a CSV for a Substack import
(Substack: Settings › Subscribers › Import; the file needs an "email" column). One file per site; the file is
written with mode 600 under state/newsletter/ (gitignored) and the addresses are never printed – only counts.
Pending and unsubscribed rows are never exported.
Usage: .venv/bin/python tipworker/export_subscribers.py --site nordic-crypto|kryptonytt [--lang nn] [--local] [--out PATH]
       [--from-json FILE]  (tests: rows as JSON instead of D1)
Needs CLOUDFLARE_API_TOKEN (remote) or --local (wrangler dev's local D1)."""
import argparse, csv, datetime as dt, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); DB = "nordic-crypto-tips"
SITES = {"nordic-crypto": ["en", "nn", "nb", "sv", "da", "fi", "is"], "kryptonytt": ["nn", "nb", "en"]}

def d1(sql, local):
    env = dict(os.environ, WRANGLER_SEND_METRICS="false"); n22 = os.path.expanduser("~/.local/node22/bin")
    if os.path.isdir(n22): env["PATH"] = n22 + os.pathsep + env.get("PATH", "")
    p = subprocess.run(["npx", "--no-install", "wrangler", "d1", "execute", DB, "--local" if local else "--remote", "--json", "--command", sql],
                       cwd=HERE, env=env, capture_output=True, text=True, timeout=180)
    if p.returncode != 0: raise SystemExit("export: wrangler d1 execute failed (no row data printed)")
    out = json.loads(p.stdout); out = out if isinstance(out, list) else [out]
    return [r for part in out for r in (part.get("results") or [])]

def rows_for(site, lang, rows):
    seen, out = set(), []
    for r in rows:
        e = (r.get("email") or "").strip().lower()
        if r.get("site") != site or r.get("status") != "confirmed" or not e or e in seen: continue
        if lang and r.get("lang") != lang: continue
        seen.add(e); out.append({"email": e, "lang": r.get("lang") or "", "confirmed_at": r.get("confirmed_at") or ""})
    return sorted(out, key=lambda r: r["confirmed_at"])

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--site", required=True, choices=SITES); a.add_argument("--lang")
    a.add_argument("--local", action="store_true"); a.add_argument("--out"); a.add_argument("--from-json")
    o = a.parse_args(argv)
    if o.lang and o.lang not in SITES[o.site]: raise SystemExit(f"export: --lang must be one of {SITES[o.site]}")
    if o.from_json: rows = json.load(open(o.from_json, encoding="utf-8"))
    else:
        if not o.local and not os.environ.get("CLOUDFLARE_API_TOKEN"): raise SystemExit("export: needs CLOUDFLARE_API_TOKEN (or --local)")
        rows = d1("SELECT email, site, lang, status, confirmed_at FROM subscribers WHERE status = 'confirmed' AND site = '%s'" % o.site, o.local)
    out = rows_for(o.site, o.lang, rows)
    path = o.out or os.path.join(ROOT, "state", "newsletter", f"{o.site}{'-' + o.lang if o.lang else ''}-confirmed-{dt.date.today():%Y%m%d}.csv")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email", "lang", "confirmed_at"]); w.writeheader(); w.writerows(out)
    os.chmod(path, 0o600)
    print(f"export: {len(out)} confirmed subscribers for {o.site}{' (' + o.lang + ')' if o.lang else ''} -> {path}")
    return path

if __name__ == "__main__": main()
