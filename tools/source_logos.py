#!/usr/bin/env python3
"""Map a news source id to an outlet logo.

The manifest is assets/img/logos/logos.json (same file as the who's who).
Resolution, in order:

  1. sources.json field ``outlet`` (a feed that belongs to a parent outlet).
  2. logos.json ``_source_alias`` (source id → logo key when the who's-who id differs).
  3. The source id itself.

A logo is shown only when that key has a file on disk and review is not ``rejected``.
The public site requires review ``ok`` (a missing review counts as ok, same as the org chart).
``./build.sh --preview`` also shows review ``pending``. There is no drawn or invented fallback:
callers show the source name as text when this returns None.

Nordic Crypto's own stories use source id ``nordic-crypto``. That id is never given a generated mark.
"""
import json, os, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "assets", "img", "logos", "logos.json")
SOURCES = os.path.join(ROOT, "sources.json")
NEWS = os.path.join(ROOT, "data", "news.json")
# Our own byline. Kaupr is a news source and is not listed here.
OWN = {"nordic-crypto"}
PUBLIC_KEYS = ("file", "source", "source_url", "license", "author")


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def manifest():
    raw = _load(MANIFEST, {}) or {}
    return {k: v for k, v in raw.items() if not str(k).startswith("_") and isinstance(v, dict)}


def aliases():
    raw = _load(MANIFEST, {}) or {}
    block = raw.get("_source_alias") or {}
    return {k: v for k, v in block.items() if not str(k).startswith("_") and isinstance(v, str) and v}


def sources():
    raw = _load(SOURCES, {}) or {}
    return [s for s in (raw.get("sources") or []) if isinstance(s, dict) and s.get("id")]


def sources_by_id():
    return {s["id"]: s for s in sources()}


def canonical_id(source_id, by_id=None, alias=None):
    """Logo key for a news item's ``source`` field. See the module docstring."""
    if not source_id or source_id in OWN:
        return None
    by_id = sources_by_id() if by_id is None else by_id
    alias = aliases() if alias is None else alias
    sid, seen = source_id, set()
    while sid and sid not in seen:
        seen.add(sid)
        outlet = (by_id.get(sid) or {}).get("outlet")
        if outlet and outlet not in seen:
            sid = outlet
            continue
        mapped = alias.get(sid)
        if mapped and mapped not in seen:
            sid = mapped
            continue
        return sid
    return None


def homepage(source_id, by_id=None):
    """Outlet homepage for a source id. The logo links here."""
    if not source_id or source_id in OWN:
        return None
    by_id = sources_by_id() if by_id is None else by_id
    own = by_id.get(source_id) or {}
    if own.get("url"):
        return own["url"]
    key = canonical_id(source_id, by_id)
    hit = (by_id.get(key) or {}).get("url") if key else None
    if hit:
        return hit
    # Some logo keys (kaupr) are a parent outlet with no row of their own.
    for s in by_id.values():
        if s.get("url") and (s.get("outlet") == source_id or canonical_id(s.get("id"), by_id) == source_id):
            return s["url"]
    return None


def for_source(source_id, preview=False):
    """Public logo record, or None when the name should be shown alone.

    Keys: file (repo-relative), source, source_url, license, author, id.
    ``pending`` is true only in a preview build.
    """
    key = canonical_id(source_id)
    rec = manifest().get(key) if key else None
    if not rec or not rec.get("file"):
        return None
    if rec.get("review") == "rejected":
        return None
    if not os.path.exists(os.path.join(ROOT, rec["file"])):
        return None
    rev = rec.get("review") or "ok"
    if rev != "ok" and not (preview and rev == "pending"):
        return None
    out = {k: rec.get(k) for k in PUBLIC_KEYS if rec.get(k)}
    out["id"] = key
    if rev == "pending":
        out["pending"] = True
    return out


def usable_homepage(url):
    """A real outlet homepage. The Medietilsynet database is not one paper's site."""
    if not url or not str(url).startswith("http"):
        return False
    if "mediedatabasen" in url or "id.bonniernews.se" in url:
        return False
    return True


def outlets_to_fetch(man=None, force=False, only=None):
    """News outlets that still need a logo file.

    Every registry source with a homepage is included, including disabled feeds,
    so a local paper with no RSS still gets its own mark. Bing search rows are
    not outlets. One job per canonical logo key. Rejected entries, and outlets
    whose terms forbid logo use, are left alone unless ``force`` is set.
    Aliases that already point at a file are skipped.
    """
    if man is None:
        raw = _load(MANIFEST, {}) or {}
        man = {k: v for k, v in raw.items() if not str(k).startswith("_")}
    by = sources_by_id()
    alias = aliases()
    news = _load(NEWS, {"items": []}) or {"items": []}
    only = set(only or [])
    def need(key, name, url, sid):
        if not key or key in seen:
            return
        if only and key not in only and sid not in only:
            return
        seen.add(key)
        rec = man.get(key) if isinstance(man.get(key), dict) else {}
        if rec.get("review") == "rejected" and not force:
            return
        if rec.get("file") and os.path.exists(os.path.join(ROOT, rec["file"])) and not force:
            return
        if url and name and usable_homepage(url):
            jobs.append({"id": key, "name": name, "url": url})

    jobs, seen = [], set()
    for s in sources():
        if s.get("type") == "bing":
            continue
        if s.get("logo_skipped"):
            continue
        sid = s["id"]
        key = canonical_id(sid, by, alias)
        host = by.get(key) or s
        need(key, host.get("name") or s.get("name"), host.get("url") or s.get("url"), sid)
    # Stories sometimes carry a source id that is not in sources.json (a one-off outlet).
    # The logo key is still that id. The site is the origin of the story URL.
    for item in news.get("items") or []:
        sid = item.get("source")
        if not sid or sid in by or sid in OWN or item.get("status") not in ("published", "pending"):
            continue
        key = canonical_id(sid, by, alias)
        parsed = urllib.parse.urlparse(item.get("url") or "")
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme in ("http", "https") and parsed.netloc else None
        need(key, item.get("source_name") or sid, origin, sid)
    jobs.sort(key=lambda j: j["id"])
    return jobs
