#!/usr/bin/env python3
"""Fetch one logo per news source in sources.json, so apps can show the outlet's logo next to its stories.

Files go to assets/img/logos/sources/<id>.svg|.webp. Metadata goes to assets/img/logos/logos.json under the key
"source:<id>" (org-chart logos keep their plain org id, so the two never collide). Every new entry has "review": "pending".
The editor (or jQrgen) checks that the image is the outlet's own logo and sets "review": "ok". Only then do /api/v1/sources.json
(logo_url) and /api/v1/news.json (source_logo_url) point at it in the public build. A preview build includes pending logos.

Order of sources (first hit wins):
  1. Wikidata: the item whose official website (P856) is on the outlet's host -> logo image (P154) on Wikimedia Commons.
     Licence and author are copied from the Commons file page. A small, clean SVG is stored as-is, otherwise Commons'
     PNG render is stored as WebP.
  2. The outlet's own site: apple-touch-icon, a large declared icon (>= 96 px or SVG), an <img> marked "logo",
     then og:logo / an og:image whose URL says "logo". Recorded with source_url, the page it was found on, and
     license "Publisher's own logo, used only to identify the source of a headline".
The image itself is never edited (no recolouring or cropping); raster images are only scaled down to about 128 px tall.
Every SVG also gets a PNG rendering next to it (<id>.png, 256 px on the long side, transparent; key "raster"), because Apple's
AsyncImage cannot draw SVG. The API's logo_url always points at a raster file. rsvg-convert is used when installed, else cairosvg.
SVGs with scripts, event handlers or external references are rejected.

Politeness (same rules as fetch.py): our own user agent (sources.json user_agent with "logo" added), robots.txt is checked for
every publisher URL, and there are at least min_delay_seconds (2 s) between two requests to the same host. Wikidata and
Commons are read through their public APIs, one request at a time, following the Wikimedia API etiquette (identifying UA).

Not fetched: search feeds (bing-*, kind "Search feed"), podcasts hosted on a platform (the platform's logo would mislead),
and sources with an `outlet` (they reuse the outlet's logo at build time; tools/api_feed.py resolves that).

Usage: python3 tools/fetch_source_logos.py [--force] [--dry-run] [id ...]
       python3 tools/fetch_source_logos.py --raster-only     # (re)render the PNG for every SVG logo, no network
"""
import datetime, html as H, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from fetch_logos import host  # noqa: E402  (shared helpers; fetch_logos.main() only runs as a script)

LOGOS = os.path.join(ROOT, "assets", "img", "logos")
DIR = os.path.join(LOGOS, "sources")
MAN = os.path.join(LOGOS, "logos.json")
REL = "assets/img/logos/sources"
CFG = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
UA = CFG["user_agent"].replace("; news headline bot)", "; news source logo bot)")
DELAY = CFG.get("min_delay_seconds", 2)
LICENSE_OWN = "Publisher's own logo, used only to identify the source of a headline"
WIKIMEDIA = {"www.wikidata.org", "query.wikidata.org", "commons.wikimedia.org", "upload.wikimedia.org"}
MAX_H = 128

# The logo belongs to a different site than the source url (checked by hand 2026-10-06).
SITE = {"nbx-ir": "https://nbx.com", "reuters-norden": "https://www.reuters.com", "dr-penge": "https://www.dr.dk",
        "kaupr": "https://www.kaupr.io"}
# Logo already in logos.json (an org-chart id, or "source:<id>" for a second feed of the same outlet): reuse that file, no new request.
ORG = {"nbx-ir": "nbx", "kaupr": "kaupr", "digi-krypto": "source:digi"}
# Wikidata items that the name search does not find on its own (checked by hand 2026-10-06).
QID = {}
# The Wikidata "logo" is not a logo (a photo of a sign, a photo of a paper, an 1871 masthead; checked 2026-10-06): use the site.
NO_WIKIDATA = {"riksbank", "mbl", "bt"}
SKIP_KIND = {"Search feed", "Podcast"}
# Logo keys that are not a source id: the outlet that several sources share.
EXTRA = {"kaupr": {"id": "kaupr", "name": "Kaupr", "url": "https://www.kaupr.io"}}

_robots, _last = {}, {}


def throttle(url):
    h = urllib.parse.urlparse(url).netloc
    wait = DELAY - (time.time() - _last.get(h, 0))
    if wait > 0:
        time.sleep(wait)
    _last[h] = time.time()


def robots_ok(url):
    p = urllib.parse.urlparse(url)
    if p.hostname in WIKIMEDIA:
        return True
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            throttle(base)
            r = urllib.request.urlopen(urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA}), timeout=15)
            rp.parse(r.read(500_000).decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as ex:
            if ex.code in (401, 403):
                rp.disallow_all = True
            else:
                rp.parse([])
        except Exception:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)


def get(url, n=3_000_000):
    if not robots_ok(url):
        raise PermissionError("robots.txt disallows " + url)
    throttle(url)
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}), timeout=25)
    return r.read(n), r.headers.get("Content-Type", ""), r.geturl()


def get_json(url):
    return json.loads(get(url)[0])


def save_raster(b, out):
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(b))
    if im.format == "ICO":  # largest frame of a .ico
        try:
            im.size = sorted(im.info.get("sizes") or [im.size])[-1]
        except Exception:
            pass
    im.load()
    if im.width < 48 or im.height < 48:  # a 16/32 px favicon is too small to be a useful logo
        return False
    im = im.convert("RGBA")
    h = min(MAX_H, im.height)
    w = max(1, round(im.width * h / im.height))
    if w > 4 * MAX_H:
        w = 4 * MAX_H
        h = max(1, round(im.height * w / im.width))
    if (w, h) != im.size:
        im = im.resize((w, h), Image.LANCZOS)
    im.save(out, "WEBP", quality=90, method=6)
    return True


def store(key, b, ct, url, svg_max=200_000):
    """Write the image as <key>.svg or <key>.webp. Returns the repo-relative path or None."""
    os.makedirs(DIR, exist_ok=True)
    is_svg = url.lower().split("?")[0].endswith(".svg") or "svg" in (ct or "")
    if is_svg:
        # Same checks as fetch_logos.clean_svg, with a larger size cap (newspaper wordmarks are often 80-200 KB).
        s = b.decode("utf-8", "replace")
        if len(b) > svg_max or "<svg" not in s or re.search(r"<script|\son\w+\s*=|<foreignObject|(?:xlink:)?href\s*=\s*[\"'](?:https?:|//|javascript:)|<iframe|@import", s, re.I):
            return None
        path, other = os.path.join(DIR, key + ".svg"), os.path.join(DIR, key + ".webp")
        open(path, "wb").write(b)
    else:
        path, other = os.path.join(DIR, key + ".webp"), os.path.join(DIR, key + ".svg")
        try:
            if not save_raster(b, path):
                return None
        except Exception:
            return None
    if os.path.exists(other):
        os.remove(other)
    return f"{REL}/{os.path.basename(path)}"


def name_variants(src, site):
    name = src["name"]
    out = [re.sub(r"\s*\(.*?\)", "", name).split(" – ")[0].split(" / ")[0].strip()]
    for m in re.findall(r"\((.*?)\)", name):
        if len(m) > 1 and not re.search(r"latest|business|economy|press|releases|crypto|tag|emne|front|Nordic|Danish|Norway|Sweden|Finland|Denmark", m, re.I):
            out.append(m)
    h = host(site).split(".")[0]
    out.append(h)
    seen, res = set(), []
    for q in out:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            res.append(q)
    return res


def same_site(a, b):
    ha, hb = host(a), host(b)
    return bool(ha) and (ha == hb or ha.endswith("." + hb) or hb.endswith("." + ha))


_by_site = {}


def sparql_sites(sites):
    """One Wikidata query for every site: exact official-website (P856) matches -> {host: [(qid, logo or None)]}."""
    iris = set()
    for site in sites:
        h = host(site)
        for scheme in ("https", "http"):
            for pre in ("", "www."):
                for tail in ("", "/"):
                    iris.add(f"<{scheme}://{pre}{h}{tail}>")
    q = ("SELECT ?item ?site ?logo WHERE { VALUES ?site { " + " ".join(sorted(iris)) + " } ?item wdt:P856 ?site . "
         "OPTIONAL { ?item wdt:P154 ?logo } }")
    throttle("https://query.wikidata.org/")
    req = urllib.request.Request("https://query.wikidata.org/sparql", data=urllib.parse.urlencode({"query": q}).encode(),
                                 headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    js = json.loads(urllib.request.urlopen(req, timeout=90).read())
    for b in js["results"]["bindings"]:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        logo = urllib.parse.unquote(b["logo"]["value"].rsplit("/", 1)[-1]) if "logo" in b else None
        _by_site.setdefault(host(b["site"]["value"]), []).append((qid, logo))


def wikidata(src, site):
    """(qid, logo file name) for the item whose official website is on the source's host."""
    hits = [] if src["id"] in QID else _by_site.get(host(site), [])
    with_logo = [h for h in hits if h[1]]
    if with_logo:  # oldest item first: usually the outlet itself, not a section or a sister product
        return sorted(with_logo, key=lambda h: int(h[0][1:]))[0]
    ids = [QID[src["id"]]] if src["id"] in QID else []
    if not ids:
        for q in name_variants(src, site):
            js = get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
                {"action": "wbsearchentities", "search": q, "language": "en", "uselang": "en", "limit": 7, "format": "json"}))
            for it in js.get("search", []):
                if it["id"] not in ids:
                    ids.append(it["id"])
    ents = get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "wbgetentities", "ids": "|".join(ids[:40]), "props": "claims", "format": "json"}))["entities"] if ids else {}
    for qid in ids[:40]:
        ent = ents.get(qid) or {}
        cl = ent.get("claims", {})
        sites = [c["mainsnak"].get("datavalue", {}).get("value", "") for c in cl.get("P856", [])]
        if not (src["id"] in QID or any(same_site(s, site) for s in sites)):
            continue
        logos = [c["mainsnak"].get("datavalue", {}).get("value") for c in cl.get("P154", []) if c.get("rank") != "deprecated"]
        pref = [c["mainsnak"].get("datavalue", {}).get("value") for c in cl.get("P154", []) if c.get("rank") == "preferred"]
        fn = (pref or logos or [None])[0]
        return ent.get("id", qid), fn
    return None, None


def commons(fname, key):
    api = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "titles": "File:" + fname, "prop": "imageinfo",
          "iiprop": "url|extmetadata|size|mime", "iiurlheight": 2 * MAX_H, "format": "json"})
    pg = next(iter(get_json(api)["query"]["pages"].values()))
    ii = pg["imageinfo"][0]
    md = ii.get("extmetadata", {})
    lic = md.get("LicenseShortName", {}).get("value", "")
    lic_url = md.get("LicenseUrl", {}).get("value") or None
    art = re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "")).strip()
    rec = {"source": "Wikimedia Commons", "source_url": ii["descriptionurl"], "license": lic, "license_url": lic_url, "author": art or None}
    f = None
    if fname.lower().endswith(".svg"):
        b, ct, _ = get(ii["url"])
        f = store(key, b, "image/svg+xml", ii["url"])
    if not f:
        u = ii.get("thumburl") or ii["url"]
        b, ct, _ = get(u)
        f = store(key, b, ct, u)
    if f:
        rec["file"] = f
        return rec
    return None


def _attr(tag, name):
    m = re.search(r"\s" + name + r"\s*=\s*([\"'])(.*?)\1", tag, re.I | re.S)
    return H.unescape(m.group(2)) if m else None


def official(site, key):
    page, ct, final = get(site)
    page = page.decode("utf-8", "replace")
    head = page  # get() caps the page at 3 MB; some <head>s carry > 400 KB of inline CSS before the icon links
    cands = []  # (priority, size, kind, url)
    for m in re.finditer(r"<link\b[^>]*>", head, re.I):
        tag = m.group(0)
        rel, href = (_attr(tag, "rel") or "").lower(), _attr(tag, "href")
        if not href or href.startswith("data:"):
            continue
        u = urllib.parse.urljoin(final, href)
        sizes = _attr(tag, "sizes") or ""
        px = max([int(x) for x in re.findall(r"(\d+)x\d+", sizes)] or [0])
        if "apple-touch-icon" in rel:
            cands.append((0, -(px or 180), "apple-touch-icon", u))
        elif "icon" in rel.split() or rel == "shortcut icon":
            if ".svg" in href.lower() or "svg" in (_attr(tag, "type") or ""):
                cands.append((1, 0, "svg-icon", u))
            elif px >= 96:
                cands.append((1, -px, "icon", u))
    for m in re.finditer(r"<img\b[^>]*>", head, re.I):
        tag = m.group(0)
        # Only an <img> that is marked logo AND names the outlet: partner/customer logos on the page must never match.
        if not re.search(r"logo", tag, re.I) or host(site).split(".")[0].lower() not in tag.lower():
            continue
        src = _attr(tag, "src")
        if src and not src.startswith("data:"):
            cands.append((2, 0, "img-logo", urllib.parse.urljoin(final, src)))
    for m in re.finditer(r"<meta\b[^>]*>", head, re.I):
        tag = m.group(0)
        prop = (_attr(tag, "property") or _attr(tag, "name") or "").lower()
        c = _attr(tag, "content")
        if c and (prop == "og:logo" or (prop == "og:image" and "logo" in c.lower())):
            cands.append((3, 0, prop, urllib.parse.urljoin(final, c)))
    if not any(k == "apple-touch-icon" for _, _, k, _ in cands):  # the conventional path, when the page declares none
        cands.append((0, 0, "apple-touch-icon", urllib.parse.urljoin(final, "/apple-touch-icon.png")))
    cands.sort(key=lambda c: (c[0], c[1]))
    seen = set()
    for _, _, kind, u in cands:
        if u in seen:
            continue
        seen.add(u)
        if len(seen) > 6:
            break
        try:
            b, ct, _ = get(u)
            if "html" in (ct or ""):
                continue
            f = store(key, b, ct, u)
            if f:
                return {"file": f, "source": "Official website", "source_url": u, "page": final, "kind": kind, "license": LICENSE_OWN}
        except Exception as ex:
            print("   ", key, kind, u, type(ex).__name__, str(ex)[:120])
    return None


def targets():
    """(logo key, source row) for every source that gets its own logo, plus why the others are skipped."""
    ids = {s["id"] for s in CFG["sources"]}
    out, skipped = [], {}
    for s in CFG["sources"]:
        if s.get("outlet"):
            skipped[s["id"]] = f"uses the logo of outlet {s['outlet']}"
            continue
        if s.get("kind") in SKIP_KIND or s.get("type") == "bing" and s["id"] != "reuters-norden":
            skipped[s["id"]] = f"{s.get('kind') or s.get('type')}: no single outlet logo"
            continue
        out.append((s["id"], s))
    for k, s in EXTRA.items():
        if k not in ids:
            out.append((k, s))
    return out, skipped


RASTER_PX = 256


def rasterize(svg, png):
    """SVG -> PNG, RASTER_PX on the long side, transparent background (Apple's AsyncImage cannot draw SVG).
    Uses rsvg-convert when installed, else the cairosvg Python package. Returns True on success."""
    import shutil
    import subprocess
    if shutil.which("rsvg-convert"):
        r = subprocess.run(["rsvg-convert", "--keep-aspect-ratio", "-w", str(RASTER_PX), "-h", str(RASTER_PX), "-f", "png", "-o", png, svg],
                           capture_output=True, timeout=60)
        ok = r.returncode == 0
    else:
        try:
            import cairosvg
        except ImportError:
            print("  raster: install rsvg-convert (librsvg) or `pip install cairosvg`", file=sys.stderr)
            return False
        from PIL import Image
        cairosvg.svg2png(url=svg, write_to=png, output_height=RASTER_PX)
        im = Image.open(png)
        if max(im.size) > RASTER_PX:  # a wide wordmark: fit the long side instead
            cairosvg.svg2png(url=svg, write_to=png, output_width=RASTER_PX)
        ok = True
    if ok and os.path.exists(png) and os.path.getsize(png) > 0:
        return True
    if os.path.exists(png):
        os.remove(png)
    return False


def ensure_raster(key, rec):
    """Every source logo gets a raster: an SVG gets <key>.png next to it ("raster"); WebP files are already raster."""
    f = rec.get("file") or ""
    if not f.endswith(".svg"):
        rec.pop("raster", None)
        return True
    rel = f"{REL}/{key}.png"
    if rec.get("raster") == rel and os.path.exists(os.path.join(ROOT, rel)):
        return True
    if rasterize(os.path.join(ROOT, f), os.path.join(ROOT, rel)):
        rec["raster"] = rel
        return True
    rec.pop("raster", None)
    return False


def main():
    force = "--force" in sys.argv
    dry = "--dry-run" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    man = json.load(open(MAN, encoding="utf-8")) if os.path.exists(MAN) else {}
    if "--raster-only" in sys.argv:  # no network: (re)write the PNG for every SVG source logo
        bad = [k for k, v in man.items() if k.startswith("source:") and isinstance(v, dict) and not ensure_raster(k[7:], v)]
        json.dump(man, open(MAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n = sum(1 for k, v in man.items() if k.startswith("source:") and isinstance(v, dict))
        print(f"raster: {n - len(bad)} of {n} source logos have a raster file" + (f"; failed: {', '.join(bad)}" if bad else ""))
        return
    man.setdefault("_how_to_sources", "Keys 'source:<id>' are news-source logos (id from sources.json, or an outlet shared by several "
                   "sources such as 'kaupr'), fetched by tools/fetch_source_logos.py into assets/img/logos/sources/. Same review rule: "
                   "pending until the editor has checked the image is that outlet's own logo; then set review 'ok'. Only 'ok' logos "
                   "appear as logo_url / source_logo_url in the public API (preview: pending too). Raster images are scaled to about "
                   "128 px tall, never otherwise edited; an SVG also gets a 256 px PNG ('raster'), which the API serves as logo_url. These are the publishers' trademarks, shown only to identify the source of a "
                   "headline. Refetch: python3 tools/fetch_source_logos.py --force <id>.")
    today = datetime.date.today().isoformat()
    todo, skipped = targets()
    got, none = [], []
    if not dry:
        try:
            sparql_sites([SITE.get(k) or s.get("url") for k, s in todo if (not only or k in only) and (force or "source:" + k not in man)])
        except Exception as ex:
            print("  sparql", type(ex).__name__, str(ex)[:160], "(falling back to name search)")
    for key, src in todo:
        if only and key not in only:
            continue
        mk = "source:" + key
        if mk in man and not force:
            got.append(key)
            continue
        site = SITE.get(key) or src.get("url")
        if dry:
            print("would fetch", key, site)
            continue
        rec = None
        org = man.get(ORG.get(key, ""))
        if org and org.get("file") and org.get("review", "ok") != "rejected":
            rec = {k: org[k] for k in ("file", "source", "source_url", "page", "kind", "license", "license_url", "author", "wikidata") if org.get(k)}
            rec["same_as"] = ORG[key]
            if not rec.get("license") and rec.get("source") == "Official website":
                rec["license"] = LICENSE_OWN
        try:
            qid, fn = wikidata(src, site) if not rec and key not in NO_WIKIDATA else (None, None)
            if fn:
                rec = commons(fn, key)
                if rec:
                    rec["wikidata"] = qid
            elif qid:
                print("  wd", key, qid, "has no logo (P154)")
        except Exception as ex:
            print("  wd", key, type(ex).__name__, str(ex)[:160])
        if not rec:
            try:
                rec = official(site, key)
            except Exception as ex:
                print("  site", key, type(ex).__name__, str(ex)[:160])
        if rec:
            rec = {k: v for k, v in rec.items() if v is not None}
            rec.update(source_id=key, outlet=src["name"], fetched=today, review="pending")
            if not ensure_raster(key, rec):
                print("  raster", key, "could not render", rec["file"])
            man[mk] = rec
            got.append(key)
            print("ok  ", key, rec["source"], rec["file"], flush=True)
        else:
            none.append(key)
            old = man.pop(mk, None)  # --force: a refetch that finds nothing drops the old entry and its file
            for f in ((old or {}).get("file", ""), (old or {}).get("raster", "")):
                if f.startswith(REL + "/") and os.path.exists(os.path.join(ROOT, f)):
                    os.remove(os.path.join(ROOT, f))
            print("none", key, site, flush=True)
        json.dump(man, open(MAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{len(got)} with a logo, {len(none)} without: {', '.join(none) or '-'}")
    print(f"{len(skipped)} skipped: " + "; ".join(f"{k} ({v})" for k, v in skipped.items()))


if __name__ == "__main__":
    main()
