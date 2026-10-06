#!/usr/bin/env python3
"""Several outlets for one event.

A story keeps its existing primary fields (source, source_name, url, title, published, language, country).
Other outlets that covered the same event sit in also_covered_by:

  {outlet, outlet_name, url, title, published, lang, country, source_type}

outlet is the source id. lang matches the story language name (Norwegian, Swedish, …).
source_type is national, regional, official (justice and official) or international.
Old stories omit also_covered_by and stay one outlet. An empty list means the same.

Import (fetch.py, reader tips, the cross-site handoff) attaches a new article instead of
creating a second story when the editor marked it, the headline matches, the title is
close inside a three-day window, or two known organisations appear in both texts.
The editor marks a duplicate with duplicate_of (story id or URL) on the review-queue
row or on the approved.json item.
"""
import datetime as dt
import os
import re
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(ROOT, "sources.json")
REACHES = ("national", "regional", "official", "international")
NORDIC = {"NO", "SE", "DK", "FI", "IS", "NORDIC"}
DATE_WINDOW_DAYS = 3
SAME_TITLE_DAYS = 14
# Known organisations. Shared with the fetch candidate list so "same entities" means the same names.
ENTITIES = [
    "Firi", "Bare Bitcoin", "K33", "NBX", "Norwegian Block Exchange", "Týr Markets", "Kaupr", "Nexa", "Seetee",
    "Finanstilsynet", "Norges Bank", "Skatteetaten", "Økokrim", "Safello", "Virtune", "Valuno", "GreenMerc", "Trijo",
    "Goobit", "BTCX", "Finansinspektionen", "Riksbanken", "Skatteverket", "Finanspolisen", "Svenska Bitcoinföreningen",
    "Coinmotion", "Northcrypto", "Kvarn", "Tesseract", "Bittimaatti", "Paxos", "Finanssivalvonta", "Suomen Pankki",
    "Verohallinto", "Myntkaup", "Monerium", "Seðlabanki", "Skatturinn", "Danmarks Nationalbank", "Nationalbanken",
    "Skattestyrelsen", "Erhvervsministeriet", "Coinify", "Nordic Blockchain Association", "Coinbase", "Binance",
    "Kraken", "Bitpanda", "Revolut", "Nordnet", "Avanza", "DNB", "Nordea", "SEB", "Swedbank", "Handelsbanken", "OP",
]
STOP = {
    "about", "after", "again", "alla", "alle", "also", "and", "anna", "annat", "are", "att", "av", "ble", "blir",
    "but", "den", "der", "det", "dette", "din", "efter", "eller", "en", "ett", "for", "fra", "from", "har", "have",
    "hos", "hva", "hvad", "hvor", "i", "ikke", "inte", "into", "ja", "kan", "med", "men", "mer", "more", "mot",
    "når", "och", "og", "om", "opp", "over", "på", "paa", "som", "than", "that", "the", "til", "till", "this",
    "under", "var", "ved", "vid", "was", "with",
}
OFFICIAL_KIND = re.compile(
    r"regulat|central bank|ministry|parliament|police|prosecut|court|tax authority|authority|government",
    re.I,
)
REGIONAL_KIND = re.compile(r"local|regional|district", re.I)
_sources = None


def load_sources():
    global _sources
    if _sources is None:
        import json
        try:
            raw = json.load(open(SOURCES, encoding="utf-8"))
        except FileNotFoundError:
            raw = {}
        _sources = {s["id"]: s for s in (raw.get("sources") or []) if s.get("id")}
    return _sources


def canon(url):
    if not url:
        return ""
    p = urllib.parse.urlparse(url.strip())
    q = urllib.parse.urlencode(
        [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
    )
    host = (p.netloc or "").lower().removeprefix("www.")
    path = p.path.rstrip("/") or "/"
    return host + path + (("?" + q) if q else "")


def parse_dt(value):
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    if not value:
        return None
    try:
        d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def reach_of(source=None, country=None, explicit=None):
    """national, regional, official or international. explicit wins, then sources.json reach, then kind."""
    if explicit in REACHES:
        return explicit
    source = source or {}
    marked = source.get("reach") or source.get("source_type")
    if marked in REACHES:
        return marked
    kind = source.get("kind") or ""
    if OFFICIAL_KIND.search(kind):
        return "official"
    if REGIONAL_KIND.search(kind) or source.get("local"):
        return "regional"
    if re.search(r"\bwire\b", kind, re.I):
        return "international"
    c = country or source.get("country")
    if c and c not in NORDIC and c != "EU":
        return "international"
    return "national"


def _clean_record(rec):
    """Fields stored on also_covered_by. Drops empty values except booleans we always keep off the list."""
    out = {}
    for key in ("outlet", "outlet_name", "url", "title", "published", "lang", "country", "source_type"):
        if rec.get(key) not in (None, ""):
            out[key] = rec[key]
    if "paywall" in rec:
        out["paywall"] = bool(rec["paywall"])
    return out


def record_from_parts(outlet, outlet_name, url, title, published, lang=None, country=None, source_type=None, paywall=None):
    src = load_sources().get(outlet) or {}
    published = published.isoformat() if isinstance(published, dt.datetime) else published
    rec = {
        "outlet": outlet,
        "outlet_name": outlet_name or src.get("name") or outlet,
        "url": url,
        "title": title,
        "published": published,
        "lang": lang or src.get("language"),
        "country": country or src.get("country"),
        "source_type": reach_of(src, country or src.get("country"), source_type),
    }
    if paywall is None:
        paywall = bool(src.get("paywall"))
    rec["paywall"] = bool(paywall)
    return _clean_record(rec)


def record_from_item(item):
    return record_from_parts(
        item.get("source"),
        item.get("source_name"),
        item.get("url"),
        item.get("title"),
        item.get("published"),
        item.get("language") or item.get("lang"),
        item.get("country"),
        item.get("source_type"),
        item.get("paywall"),
    )


def primary_of(item, by_id=None):
    by_id = load_sources() if by_id is None else by_id
    src = by_id.get(item.get("source")) or {}
    return {
        "outlet": item.get("source"),
        "outlet_name": item.get("source_name") or src.get("name") or item.get("source"),
        "url": item.get("url"),
        "title": item.get("title"),
        "published": item.get("published"),
        "lang": item.get("language"),
        "country": item.get("country") or src.get("country"),
        "source_type": reach_of(src, item.get("country"), item.get("source_type")),
        "paywall": bool(item.get("paywall")),
        "primary": True,
    }


def normalize_extra(raw, by_id=None):
    by_id = load_sources() if by_id is None else by_id
    sid = raw.get("outlet") or raw.get("source")
    src = by_id.get(sid) or {}
    return {
        "outlet": sid,
        "outlet_name": raw.get("outlet_name") or raw.get("source_name") or src.get("name") or sid,
        "url": raw.get("url"),
        "title": raw.get("title"),
        "published": raw.get("published"),
        "lang": raw.get("lang") or raw.get("language") or src.get("language"),
        "country": raw.get("country") or src.get("country"),
        "source_type": reach_of(src, raw.get("country") or src.get("country"), raw.get("source_type") or raw.get("reach")),
        "paywall": bool(raw["paywall"]) if "paywall" in raw else bool(src.get("paywall")),
        "primary": False,
    }


def all_outlets(item, by_id=None):
    """Primary first, then other outlets. One row per URL. Stories without also_covered_by return the primary only."""
    by_id = load_sources() if by_id is None else by_id
    rows = [primary_of(item, by_id)]
    seen = set()
    if rows[0].get("url"):
        seen.add(canon(rows[0]["url"]))
    for raw in item.get("also_covered_by") or []:
        if not isinstance(raw, dict):
            continue
        rec = normalize_extra(raw, by_id)
        key = canon(rec.get("url") or "")
        if not rec.get("url") or key in seen:
            continue
        seen.add(key)
        rows.append(rec)
    return rows


def breakdown(rows):
    """Counts for the story page and the API. Every source type is present, including zeros."""
    n = len(rows)
    by_c = {}
    for row in rows:
        c = row.get("country") or ""
        by_c[c] = by_c.get(c, 0) + 1
    order = ["NO", "SE", "DK", "FI", "IS", "NORDIC", "EU"]
    countries = sorted(by_c, key=lambda c: (order.index(c) if c in order else 50, c))
    share = (lambda count: round(count / n, 4) if n else 0)
    return {
        "count": n,
        "by_country": [{"country": c, "count": by_c[c], "share": share(by_c[c])} for c in countries],
        "by_source_type": [
            {"type": key, "count": sum(1 for r in rows if r.get("source_type") == key), "share": share(sum(1 for r in rows if r.get("source_type") == key))}
            for key in REACHES
        ],
    }


def tokens(text):
    words = re.findall(r"[^\W\d_]{4,}", (text or "").lower(), re.UNICODE)
    return {w for w in words if w not in STOP}


def entities_in(text):
    blob = text or ""
    return {name.lower() for name in ENTITIES if re.search(rf"\b{re.escape(name)}\b", blob, re.I)}


def norm_title(title):
    return re.sub(r"[^\w]+", " ", (title or "").lower(), flags=re.UNICODE).strip()


def same_event(new, old):
    """Reason string when new is another outlet on old's event, else None.

    new/old: url, title, published, text (title + teaser or summary).
    """
    if not new.get("url") or not old.get("url"):
        return None
    if canon(new["url"]) == canon(old["url"]):
        return None
    nd, od = parse_dt(new.get("published")), parse_dt(old.get("published"))
    if not nd or not od:
        return None
    days = abs((nd - od).total_seconds()) / 86400
    nt, ot = norm_title(new.get("title")), norm_title(old.get("title"))
    if nt and nt == ot and days <= SAME_TITLE_DAYS:
        return "same title"
    if days > DATE_WINDOW_DAYS:
        return None
    a = tokens(new.get("title"))
    b = tokens(old.get("title"))
    inter = a & b
    union = a | b
    jac = (len(inter) / len(union)) if union else 0
    if len(inter) >= 4 and jac >= 0.55:
        return "title similarity"
    shared = entities_in(new.get("text") or new.get("title")) & entities_in(old.get("text") or old.get("title"))
    if len(shared) >= 2:
        return "same entities"
    return None


def story_text(item, teaser=""):
    return " ".join(x for x in (item.get("title"), item.get("title_en"), item.get("summary"), teaser) if x)


def find_match(candidate, items, teasers=None):
    """(item, reason) for the closest existing story, or (None, None).

    candidate: url, title, published, text. Rejected and already-merged rows are not targets.
    """
    teasers = teasers or {}
    best, best_reason, best_days = None, None, None
    nd = parse_dt(candidate.get("published"))
    for item in items:
        if item.get("status") in ("rejected", "merged"):
            continue
        if item.get("id") and candidate.get("id") and item["id"] == candidate["id"]:
            continue
        old = {
            "url": item.get("url"),
            "title": item.get("title"),
            "published": item.get("published"),
            "text": story_text(item, teasers.get(item.get("id")) or ""),
        }
        reason = same_event(candidate, old)
        if not reason:
            continue
        od = parse_dt(item.get("published"))
        days = abs((nd - od).total_seconds()) if nd and od else 9e9
        if best is None or days < best_days:
            best, best_reason, best_days = item, reason, days
    return best, best_reason


def resolve_target(items, ref):
    ref = (ref or "").strip()
    if not ref:
        return None
    key = canon(ref) if "://" in ref or "/" in ref else ""
    for item in items:
        if item.get("id") == ref:
            return item
        if key and canon(item.get("url")) == key:
            return item
    return None


def attach(item, record):
    """Append record to also_covered_by. False when the URL is already the primary or an extra."""
    url = record.get("url")
    if not url or canon(url) == canon(item.get("url")):
        return False
    extras = item.setdefault("also_covered_by", [])
    if any(canon(ex.get("url")) == canon(url) for ex in extras if isinstance(ex, dict)):
        return False
    extras.append(_clean_record(record))
    return True


def fold_into(items, source_item, target_ref):
    """Editor mark: move source_item onto target as an extra outlet. Returns the target, or None."""
    target = resolve_target(items, target_ref)
    if not target or target is source_item or target.get("id") == source_item.get("id"):
        return None
    if target.get("status") in ("rejected", "merged"):
        return None
    attach(target, record_from_item(source_item))
    source_item["status"] = "merged"
    source_item["merged_into"] = target.get("id")
    source_item["summary"] = None
    return target


def index_urls(items):
    """Primary and extra URLs → story, so a later fetch of an outlet we already list is not a new story."""
    by = {}
    for item in items:
        if item.get("url"):
            by[canon(item["url"])] = item
        for ex in item.get("also_covered_by") or []:
            if isinstance(ex, dict) and ex.get("url"):
                by.setdefault(canon(ex["url"]), item)
    return by
