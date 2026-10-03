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
import datetime as dt, fcntl, importlib.util, json, os, sys
KN = os.environ.get("KRYPTONYTT_DIR", "/workspace/kryptonytt"); NC = os.environ.get("NORDIC_CRYPTO_DIR", "/workspace/nordic-crypto")
NOW = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
TOPIC_KN_TO_NC = {"krypto": "crypto", "blokkjede": "blockchain", "regulering": "regulation", "selskaper": "companies", "bitcoin": "bitcoin"}
TOPIC_NC_TO_KN = {v: k for k, v in TOPIC_KN_TO_NC.items()}

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
def save(p, d):
    t = p + ".handoff.tmp"; json.dump(d, open(t, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(t, p)
def canon_of(repo, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(repo, "fetch.py")); m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m); return m.canon, m.iid

def handoff(src, dst, pick, convert, queue_fields, label, dry):
    s_news = load(os.path.join(src, "data", "news.json"), {"items": []})
    d_newsf = os.path.join(dst, "data", "news.json"); d_news = load(d_newsf, {"items": []})
    d_qf = os.path.join(dst, "queue", "review.json"); d_q = load(d_qf, {"items_needing_summary": [], "candidate_entities": []})
    d_ap = load(os.path.join(dst, "queue", "approved.json"), {})
    canon, iid = canon_of(dst, "dst_fetch_" + os.path.basename(dst).replace("-", "_"))
    have = {canon(i["url"]) for i in d_news["items"]} | {canon(r["url"]) for r in d_ap.get("rejected", []) if r.get("url")}
    added = []
    for it in s_news["items"]:
        if not pick(it): continue
        c = canon(it["url"])
        if c in have: continue
        new = convert(it); new.update(id=iid(it["url"]), url=it["url"], status="pending", summary=None, fetched=NOW)
        d_news["items"].append(new); have.add(c); added.append(new)
        d_q.setdefault("items_needing_summary", []).append({k: new.get(k) for k in queue_fields})
    if added and not dry:
        save(d_newsf, d_news); save(d_qf, d_q)
    print(f"handoff {label}: {len(added)} nye forslag" + (" (dry-run)" if dry else ""))
    for a in added: print(f"   + {a['published'][:10]} {a['source_name']}: {a['title'][:90]}")
    return added

def main():
    dry = "--dry-run" in sys.argv
    lock = open("/tmp/crosssite-handoff.lock", "w"); fcntl.flock(lock, fcntl.LOCK_EX)
    def kn_to_nc(it):
        return {"title": it["title"], "title_en": None, "source": it.get("source"), "source_name": it.get("source_name") or it.get("source"),
                "country": "NO", "language": "Norwegian", "via": "kryptonytt", "seen_via": ["kryptonytt"], "published": it["published"],
                "topics": sorted({TOPIC_KN_TO_NC.get(t, t) for t in it.get("topics", [])}), "matched": [], "paywall": bool(it.get("paywall")),
                "suggested_by": "Kryptonytt", "suggested_status": "approved on Kryptonytt" if it.get("status") == "published" else "candidate on Kryptonytt",
                "suggested_at": NOW}
    def nc_to_kn(it):
        return {"title": it["title"], "source": it.get("source"), "source_name": it.get("source_name") or it.get("source"),
                "via": "nordic-crypto", "seen_via": ["nordic-crypto"], "published": it["published"],
                "topics": sorted({TOPIC_NC_TO_KN.get(t, t) for t in it.get("topics", [])}), "matched": [], "paywall": bool(it.get("paywall")),
                "suggested_by": "Nordic Crypto", "suggested_status": "godkjent hos Nordic Crypto" if it.get("status") == "published" else "kandidat hos Nordic Crypto",
                "suggested_at": NOW}
    handoff(KN, NC, lambda i: i.get("status") in ("pending", "published"), kn_to_nc,
            ("id", "country", "language", "title", "source_name", "url", "published", "topics", "suggested_by", "suggested_status"), "Kryptonytt -> Nordic Crypto", dry)
    handoff(NC, KN, lambda i: i.get("country") == "NO" and i.get("status") in ("pending", "published"), nc_to_kn,
            ("id", "title", "source_name", "url", "published", "topics", "suggested_by", "suggested_status"), "Nordic Crypto -> Kryptonytt", dry)

if __name__ == "__main__": main()
