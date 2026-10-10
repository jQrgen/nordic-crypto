#!/usr/bin/env python3
"""Samarbeid om norske nyheter mellom Kryptonytt Norge og Nordic Crypto (begge retninger, idempotent).
  Kryptonytt -> Nordic Crypto: Kryptonytts kandidater og godkjente saker (ikke avviste) legges i Nordic Crypto sin kø som
                               «suggested by Kryptonytt» (country NO).
  Nordic Crypto -> Kryptonytt: Nordic Crypto sine NO-saker (ikke avviste) legges i Kryptonytts kø som «foreslått av Nordic Crypto».
Bare tittel, URL, kilde, dato og tagger kopieres – aldri oppsummeringer eller teasere. Alt havner som status «pending»:
hver redaksjon bestemmer selv og skriver sin egen oppsummering (Kryptonytt på norsk, Nordic Crypto på engelsk). Publiserer aldri.
Dedup: kanonisk URL mot ALLE saker i målet (også avviste) og målets approved.json -> rejected.
Kalles fra ./fetch.sh (Kryptonytt) og routines/nightly-fetch.sh (Nordic Crypto). Identisk kopi ligger i begge repoene.
Stier kan overstyres med KRYPTONYTT_DIR / NORDIC_CRYPTO_DIR.  Bruk: python3 tools/crosssite_handoff.py [--dry-run]"""
import datetime as dt, fcntl, importlib.util, json, os, re, signal, subprocess, sys, time, urllib.parse
KN = os.environ.get("KRYPTONYTT_DIR", "/workspace/kryptonytt"); NC = os.environ.get("NORDIC_CRYPTO_DIR", "/workspace/nordic-crypto")
NOW = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
TOPIC_KN_TO_NC = {"krypto": "crypto", "blokkjede": "blockchain", "regulering": "regulation", "selskaper": "companies", "bitcoin": "bitcoin"}
TOPIC_NC_TO_KN = {v: k for k, v in TOPIC_KN_TO_NC.items()}

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
def save(p, d):
    t = p + ".handoff.tmp"; json.dump(d, open(t, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(t, p)
TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|gclsrc|dclid|msclkid|yclid|twclid|igshid|mc_cid|mc_eid|_hsenc|_hsmi|mkt_tok|ref|ref_src|ref_url|cmpid|ocid|ncid|xtor|s_cid|wt_mc|at_.*|spm|share|guccounter|guce_.*|__twitter_impression|cmp|campaign)$", re.I)
def norm_url(url):
    """Normalisert URL for duplikatsjekk: https, vert med små bokstaver uten www., uten avsluttende /, uten sporingsparametre, uten fragment."""
    p = urllib.parse.urlparse(url.strip())
    host = (p.hostname or "").lower().removeprefix("www.")
    if p.port and p.port not in (80, 443): host += f":{p.port}"
    q = sorted((k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k))
    return urllib.parse.urlunparse(("https", host, p.path.rstrip("/") or "/", "", urllib.parse.urlencode(q), ""))
def strip_tracking(url):
    p = urllib.parse.urlparse(url.strip())
    return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k)]), fragment=""))
def canon_of(repo, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(repo, "fetch.py")); m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m); return m.canon, m.iid

def refresh_published(d_news, d_q, canon_url, published):
    """Copy a corrected Nordic Crypto publish time onto rows Kryptonytt already imported (via nordic-crypto)."""
    n = 0
    for i in d_news["items"]:
        if i.get("via") == "nordic-crypto" and norm_url(i.get("url") or "") == canon_url and i.get("published") != published:
            i["published"] = published
            n += 1
            for q in d_q.get("items_needing_summary", []):
                if q.get("id") == i.get("id"):
                    q["published"] = published
        for ex in i.get("also_covered_by") or []:
            if isinstance(ex, dict) and norm_url(ex.get("url") or "") == canon_url and ex.get("published") != published:
                ex["published"] = published
                n += 1
    return n

def handoff(src, dst, pick, convert, queue_fields, label, dry):
    s_news = load(os.path.join(src, "data", "news.json"), {"items": []})
    d_newsf = os.path.join(dst, "data", "news.json"); d_news = load(d_newsf, {"items": []})
    d_qf = os.path.join(dst, "queue", "review.json"); d_q = load(d_qf, {"items_needing_summary": [], "candidate_entities": []})
    d_ap = load(os.path.join(dst, "queue", "approved.json"), {})
    _, iid = canon_of(dst, "dst_fetch_" + os.path.basename(dst).replace("-", "_")); canon = norm_url
    cov_path = os.path.join(dst, "tools", "coverage.py")
    cov = None
    if os.path.exists(cov_path):
        spec = importlib.util.spec_from_file_location("nc_coverage_" + os.path.basename(dst).replace("-", "_"), cov_path)
        cov = importlib.util.module_from_spec(spec); spec.loader.exec_module(cov)
    have = {canon(i["url"]) for i in d_news["items"] if i.get("url")} | {canon(r["url"]) for r in d_ap.get("rejected", []) if r.get("url")}
    for i in d_news["items"]:
        for ex in i.get("also_covered_by") or []:
            if isinstance(ex, dict) and ex.get("url"): have.add(canon(ex["url"]))
    added, attached = [], []
    refreshed = 0
    for it in s_news["items"]:
        if not pick(it): continue
        c = canon(it["url"])
        if c in have:
            # Nordic Crypto -> Kryptonytt: an already imported row keeps via nordic-crypto and
            # must pick up a corrected publish time. The other direction does not overwrite a
            # page time we have already stored.
            if "Nordic Crypto ->" in label and it.get("published"):
                refreshed += refresh_published(d_news, d_q, c, it["published"])
            continue
        url = strip_tracking(it["url"])
        new = convert(it); new.update(id=iid(url), url=url, status="pending", summary=None, fetched=NOW)
        if cov:
            match, why = cov.find_match(
                {"url": url, "title": new.get("title"), "published": new.get("published"), "text": new.get("title") or ""}, d_news["items"])
            if match:
                rec = cov.record_from_parts(new.get("source"), new.get("source_name"), url, new.get("title"), new.get("published"),
                                            new.get("language"), new.get("country"), paywall=new.get("paywall"))
                cov.attach(match, rec)
                have.add(c); attached.append(new)
                d_q.setdefault("coverage_attached", []).append(
                    {"url": url, "title": new.get("title"), "outlet": new.get("source"), "attached_to": match.get("id"),
                     "reason": why, "at": NOW, "origin": new.get("origin")})
                continue
        d_news["items"].append(new); have.add(c); added.append(new)
        d_q.setdefault("items_needing_summary", []).append({k: new.get(k) for k in queue_fields})
    # eldre forslag uten origin får den nå (bare forslag fra denne retningen)
    lab = convert({"title": "", "published": "", "topics": []}).get("origin")
    fixed = 0
    for i in d_news["items"]:
        if i.get("suggested_by") and not i.get("origin") and i.get("via") == ("kryptonytt" if "Kryptonytt ->" in label else "nordic-crypto"):
            i["origin"] = lab; fixed += 1
    org = {i["id"]: i for i in d_news["items"] if i.get("origin")}
    for q in d_q.get("items_needing_summary", []):  # målets egen henting kan ha bygd køraden på nytt uten origin
        src_i = org.get(q.get("id"))
        if src_i and not q.get("origin"):
            q["origin"] = src_i["origin"]; q.setdefault("suggested_by", src_i.get("suggested_by")); fixed += 1
    if (added or fixed or attached or refreshed) and not dry:
        save(d_newsf, d_news); save(d_qf, d_q)
    print(f"handoff {label}: {len(added)} nye forslag, {len(attached)} lagt på en sak som finnes, {refreshed} datoer oppdatert" + (" (dry-run)" if dry else ""))
    for a in added: print(f"   + {a['published'][:10]} {a['source_name']}: {a['title'][:90]}")
    return added

LOCK_PATH = os.environ.get("CROSSSITE_LOCK", "/tmp/crosssite-handoff.lock")

def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

def _stop_pid(pid):
    """Stop pid and its children. A hung handoff must not keep the next night waiting."""
    if not isinstance(pid, int) or pid <= 1:
        return
    children = []
    try:
        raw = subprocess.run(["ps", "-o", "pid=", "--ppid", str(pid)], capture_output=True, text=True, timeout=5).stdout
        children = [int(x) for x in raw.split() if x.isdigit()]
    except (OSError, subprocess.TimeoutExpired):
        children = []
    for child in children:
        _stop_pid(child)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not _pid_alive(pid):
            return
        try:
            os.kill(pid, sig)
        except OSError:
            return
        for _ in range(20):
            if not _pid_alive(pid):
                return
            time.sleep(0.1)

def _lock_record(fh):
    fh.seek(0)
    parts = fh.read().split()
    pid = int(parts[0]) if parts and parts[0].isdigit() else None
    started = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    return pid, started

def acquire_lock(path=None, stale=900, wait=30):
    """Exclusive handoff lock. Returns the open file; keep it until the process exits.

    flock dies with the process, so a leftover file from a dead run is not a lock.
    A live holder older than ``stale`` seconds is stopped. Otherwise this waits at
    most ``wait`` seconds and then exits. It does not block until an outer timer kills it.
    """
    path = path or LOCK_PATH
    fh = open(path, "a+")
    deadline = time.time() + max(0, wait)
    while True:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            pid, started = _lock_record(fh)
            age = (time.time() - started) if started else None
            alive = bool(pid) and _pid_alive(pid)
            if alive and age is not None and age >= stale:
                print(f"handoff: stale lock held by pid {pid} for {int(age)}s — stopping it ({path})", flush=True)
                _stop_pid(pid)
                time.sleep(0.2)
                continue
            if time.time() >= deadline:
                if alive:
                    raise SystemExit(f"handoff: lock held by pid {pid} ({path}). Stop that process if it is stuck. The file is not the lock; flock dies with the process.")
                raise SystemExit(f"handoff: {path} is busy and the recorded pid is not running. Another handoff still holds it.")
            time.sleep(0.2)
    fh.seek(0)
    fh.truncate()
    fh.write(f"{os.getpid()} {int(time.time())}\n")
    fh.flush()
    return fh

def main():
    dry = "--dry-run" in sys.argv
    lock = acquire_lock()  # held until this process exits; do not close
    def kn_to_nc(it):
        return {"title": it["title"], "title_en": None, "source": it.get("source"), "source_name": it.get("source_name") or it.get("source"),
                "country": "NO", "language": "Norwegian", "via": "kryptonytt", "seen_via": ["kryptonytt"], "published": it["published"],
                "topics": sorted({TOPIC_KN_TO_NC.get(t, t) for t in it.get("topics", [])}), "matched": [], "paywall": bool(it.get("paywall")),
                "suggested_by": "Kryptonytt", "origin": "suggested by Kryptonytt", "suggested_status": "approved on Kryptonytt" if it.get("status") == "published" else "candidate on Kryptonytt",
                "suggested_at": NOW}
    def nc_to_kn(it):
        return {"title": it["title"], "source": it.get("source"), "source_name": it.get("source_name") or it.get("source"),
                "via": "nordic-crypto", "seen_via": ["nordic-crypto"], "published": it["published"],
                "topics": sorted({TOPIC_NC_TO_KN.get(t, t) for t in it.get("topics", [])}), "matched": [], "paywall": bool(it.get("paywall")),
                "suggested_by": "Nordic Crypto", "origin": "tips fra Nordic Crypto", "suggested_status": "godkjent hos Nordic Crypto" if it.get("status") == "published" else "kandidat hos Nordic Crypto",
                "suggested_at": NOW}
    handoff(KN, NC, lambda i: i.get("status") in ("pending", "published"), kn_to_nc,
            ("id", "country", "language", "title", "source_name", "url", "published", "topics", "suggested_by", "origin", "suggested_status"), "Kryptonytt -> Nordic Crypto", dry)
    handoff(NC, KN, lambda i: i.get("country") == "NO" and i.get("status") in ("pending", "published"), nc_to_kn,
            ("id", "title", "source_name", "url", "published", "topics", "suggested_by", "origin", "suggested_status"), "Nordic Crypto -> Kryptonytt", dry)

if __name__ == "__main__": main()
