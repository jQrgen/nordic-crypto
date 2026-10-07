#!/usr/bin/env python3
"""Fetch one logo per organisation and per news outlet, and record it in assets/img/logos/logos.json.

Order of sources (first hit wins):
  1. Wikidata: the item whose official website (P856) matches the org's domain -> logo image (P154) on Wikimedia Commons.
     The file is stored as-is if it is a small, clean SVG; otherwise Commons' own 128px PNG render is saved as WebP.
  2. The organisation's own website: an <img>/<svg> marked "logo" in the page, else the declared SVG icon or apple-touch-icon.
The image itself is never edited (no recolouring or cropping); raster images are only scaled to about 64px tall.
SVGs with scripts, event handlers or external references are rejected. Entries already in logos.json are kept (use --force to refetch).
Entries are written with "review": "pending" – the editor checks each logo before publishing (see logos.json _how_to).
Nothing is drawn when a source has no file. News ids that share a who's-who logo are listed in _source_alias and are not fetched again.
Usage: python3 tools/fetch_logos.py [--force] [id ...]
"""
import html as H, io, json, subprocess, os, re, sys, threading, time, urllib.parse, urllib.request, urllib.robotparser, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import site_url
DIR = os.path.join(ROOT, "assets", "img", "logos"); MAN = os.path.join(DIR, "logos.json")
UA = {"User-Agent": f"NordicCryptoLogoBot/1.0 ({site_url.BASE}; editorial use)"}
# Official domains for orgs whose data entry has no url (checked by hand 2026-10-03).
DOMAIN = {"stortinget-finanskomiteen": "https://www.stortinget.no", "finansdepartementet": "https://www.regjeringen.no", "fma": "https://www.regjeringen.no",
  "finanstilsynet": "https://www.finanstilsynet.no", "norges-bank": "https://www.norges-bank.no", "skatteetaten": "https://www.skatteetaten.no",
  "okokrim": "https://www.okokrim.no", "dfd": "https://www.regjeringen.no", "energidepartementet": "https://www.regjeringen.no", "nkom": "https://www.nkom.no",
  "nve": "https://www.nve.no", "statnett": "https://www.statnett.no", "esma": "https://www.esma.europa.eu", "eba": "https://www.eba.europa.eu",
  "firi": "https://firi.com", "nbx": "https://nbx.com", "k33": "https://k33.com", "bare-bitcoin": "https://barebitcoin.no", 
  "dnb": "https://www.dnb.no", "seetee": "https://seetee.io", "schibsted-ventures": "https://schibsted.com", "bpi": "https://bpinorge.no",
  "finans-norge": "https://www.finansnorge.no", "nordic-blockchain-association": "https://www.nordicblockchain.com", "fintech-norway": "https://fintechnorway.com",
  "kaupr": "https://www.kaupr.io", "valuno": "https://valuno.com", "virtune": "https://www.virtune.com", "is-sfl": "https://www.logreglan.is",
  "intl-binance": "https://www.binance.com", "shifter": "https://www.shifter.no", "greenmerc": "https://greenmerc.com", "ak-jensen-norway": "https://www.akj.com", "tydal-data-center": "https://www.bitdeer.com"}
SKIP = {"kryptoeiendelsloven", "is-act-101-2025", "nedlagte-vekslere-2026", "norges-bank-tokenisering", "sparebank-1-bankene", "nkom-kryptoutvinnere",
        "finanswatch-e24-dn-finansavisen-okonomi24", "nrk-klassekampen-inyheter"}  # acts and groupings: no single logo
# Several entities share one ministry website; a shared logo would mislead, so they get the initials fallback.
SHARED = {"fma", "dfd", "energidepartementet", "finansdepartementet", "se-finansdepartementet", "is-fjr", "is-fme", "fi-fiu", "se-finanspolisen"}

_pace_guard = threading.Lock()
_pace_locks, _pace_last = {}, {}
_robots, _robots_lock = {}, threading.Lock()

def _pace(url):
    host = urllib.parse.urlparse(url).hostname or ""
    with _pace_guard:
        lock = _pace_locks.setdefault(host, threading.Lock())
    with lock:
        wait = 0.3 - (time.time() - _pace_last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _pace_last[host] = time.time()

def robots_ok(url):
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        return False
    base = f"{p.scheme}://{p.netloc}"
    with _robots_lock:
        rp = _robots.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            _pace(base + "/robots.txt")
            body, _, _ = _fetch(base + "/robots.txt", n=200_000)
            rp.parse(body.decode("utf-8", "replace").splitlines())
        except Exception:
            rp.parse([])
        with _robots_lock:
            _robots[base] = rp
    return rp.can_fetch(UA["User-Agent"], url)

def get(url, n=3_000_000):
    _pace(url)
    return _fetch(url, n)

def _fetch(url, n=3_000_000):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20)
        return r.read(n), r.headers.get("Content-Type", ""), r.geturl()
    except Exception as ex:  # some TLS stacks / WAFs reject urllib; retry once with curl (same request, browser-like UA)
        if isinstance(ex, urllib.error.HTTPError) and ex.code == 404: raise
        out = subprocess.run(["curl", "-sSL", "--max-time", "20", "-A", "Mozilla/5.0 (X11; Linux x86_64) NordicCryptoLogoBot/1.0", "-w", "\n%{content_type}\n%{url_effective}", url],
                             capture_output=True, timeout=30)
        if out.returncode: raise
        body, ct, final = out.stdout.rsplit(b"\n", 2)
        return body[:n], ct.decode(), final.decode()
def host(u): return (urllib.parse.urlparse(u).hostname or "").lower().removeprefix("www.")
def clean_svg(b):
    s = b.decode("utf-8", "replace")
    if "<svg" not in s or len(b) > 80_000: return False
    return not re.search(r"<script|\son\w+\s*=|<foreignObject|(?:xlink:)?href\s*=\s*[\"'](?:https?:|//|javascript:)|<iframe|@import", s, re.I)
def to_webp(b, out):
    from PIL import Image
    im = Image.open(io.BytesIO(b)); im.load()
    if im.width < 16 or im.height < 16: return False
    im = im.convert("RGBA"); h = 64 if im.height > 64 else im.height
    w = max(1, round(im.width * h / im.height)); im = im.resize((min(w, 256), h), Image.LANCZOS) if (w, h) != im.size else im
    im.save(out, "WEBP", quality=90, method=6); return True

def wikidata(name, site):
    q = re.sub(r"\s*\(.*?\)", "", name).split(" – ")[0].strip()
    js = json.loads(get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbsearchentities", "search": q, "language": "en", "limit": 7, "format": "json"}))[0])
    for it in js.get("search", []):
        ent = json.loads(get(f"https://www.wikidata.org/wiki/Special:EntityData/{it['id']}.json")[0])["entities"][it["id"]]
        cl = ent.get("claims", {})
        sites = [c["mainsnak"].get("datavalue", {}).get("value", "") for c in cl.get("P856", [])]
        if not any(host(s) == host(site) for s in sites): continue
        logos = [c["mainsnak"].get("datavalue", {}).get("value") for c in cl.get("P154", [])]
        if logos and logos[0]: return it["id"], logos[0]
        return it["id"], None
    return None, None
def commons(fname, eid):
    api = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "titles": "File:" + fname, "prop": "imageinfo",
          "iiprop": "url|extmetadata|size", "iiurlheight": 128, "format": "json"})
    pg = next(iter(json.loads(get(api)[0])["query"]["pages"].values())); ii = pg["imageinfo"][0]; md = ii.get("extmetadata", {})
    lic = md.get("LicenseShortName", {}).get("value", ""); art = re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "")).strip()
    rec = {"source": "Wikimedia Commons", "source_url": ii["descriptionurl"], "license": lic, "author": art or None}
    if fname.lower().endswith(".svg"):
        b = get(ii["url"])[0]
        if clean_svg(b):
            open(os.path.join(DIR, eid + ".svg"), "wb").write(b); rec["file"] = f"assets/img/logos/{eid}.svg"; return rec
    b = get(ii.get("thumburl") or ii["url"])[0]
    if to_webp(b, os.path.join(DIR, eid + ".webp")): rec["file"] = f"assets/img/logos/{eid}.webp"; return rec
def official(site, eid):
    html, ct, final = get(site); html = html.decode("utf-8", "replace")
    cands = []
    for m in re.finditer(r"<img\b[^>]*>", html, re.I):
        tag = m.group(0)
        if not re.search(r"logo", tag, re.I): continue
        src = re.search(r"\ssrc\s*=\s*[\"']([^\"']+)", tag, re.I)
        if src and not src.group(1).startswith("data:"): cands.append(("img", urllib.parse.urljoin(final, H.unescape(src.group(1)))))
    for m in re.finditer(r"<link\b[^>]*>", html, re.I):
        tag = m.group(0); rel = re.search(r"rel\s*=\s*[\"']([^\"']+)", tag, re.I); href = re.search(r"href\s*=\s*[\"']([^\"']+)", tag, re.I)
        if not (rel and href): continue
        r = rel.group(1).lower()
        if "apple-touch-icon" in r: cands.append(("touch", urllib.parse.urljoin(final, H.unescape(href.group(1)))))
        elif "icon" in r and (".svg" in href.group(1) or "svg" in tag): cands.append(("svgicon", urllib.parse.urljoin(final, H.unescape(href.group(1)))))
        elif "icon" in r and "mask-icon" not in r: cands.append(("icon", urllib.parse.urljoin(final, H.unescape(href.group(1)))))
    # The outlet's own icon first. A white "negative" wordmark is kept as a last resort (it disappears on a white page).
    def rank(c):
        kind, u = c
        base = {"touch": 0, "svgicon": 1, "icon": 2, "img": 3}[kind]
        if re.search(r"negativ|negative|white|hvit|vit\.|-neg", u, re.I):
            base += 5
        return base
    cands.sort(key=rank)
    for kind, u in cands[:8]:
        try:
            b, ct, _ = get(u)
            if u.lower().split("?")[0].endswith(".svg") or "svg" in ct:
                if clean_svg(b): open(os.path.join(DIR, eid + ".svg"), "wb").write(b); f = eid + ".svg"
                else: continue
            elif to_webp(b, os.path.join(DIR, eid + ".webp")): f = eid + ".webp"
            else: continue
            return {"file": f"assets/img/logos/{f}", "source": "Official website", "source_url": u, "page": final, "kind": kind}
        except Exception as ex: print("   ", eid, kind, u, ex)

HOW = ("One logo per id. News articles use the source id on the story (the same id as sources.json). "
       "If that source has outlet, the outlet id is used. _source_alias maps a source id onto another key when the who's-who id differs. "
       "file is relative to the repo root; source_url is where the image was fetched (also copied to sources.json logo_source). "
       "A news source whose file is the outlet's own logo, favicon or apple-touch icon is review ok: nominative use, "
       "small, unaltered except a raster scale to about 64px, linked to the outlet, no endorsement. "
       "Terms that explicitly forbid logo use are review rejected and the name stays text. "
       "Other new files stay pending until an editor checks them. The public build shows review ok only "
       "(a missing review counts as ok) and --preview also shows pending. rejected, a missing file, or no entry: the source name is text only. "
       "Never invent a logo and never edit one (colour, crop). "
       "News sources: python3 tools/fetch_logos.py --sources. One id: python3 tools/fetch_logos.py --sources <id>.")

_man_lock = threading.Lock()

def store(man, eid, rec, today, review=None):
    with _man_lock:
        for ext in ("svg", "webp"):  # drop a stale file of the other type
            p = os.path.join(DIR, f"{eid}.{ext}")
            if os.path.exists(p) and not rec["file"].endswith(ext): os.remove(p)
        rev = review or rec.get("review") or "pending"
        rec.update(fetched=today, review=rev)
        man[eid] = rec
        json.dump(man, open(MAN, "w"), ensure_ascii=False, indent=1)
    print("ok", eid, rec["source"], rec["file"])

def fetch_logo(eid, name, site):
    rec = None
    try:
        qid, fn = wikidata(name, site)
        if fn:
            rec = commons(fn, eid)
            if rec: rec["wikidata"] = qid
    except Exception as ex:
        print("  wd", eid, ex)
    if not rec:
        try:
            rec = official(site, eid)
        except Exception as ex:
            print("  site", eid, ex)
    return rec

NOMINATIVE = ("Nominative use of the outlet's own mark. Unaltered except a raster scale to about 64px. "
               "Shown only to identify the source, linked to the outlet. No endorsement.")

def terms_pages(site, html, final):
    """Homepage plus up to two linked terms pages on the same site."""
    import logo_policy
    chunks = [html or ""]
    hrefs = []
    for m in re.finditer(r'<a\b[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', html or "", re.I | re.S):
        href, text = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
        blob = href + " " + text
        if re.search(r"vilkår|villkor|vilkar|terms|legal|juridisk|käyttöehdot|skilmálar|opphavsrett|copyright|varemerke|varumärke|trademark", blob, re.I):
            hrefs.append(urllib.parse.urljoin(final or site, href))
    seen = set()
    home = logo_policy._host(final or site)
    for u in hrefs:
        if u in seen or logo_policy._host(u) != home:
            continue
        seen.add(u)
        if len(seen) > 1:
            break
        try:
            b, _, _ = get(u, n=180_000)
            chunks.append(b.decode("utf-8", "replace"))
        except Exception:
            continue
    return "\n".join(chunks)

def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

def write_provenance(man):
    """Copy each stored logo's source URL onto every source that uses that mark."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import source_logos
    path = os.path.join(ROOT, "sources.json")
    cfg = json.load(open(path, encoding="utf-8"))
    changed = False
    for s in cfg.get("sources") or []:
        if s.get("type") == "bing" or s.get("logo_skipped"):
            continue
        key = source_logos.canonical_id(s.get("id"))
        rec = man.get(key) if key and isinstance(man.get(key), dict) else None
        if not rec or rec.get("review") == "rejected" or not str(rec.get("source_url") or "").startswith("http"):
            continue
        if s.get("logo_source") != rec["source_url"]:
            s["logo_source"] = rec["source_url"]
            changed = True
    if changed:
        _dump(path, cfg)
    return changed

def fetch_source_logos(force=False, only=None):
    """Fetch or accept a logo for every news source. Own marks are review ok."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import source_logos, logo_policy
    man = json.load(open(MAN)) if os.path.exists(MAN) else {}
    man["_how_to"] = HOW
    today = datetime.date.today().isoformat()
    by = source_logos.sources_by_id()
    # Promote marks we already stored, then fill the gaps.
    for s in source_logos.sources():
        if s.get("type") == "bing":
            continue
        key = source_logos.canonical_id(s["id"], by, source_logos.aliases())
        rec = man.get(key) if key and isinstance(man.get(key), dict) else None
        if not rec or not rec.get("file") or not os.path.exists(os.path.join(ROOT, rec["file"])):
            continue
        if rec.get("review") == "ok" and not force:
            continue
        if rec.get("review") == "rejected" and not force:
            continue
        home = (by.get(key) or s).get("url") or s.get("url")
        if not logo_policy.own_mark(rec, home, (by.get(key) or s).get("name") or s.get("name") or ""):
            continue
        forbid = None
        if home and source_logos.usable_homepage(home):
            try:
                html, _, final = get(home, n=250_000)
                html = html.decode("utf-8", "replace")
                forbid = logo_policy.terms_forbid_logo(terms_pages(home, html, final))
            except Exception as ex:
                print("  terms", key, type(ex).__name__)
        if forbid:
            print("skip-terms", key, forbid)
            p = os.path.join(ROOT, rec["file"])
            if os.path.exists(p):
                os.remove(p)
            man[key] = {"review": "rejected", "reason": "terms forbid logo use", "quote": forbid, "fetched": today}
            continue
        rec["review"] = "ok"
        rec["use"] = "nominative"
        rec.setdefault("note", NOMINATIVE)
        rec.setdefault("reviewed", today + " (outlet's own mark)")
        man[key] = rec
        print("ok-own", key, rec.get("source_url"))
    _dump(MAN, man)
    jobs = source_logos.outlets_to_fetch(man, force=force, only=only)
    print("to fetch", len(jobs))
    cfg_path = os.path.join(ROOT, "sources.json")
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    skipped = {s["id"]: s for s in cfg.get("sources") or []}

    def one(job):
        if not robots_ok(job["url"]):
            print("robots", job["id"])
            with _man_lock:
                row = skipped.get(job["id"])
                if row is not None and not row.get("logo_note"):
                    row["logo_note"] = "robots.txt disallows the homepage, so no logo was fetched. Text only."
            return
        forbid = None
        try:
            html, _, final = get(job["url"], n=400_000)
            html = html.decode("utf-8", "replace")
            blob = terms_pages(job["url"], html, final)
            forbid = logo_policy.terms_forbid_logo(blob)
        except Exception as ex:
            print("  home", job["id"], type(ex).__name__)
            html = ""
        if forbid:
            print("skip-terms", job["id"], forbid)
            with _man_lock:
                row = skipped.get(job["id"])
                if row is not None:
                    row["logo_skipped"] = "terms forbid logo use"
                    row["logo_note"] = "Terms forbid logo use (" + forbid + "). Text only."
                    row.pop("logo_source", None)
                rec = man.get(job["id"])
                if isinstance(rec, dict) and rec.get("file"):
                    p = os.path.join(ROOT, rec["file"])
                    if os.path.exists(p):
                        os.remove(p)
                if isinstance(rec, dict):
                    man[job["id"]] = {"review": "rejected", "reason": "terms forbid logo use", "quote": forbid, "fetched": today}
            return
        rec = None
        try:
            rec = official(job["url"], job["id"])
        except Exception as ex:
            print("  site", job["id"], type(ex).__name__)
        if rec and logo_policy.bad_image_url(rec.get("source_url")):
            rec = None
        if not rec:
            print("none", job["id"])
            return
        if logo_policy.own_mark(rec, job["url"], job.get("name") or ""):
            rec["review"] = "ok"
            rec["use"] = "nominative"
            rec["note"] = NOMINATIVE
            rec["reviewed"] = today + " (outlet's own mark)"
            store(man, job["id"], rec, today, review="ok")
        else:
            for ext in ("svg", "webp"):
                p = os.path.join(DIR, job["id"] + "." + ext)
                prev = man.get(job["id"]) if isinstance(man.get(job["id"]), dict) else {}
                if os.path.exists(p) and not str(prev.get("file") or "").endswith("." + ext):
                    os.remove(p)
            print("not-own", job["id"])

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(one, job) for job in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                fut.result()
            except Exception as ex:
                print("job", type(ex).__name__, ex)
            if i % 40 == 0:
                print(f"logos {i}/{len(jobs)}", flush=True)
                with _man_lock:
                    _dump(MAN, man)
                    _dump(cfg_path, cfg)
    _dump(MAN, man)
    _dump(cfg_path, cfg)
    write_provenance(man)

def main():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import source_logos
    if "--sources" in sys.argv:
        only = [a for a in sys.argv[1:] if not a.startswith("--")]
        fetch_source_logos(force="--force" in sys.argv, only=only or None)
        return
    force = "--force" in sys.argv; only = [a for a in sys.argv[1:] if not a.startswith("--")]
    man = json.load(open(MAN)) if os.path.exists(MAN) else {}
    if not str(man.get("_how_to") or "").startswith("One logo per id"):
        man["_how_to"] = HOW
    org = json.load(open(os.path.join(ROOT, "data", "orgchart.json")))
    today = datetime.date.today().isoformat()
    for e in org["entities"]:
        eid = e["id"]
        if e["type"] == "person" or eid in SKIP or eid in SHARED or (only and eid not in only): continue
        if eid in man and not force: continue
        site = DOMAIN.get(eid) or e.get("url")
        if not site: print("no site", eid); continue
        rec = fetch_logo(eid, e["name"], site)
        if rec: store(man, eid, rec, today)
        else: print("none", eid)
    for job in source_logos.outlets_to_fetch(man, force=force, only=only):
        print("news", job["id"], job["url"])
        rec = fetch_logo(job["id"], job["name"], job["url"])
        if rec: store(man, job["id"], rec, today)
        else: print("none", job["id"])
if __name__ == "__main__":  # tools/fetch_source_logos.py imports the helpers above
    main()
