#!/usr/bin/env python3
"""Fetch one logo per organisation in the org chart and record its source in assets/img/logos/logos.json.

Order of sources (first hit wins):
  1. Wikidata: the item whose official website (P856) matches the org's domain -> logo image (P154) on Wikimedia Commons.
     The file is stored as-is if it is a small, clean SVG; otherwise Commons' own 128px PNG render is saved as WebP.
  2. The organisation's own website: an <img>/<svg> marked "logo" in the page, else the declared SVG icon or apple-touch-icon.
The image itself is never edited (no recolouring or cropping); raster images are only scaled to about 64px tall.
SVGs with scripts, event handlers or external references are rejected. Entries already in logos.json are kept (use --force to refetch).
Entries are written with "review": "pending" – the editor checks each logo against the org before publishing (see logos.json _how_to).
Usage: python3 tools/fetch_logos.py [--force] [id ...]
"""
import html as H, io, json, subprocess, os, re, sys, urllib.parse, urllib.request, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "assets", "img", "logos"); MAN = os.path.join(DIR, "logos.json")
UA = {"User-Agent": "NordicCryptoLogoBot/1.0 (https://jqrgen.github.io/nordic-crypto/; editorial use)"}
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

def get(url, n=3_000_000):
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
    cands.sort(key=lambda c: {"img": 0, "svgicon": 1, "touch": 2}[c[0]])
    for kind, u in cands[:6]:
        try:
            b, ct, _ = get(u)
            if u.lower().split("?")[0].endswith(".svg") or "svg" in ct:
                if clean_svg(b): open(os.path.join(DIR, eid + ".svg"), "wb").write(b); f = eid + ".svg"
                else: continue
            elif to_webp(b, os.path.join(DIR, eid + ".webp")): f = eid + ".webp"
            else: continue
            return {"file": f"assets/img/logos/{f}", "source": "Official website", "source_url": u, "page": final, "kind": kind}
        except Exception as ex: print("   ", eid, kind, u, ex)

def main():
    force = "--force" in sys.argv; only = [a for a in sys.argv[1:] if not a.startswith("--")]
    man = json.load(open(MAN)) if os.path.exists(MAN) else {}
    man.setdefault("_how_to", "One logo per org id. file is relative to the repo root; source_url is where the image was fetched. "
        "review: pending until the editor has checked the logo belongs to the org; build.py only shows logos with review 'ok' (preview: all). "
        "Never edit a logo (colour, crop); raster images are only scaled to about 64px. Refetch: python3 tools/fetch_logos.py --force <id>.")
    org = json.load(open(os.path.join(ROOT, "data", "orgchart.json")))
    today = datetime.date.today().isoformat()
    for e in org["entities"]:
        eid = e["id"]
        if e["type"] == "person" or eid in SKIP or eid in SHARED or (only and eid not in only): continue
        if eid in man and not force: continue
        site = DOMAIN.get(eid) or e.get("url")
        if not site: print("no site", eid); continue
        rec = None
        try:
            qid, fn = wikidata(e["name"], site)
            if fn: rec = commons(fn, eid); rec and rec.update(wikidata=qid)
        except Exception as ex: print("  wd", eid, ex)
        if not rec:
            try: rec = official(site, eid)
            except Exception as ex: print("  site", eid, ex)
        if rec:
            for ext in ("svg", "webp"):  # drop a stale file of the other type
                p = os.path.join(DIR, f"{eid}.{ext}")
                if os.path.exists(p) and not rec["file"].endswith(ext): os.remove(p)
            rec.update(fetched=today, review="pending"); man[eid] = rec; print("ok", eid, rec["source"], rec["file"])
        else: print("none", eid)
        json.dump(man, open(MAN, "w"), ensure_ascii=False, indent=1)
main()
