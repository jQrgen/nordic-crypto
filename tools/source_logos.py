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
PUBLIC_KEYS = ("file", "source", "source_url", "license", "license_url", "author")


# path -> ((st_mtime_ns, st_size), parsed JSON); name -> (raw object, derived table).
_PARSED, _DERIVED = {}, {}


def _load(path, default):
    """Parsed JSON at path, re-read only when the file's mtime or size changes.

    The build looks up a logo ~27 000 times; parsing sources.json and logos.json each time cost ~230 s.
    The stat is taken before the read, so a write during the read is picked up next call.
    Returned objects (here and in manifest/aliases/sources/sources_by_id) are shared: do not mutate them.
    """
    try:
        st = os.stat(path)
        hit = _PARSED.get(path)
        stamp = (st.st_mtime_ns, st.st_size)
        if hit and hit[0] == stamp:
            return hit[1]
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return default
    _PARSED[path] = (stamp, data)
    return data


def _derive(name, raw, build):
    """build(raw), cached until raw is a different object. Holds raw itself so its id() cannot be reused."""
    hit = _DERIVED.get(name)
    if hit and hit[0] is raw:
        return hit[1]
    out = build(raw)
    _DERIVED[name] = (raw, out)
    return out


def manifest():
    raw = _load(MANIFEST, {}) or {}
    return _derive("manifest", raw, lambda raw: {k: v for k, v in raw.items() if not str(k).startswith("_") and isinstance(v, dict)})


def aliases():
    raw = _load(MANIFEST, {}) or {}
    def build(raw):
        block = raw.get("_source_alias") or {}
        return {k: v for k, v in block.items() if not str(k).startswith("_") and isinstance(v, str) and v}
    return _derive("aliases", raw, build)


def sources():
    raw = _load(SOURCES, {}) or {}
    return _derive("sources", raw, lambda raw: [s for s in (raw.get("sources") or []) if isinstance(s, dict) and s.get("id")])


def sources_by_id():
    return _derive("sources_by_id", sources(), lambda lst: {s["id"]: s for s in lst})


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
    # Read the alias map once: canonical_id() would otherwise re-parse logos.json for every source below.
    alias = aliases()
    key = canonical_id(source_id, by_id, alias)
    hit = (by_id.get(key) or {}).get("url") if key else None
    if hit:
        return hit
    # Some logo keys (kaupr) are a parent outlet with no row of their own.
    for s in by_id.values():
        if s.get("url") and (s.get("outlet") == source_id or canonical_id(s.get("id"), by_id, alias) == source_id):
            return s["url"]
    return None


def _usable(rec, preview):
    if not rec or not rec.get("file") or rec.get("review") == "rejected":
        return None
    if not os.path.exists(os.path.join(ROOT, rec["file"])):
        return None
    rev = rec.get("review") or "ok"
    if rev != "ok" and not (preview and rev == "pending"):
        return None
    return rev


def raster_of(rec):
    """Repo-relative raster image for a logo record (PNG or WebP, never SVG), or None.

    An SVG uses its PNG rendering (key ``raster``, written by tools/fetch_source_logos.py --raster-only);
    any other file is already raster."""
    f = str(rec.get("file") or "")
    if not f.lower().endswith(".svg"):
        return f or None
    r = rec.get("raster")
    return r if r and os.path.exists(os.path.join(ROOT, r)) else None


def candidates(source_id, by_id=None, alias=None):
    """Manifest keys to try for a source id, best first.

    1. The canonical key (outlet, then _source_alias, then the id): logos fetched by tools/fetch_logos.py.
    2. ``source:<key>``, ``source:<id>``, ``source:<outlet>``: logos fetched by tools/fetch_source_logos.py.
    3. A one-off domain id (search hits such as ``itavisen.no``): the same keys for the source whose url is on that host.
    """
    by_id = sources_by_id() if by_id is None else by_id
    alias = aliases() if alias is None else alias
    key = canonical_id(source_id, by_id, alias)
    if not key:
        return []
    out = [key, "source:" + key, "source:" + source_id]
    outlet = (by_id.get(source_id) or {}).get("outlet")
    if outlet:
        out.append("source:" + outlet)
    if "." in source_id and source_id not in by_id:
        host = source_id.lower().removeprefix("www.")
        for s in sorted(by_id.values(), key=lambda s: bool(s.get("outlet"))):
            h = (urllib.parse.urlparse(s.get("url") or "").hostname or "").lower().removeprefix("www.")
            if h and s.get("type") != "bing" and (h == host or host.endswith("." + h)):
                out += candidates(s["id"], by_id, alias)
                break
    seen, res = set(), []
    for k in out:
        if k not in seen:
            seen.add(k)
            res.append(k)
    return res


def for_source(source_id, preview=False):
    """Public logo record, or None when the name should be shown alone.

    Keys: file (repo-relative), raster (repo-relative PNG/WebP, or None for an SVG without a rendering),
    source, source_url, license, author, id. ``pending`` is true only in a preview build.
    A rejected or missing entry falls through to the next candidate key (see candidates()).
    """
    man = manifest()
    for key in candidates(source_id):
        rec = man.get(key)
        rev = _usable(rec, preview)
        if not rev:
            continue
        out = {k: rec.get(k) for k in PUBLIC_KEYS if rec.get(k)}
        out["raster"] = raster_of(rec)
        out["id"] = key
        if rev == "pending":
            out["pending"] = True
        return out
    return None



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
