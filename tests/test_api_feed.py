#!/usr/bin/env python3
"""Checks the public JSON API: approved news and newsletters only, stable URLs, no private fields.
  python3 tests/test_api_feed.py
Does not run the full site build (that needs the editor queue and the research workspace)."""
import json, os, re, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import api_feed
import build
import markets

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
BANNED = api_feed.BANNED_KEYS | {"_how_to", "_note"}

def walk(obj, where, hits):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in BANNED or str(k).startswith("_"):
                hits.append(f"{where}.{k}")
            walk(v, f"{where}.{k}", hits)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{where}[{i}]", hits)
    elif isinstance(obj, str):
        if "/workspace/" in obj or "private_terms" in obj or "tips.db" in obj:
            hits.append(f"{where}: local path")
        if EMAIL.search(re.sub(r"https?://\S+", " ", obj)):
            hits.append(f"{where}: email")

def _markets_fixture():
    fetched = "2026-10-05T12:00:00+00:00"
    rows = markets.parse_firi(
        [{"id": "BTCNOK", "last": "100.5", "high": "101", "low": "99", "volume": "1", "change": "0.1"}],
        [{"market": "BTCNOK", "bid": "100", "ask": "101"}],
        fetched,
    )
    body = markets.empty_failure("fixture")
    body["tickers"] = rows
    body["count"] = len(rows)
    for ex in body["exchanges"]:
        if ex["id"] == "firi":
            ex["status"] = "ok"
            ex["error"] = None
            ex["ticker_count"] = len(rows)
    return body


def meta_ios_later(tmp):
    meta = json.load(open(os.path.join(tmp, "api/v1/meta.json"), encoding="utf-8"))
    return (meta.get("ios") or {}).get("url")


def _write(tmp, ctx, preview):
    ev = ctx["events"][0] if isinstance(ctx["events"], tuple) else ctx["events"]
    return api_feed.write(
        tmp, preview=preview, base=build.BASE,
        items=ctx["items"], events=ev, entities=ctx["ents"], relations=ctx["rels"],
        org_updated=ctx["org"].get("updated"), regulation=ctx["org"].get("regulation") or [],
        caveats=ctx["org"].get("caveats") or [], sources_cfg=ctx["cfg"],
        news_updated=ctx["news"].get("updated"), markets=_markets_fixture(),
    )


def source_logos(fails):
    """logo_url / source_logo_url are null unless the logo's review is 'ok' (preview: 'pending' too, never 'rejected')."""
    ctx = api_feed.repo_context(False)
    real = json.load(open(api_feed.source_logos.MANIFEST, encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:  # the committed manifest, public build
        _write(tmp, ctx, False)
        srcs = json.load(open(os.path.join(tmp, "api/v1/sources.json"), encoding="utf-8"))
        for s in srcs["sources"]:
            if "logo_url" not in s or "logo" not in s:
                fails.append("sources.json row without logo_url/logo: " + s["id"])
                continue
            if s["logo_url"]:
                lg = api_feed.source_logos.for_source(s["id"], preview=False)
                if not lg or (real.get(lg["id"]) or {}).get("review", "ok") != "ok":
                    fails.append("unapproved source logo in public build: " + s["id"])
                if not s["logo_url"].lower().endswith((".png", ".webp")) or s["logo_url"] != (s["logo"] or {}).get("raster_url"):
                    fails.append("logo_url is not the raster of logo: " + s["id"])
                if not s["logo_url"].startswith(build.BASE) or not os.path.exists(os.path.join(tmp, s["logo_url"][len(build.BASE):])):
                    fails.append("source logo file not in site: " + s["id"])
        news = json.load(open(os.path.join(tmp, "api/v1/news.json"), encoding="utf-8"))
        if any("source_logo_url" not in n for n in news["items"]):
            fails.append("news item without source_logo_url")
        for n in news["items"]:
            if n.get("source_logo_url") != ((n.get("source_logo") or {}).get("raster_url")):
                fails.append("source_logo_url differs from source_logo.raster_url: " + n["id"])
        if not srcs.get("logo_note") or "trademark" not in srcs["logo_note"]:
            fails.append("sources.json logo_note")
    # Every SVG a news source can resolve to has a PNG rendering (Apple's AsyncImage cannot draw SVG).
    for sid in [x["id"] for x in ctx["cfg"]["sources"]] + [i.get("source") for i in ctx["items"] if i.get("source")]:
        for preview in (False, True):
            lg = api_feed.source_logos.for_source(sid, preview=preview)
            if lg and str(lg["file"]).endswith(".svg") and not str(lg.get("raster") or "").endswith(".png"):
                fails.append(f"SVG logo without a PNG raster: {sid} -> {lg['id']}")
    svg, png = "assets/img/logos/sources/vg.svg", "assets/img/logos/sources/vg.png"
    fixture = {
        "source:e24": {"file": svg, "raster": png, "source": "Official website", "source_url": "https://e24.no/x.png",
                       "license": "Publisher's own logo, used only to identify the source of a headline", "review": "ok"},
        "source:nrk": {"file": svg, "raster": png, "source": "Wikimedia Commons", "source_url": "https://commons.wikimedia.org/wiki/File:X.svg",
                       "license": "Public domain", "review": "ok"},
        "source:svd": {"file": svg, "source": "Wikimedia Commons", "source_url": "https://commons.wikimedia.org/wiki/File:Y.svg",
                       "license": "Public domain", "review": "ok"},  # SVG without a raster: logo listed, logo_url null
        "source:kaupr": {"file": "assets/img/logos/kaupr.webp", "source": "Official website", "source_url": "https://www.kaupr.io/x.png", "review": "ok"},
        "source:vg": {"file": svg, "raster": png, "source": "Official website", "source_url": "https://www.vg.no/x.png", "review": "pending"},
        "source:dn": {"file": svg, "raster": png, "source": "Official website", "source_url": "https://www.dn.no/x.png", "review": "rejected"},
    }
    saved = api_feed.source_logos.MANIFEST
    with tempfile.TemporaryDirectory() as tmp:
        man = os.path.join(tmp, "logos.json")
        json.dump(fixture, open(man, "w", encoding="utf-8"))
        api_feed.source_logos.MANIFEST = man
        try:
            for preview in (False, True):
                out = os.path.join(tmp, "preview" if preview else "public")
                _write(out, api_feed.repo_context(preview), preview)
                by = {s["id"]: s for s in json.load(open(os.path.join(out, "api/v1/sources.json"), encoding="utf-8"))["sources"]}
                tag = "preview" if preview else "public"
                want = build.BASE + png
                lg = by["e24"]["logo"] or {}
                if by["e24"]["logo_url"] != want or lg.get("kind") != "logo":
                    fails.append(f"{tag}: approved logo missing (e24)")
                if lg.get("file_url") != build.BASE + svg or lg.get("raster_url") != want:
                    fails.append(f"{tag}: logo.file_url should be the SVG and logo.raster_url the PNG (e24)")
                if by["svd"]["logo_url"] is not None or (by["svd"]["logo"] or {}).get("raster_url") is not None:
                    fails.append(f"{tag}: an SVG without a raster must not become logo_url (svd)")
                kp = (by["kaupr-no"]["logo"] or {})
                if by["kaupr-no"]["logo_url"] != build.BASE + "assets/img/logos/kaupr.webp" or kp.get("raster_url") != kp.get("file_url"):
                    fails.append(f"{tag}: a WebP logo is its own raster (kaupr-no)")
                for s in by.values():
                    if s["logo_url"] and not s["logo_url"].lower().endswith((".png", ".webp", ".jpg", ".jpeg")):
                        fails.append(f"{tag}: logo_url is not a raster: {s['id']}")
                if by["nrk-siste"]["logo_url"] != want:
                    fails.append(f"{tag}: outlet logo not used for nrk-siste")
                if by["dn"]["logo_url"] is not None:
                    fails.append(f"{tag}: rejected logo published (dn)")
                if (by["vg"]["logo_url"] is not None) != preview:
                    fails.append(f"{tag}: pending logo (vg) should be {'listed' if preview else 'null'}")
                if by["bing-no"]["logo_url"] is not None:
                    fails.append(f"{tag}: search feed got a logo")
                if not (os.path.exists(os.path.join(out, svg)) and os.path.exists(os.path.join(out, png))):
                    fails.append(f"{tag}: logo SVG and PNG not both copied into the site")
                news = json.load(open(os.path.join(out, "api/v1/news.json"), encoding="utf-8"))["items"]
                for n in news:
                    if n.get("source") in ("kaupr", "e24") and not n.get("source_logo_url"):
                        fails.append(f"{tag}: news {n['id']} ({n['source']}) has no source_logo_url")
                    if n.get("source") == "dn" and n.get("source_logo_url"):
                        fails.append(f"{tag}: news {n['id']} uses a rejected logo")
                    one = json.load(open(os.path.join(out, "api/v1/news", n["id"] + ".json"), encoding="utf-8"))["item"]
                    if one.get("source_logo_url") != n.get("source_logo_url"):
                        fails.append(f"{tag}: news/{n['id']}.json source_logo_url differs from the list")
        finally:
            api_feed.source_logos.MANIFEST = saved


def main():
    fails = []
    source_logos(fails)
    ctx = api_feed.repo_context(False)
    with tempfile.TemporaryDirectory() as tmp:
        ev = ctx["events"][0]
        ctx["markets"] = _markets_fixture()
        info = api_feed.write(
            tmp, preview=False, base=build.BASE,
            items=ctx["items"], events=ev, entities=ctx["ents"], relations=ctx["rels"],
            org_updated=ctx["org"].get("updated"), regulation=ctx["org"].get("regulation") or [],
            caveats=ctx["org"].get("caveats") or [], sources_cfg=ctx["cfg"],
            news_updated=ctx["news"].get("updated"),
            markets=ctx["markets"],
        )
        build.SITE = tmp
        build.PREVIEW = False
        build.emit_api(ctx)
        news = json.load(open(os.path.join(tmp, "api/v1/news.json"), encoding="utf-8"))
        if not news["items"]:
            fails.append("news list empty")
        ids = {i["id"] for i in news["items"]}
        if "e6727b4858b5" not in ids:
            fails.append("published story missing")
        if "fd3554c61e93" in ids:
            fails.append("rejected story leaked")
        for item in news["items"]:
            if not item.get("api_url", "").endswith(f"/news/{item['id']}.json"):
                fails.append("bad api_url " + item["id"])
            path = os.path.join(tmp, "api/v1/news", item["id"] + ".json")
            if not os.path.exists(path):
                fails.append("missing item file " + item["id"])
            if item.get("published") and "T" not in item["published"]:
                fails.append("published not ISO " + item["id"])
            if item.get("source") == "kaupr" and "news source" not in (item.get("source_note") or ""):
                fails.append("kaupr source note missing")
            if item.get("source") == "kaupr":
                logo = item.get("source_logo") or {}
                if not str(logo.get("file_url") or "").endswith("/assets/img/logos/kaupr.webp"):
                    fails.append("kaupr logo missing")
            if item.get("source") == "fi-se":
                logo = item.get("source_logo") or {}
                if not str(logo.get("file_url") or "").endswith("/assets/img/logos/se-fi.svg"):
                    fails.append("fi-se logo not aliased")
            if item.get("source") == "e24":
                shown = bool((item.get("source_logo") or {}).get("file_url"))
                e24 = json.load(open(os.path.join(ROOT, "assets/img/logos/logos.json"), encoding="utf-8")).get("e24") or {}
                public = (e24.get("review") or "ok") == "ok" and bool(e24.get("file"))
                if shown != public:
                    fails.append("e24 logo visibility")
            if item.get("source") == "nordic-crypto" and item.get("source_logo"):
                fails.append("invented Nordic Crypto logo")
            cov = item.get("coverage") or {}
            types = [r.get("type") for r in cov.get("by_source_type") or []]
            if types != ["national", "regional", "official", "international"]:
                fails.append("coverage types " + item["id"])
            if "also_covered_by" not in item or "sources" not in item or "primary_source" not in item:
                fails.append("coverage fields missing " + item["id"])
            if item.get("id") == "1a95167a3af8":
                extras = item.get("also_covered_by") or []
                if len(extras) != 1 or extras[0].get("outlet") != "nettavisen":
                    fails.append("nettavisen not on the aftenposten story")
                if "nettavisen.no" not in (extras[0].get("url") or ""):
                    fails.append("nettavisen url")
                if item.get("primary_source", {}).get("outlet") != "aftenposten":
                    fails.append("primary is not aftenposten")
                if cov.get("count") != 2 or not any(r.get("country") == "NO" and r.get("count") == 2 for r in cov.get("by_country") or []):
                    fails.append("coverage counts")
                if not str(item.get("html_url") or "").endswith("/stories/1a95167a3af8/"):
                    fails.append("story page url")
        letters = json.load(open(os.path.join(tmp, "api/v1/newsletters.json"), encoding="utf-8"))
        if not any(i["id"] == "001" for i in letters["issues"]):
            fails.append("newsletter 001 missing")
        issue = json.load(open(os.path.join(tmp, "api/v1/newsletters/001.json"), encoding="utf-8"))["item"]
        if "The Nordic Crypto team" not in (issue.get("text") or ""):
            fails.append("sign-off missing from issue text")
        if "jqrgen.github.io/nordic-crypto" in (issue.get("html") or "") or "jqrgen.github.io/nordic-crypto" in json.dumps(issue.get("html_urls") or {}):
            fails.append("newsletter still links to github.io")
        if not str(issue.get("html_url") or "").startswith(build.BASE):
            fails.append("newsletter html_url")
        if issue.get("sign_off") != "The Nordic Crypto team":
            fails.append("sign-off field")
        opening = (issue.get("text") or "")[:400].lower()
        if "made with" in opening or "artificial intelligence" in opening:
            fails.append("issue opening mentions the production method")
        if "LASK3077" in open(os.path.join(tmp, "api/v1/academia.json"), encoding="utf-8").read():
            fails.append("pending academia row published")
        if "TTM4195" not in open(os.path.join(tmp, "api/v1/academia.json"), encoding="utf-8").read():
            fails.append("approved course missing")
        spec = json.load(open(os.path.join(tmp, "api/v1/openapi.json"), encoding="utf-8"))
        for path in ("/api/v1/news.json", "/api/v1/news/{id}.json", "/api/v1/newsletters.json", "/api/v1/newsletters/{id}.json",
                     "/api/v1/markets.json", "/api/v1/markets/aggregated.json", "/api/v1/markets/{exchange}.json", "/api/v1/markets/by-asset/{symbol}.json",
                     "/api/v1/languages.json", "/api/v1/geo-language.json"):
            if path not in spec["paths"]:
                fails.append("openapi missing " + path)
        try:
            import yaml
            spec_y = yaml.safe_load(open(os.path.join(tmp, "api/v1/openapi.yaml"), encoding="utf-8"))
            if spec_y.get("openapi") != "3.0.3" or "/api/v1/news/{id}.json" not in spec_y.get("paths", {}):
                fails.append("openapi yaml contents")
        except Exception as ex:
            fails.append("openapi yaml: " + type(ex).__name__ + " " + str(ex).split("\n")[0])
        llms = open(os.path.join(tmp, "llms.txt"), encoding="utf-8").read()
        if "curl -fsS" not in llms or "newsletters" not in llms:
            fails.append("llms.txt")
        if "Access-Control-Allow-Origin" not in json.dumps(info.get("cors")):
            fails.append("cors")
        if "https://nordiccrypto.no/api/v1/news.json" not in json.dumps(info):
            fails.append("custom domain example")
        mk = json.load(open(os.path.join(tmp, "api/v1/markets.json"), encoding="utf-8"))
        if mk["tickers"][0]["last"] != "100.5" or mk["tickers"][0]["source_url"] != "https://api.firi.com/v2/markets/BTCNOK":
            fails.append("markets fixture")
        if "raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json" not in json.dumps(mk["urls"]):
            fails.append("markets raw url")
        if not any(ep["path"] == "/api/v1/markets.json" for ep in info["endpoints"]):
            fails.append("markets missing from discovery")
        if not any("markets.json" in (s.get("url") or "") for s in info.get("start_here") or []):
            fails.append("markets missing from start_here")
        if not any(ep["path"] == "/api/v1/markets/aggregated.json" for ep in info["endpoints"]):
            fails.append("aggregated missing from discovery")
        agg = json.load(open(os.path.join(tmp, "api/v1/markets/aggregated.json"), encoding="utf-8"))
        if agg.get("kind") != "markets-aggregated" or not agg.get("pairs"):
            fails.append("aggregated file")
        btc_pair = next(p for p in agg["pairs"] if p["symbol"] == "BTC-NOK")
        if btc_pair["price"] != "100.5" or btc_pair["currency"] != "NOK" or btc_pair["volume"]["volume_base"] != "1":
            fails.append("aggregated fixture math")
        if btc_pair.get("logo_path") != "api/v1/markets/logos/btc.svg":
            fails.append("aggregated logo")
        if not os.path.isfile(os.path.join(tmp, "api/v1/markets/logos/btc.svg")):
            fails.append("logo file not written")
        asset = json.load(open(os.path.join(tmp, "api/v1/markets/by-asset/BTC.json"), encoding="utf-8"))
        if not asset.get("aggregated") or asset.get("logo_url") is None:
            fails.append("by-asset logo")
        if "MarketAggregate" not in spec["components"]["schemas"]:
            fails.append("openapi aggregate schema")
        if meta_ios_later(tmp) != "https://testflight.apple.com/join/nQ2fpjZn":
            fails.append("testflight url missing from meta")
        meta = json.load(open(os.path.join(tmp, "api/v1/meta.json"), encoding="utf-8"))
        social = meta.get("social") or {}
        tg = social.get("telegram") or {}
        xacc = social.get("x") or {}
        if tg.get("url") != "https://t.me/nordiccryptochat" or tg.get("label") != "Telegram" or tg.get("name") != "Nordic Crypto on Telegram":
            fails.append("meta social telegram")
        if xacc.get("url") != "https://x.com/xcryptonordic" or xacc.get("label") != "X" or xacc.get("handle") != "@xcryptonordic":
            fails.append("meta social x")
        if (tg.get("name_i18n") or {}).get("nb") != "Nordic Crypto på Telegram":
            fails.append("meta social telegram nb")
        if (xacc.get("name_i18n") or {}).get("fi") != "Seuraa Nordic Cryptoa X:ssä":
            fails.append("meta social x fi")
        if "jqrgensn" in json.dumps(social) or "Follow me" in json.dumps(social):
            fails.append("personal profile leaked into social")
        urls = meta.get("urls") or {}
        if urls.get("telegram") != "https://t.me/nordiccryptochat" or urls.get("x") != "https://x.com/xcryptonordic":
            fails.append("meta urls social")
        if not str(urls.get("rss") or "").endswith("/rss.xml") or "substack" in urls:
            fails.append("meta urls rss, no substack signup")
        schema = (spec.get("components") or {}).get("schemas") or {}
        if "social" not in ((schema.get("SiteMeta") or {}).get("properties") or {}):
            fails.append("openapi social")
        build.LANG = "nb"
        nb_html = build.community_links() + build.community_section()
        if "https://t.me/nordiccryptochat" not in nb_html or "https://x.com/xcryptonordic" not in nb_html:
            fails.append("community links missing")
        if "Nordic Crypto på Telegram" not in nb_html or "Fellesskap" not in nb_html:
            fails.append("nb community copy")
        if "text-align:center" in nb_html or "jqrgensn" in nb_html or "Follow me" in nb_html:
            fails.append("community links centered or personal")
        build.LANG = "zh"
        if "Nordic Crypto on Telegram" not in build.community_links():
            fails.append("zh community did not fall back to English")
        build.LANG = "en"
        if "/ethics/" not in {p.get("path") for p in meta.get("site_pages") or []}:
            fails.append("ethics page missing from site meta")
        need = {"en", "nn", "nb", "sv", "da", "fi", "is", "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur", "id", "de", "ja", "sw", "mr"}
        langs_doc = json.load(open(os.path.join(tmp, "api/v1/languages.json"), encoding="utf-8"))
        got = {row.get("code") for row in langs_doc.get("languages") or []}
        if got != need:
            fails.append("languages.json codes " + ",".join(sorted(got)))
        for row in langs_doc.get("languages") or []:
            for key in ("code", "native_name", "english_name", "rtl", "html_lang", "home"):
                if key not in row:
                    fails.append("languages.json missing " + key + " on " + str(row.get("code")))
            if row.get("code") in ("ar", "ur") and row.get("rtl") is not True:
                fails.append("rtl missing for " + row["code"])
            if row.get("code") == "en" and row.get("rtl"):
                fails.append("english marked rtl")
            if row.get("code") == "en" and row.get("home") != build.BASE:
                fails.append("english home")
            if "jqrgen.github.io/nordic-crypto" in str(row.get("home") or ""):
                fails.append("home still on github.io")
            if row.get("code") == "zh" and not str(row.get("home") or "").endswith("/zh/"):
                fails.append("zh home")
        meta_codes = {row.get("code") for row in meta.get("languages") or []}
        if meta_codes != need:
            fails.append("meta languages")
        for row in meta.get("languages") or []:
            for key in ("native_name", "english_name", "rtl"):
                if key not in row:
                    fails.append("meta language missing " + key)
        geo = json.load(open(os.path.join(tmp, "api/v1/geo-language.json"), encoding="utf-8"))
        by = geo.get("by_country") or {}
        expect = {"NO": "nn", "SE": "sv", "DK": "da", "FI": "fi", "IS": "is", "AX": "sv", "FO": "da", "GL": "da",
                  "CN": "zh", "TW": "zh", "SG": "zh", "IN": "hi", "ES": "es", "MX": "es", "AR": "es", "FR": "fr",
                  "SA": "ar", "EG": "ar", "AE": "ar", "BD": "bn", "BR": "pt", "PT": "pt", "RU": "ru", "PK": "ur",
                  "ID": "id", "DE": "de", "AT": "de", "CH": "de", "JP": "ja", "KE": "sw", "TZ": "sw", "MR": "ar"}
        for c, l in expect.items():
            if by.get(c) != l:
                fails.append(f"geo {c} -> {by.get(c)} want {l}")
        if by.get("US") is not None:
            fails.append("US should stay unmapped")
        note = (geo.get("note") or "").lower()
        if "cookie" not in note or "guess" not in note or "cloudflare" not in note:
            fails.append("geo note")
        if "nc_lang" not in (geo.get("cookie") or ""):
            fails.append("geo cookie name")
        if not any(ep["path"] == "/api/v1/languages.json" for ep in info["endpoints"]):
            fails.append("languages missing from discovery")
        if not any(ep["path"] == "/api/v1/geo-language.json" for ep in info["endpoints"]):
            fails.append("geo-language missing from discovery")
        page = open(os.path.join(tmp, "api/index.html"), encoding="utf-8").read()
        if "Nordic Crypto data API" not in page or "curl -fsS" not in page or "<header" not in page:
            fails.append("human docs were not themed by the site builder")
        if "https://t.me/nordiccryptochat" not in page or "social.telegram" not in page or "https://x.com/xcryptonordic" not in page:
            fails.append("api docs missing brand accounts")
        catalog = json.load(open(os.path.join(tmp, ".well-known/api-catalog"), encoding="utf-8"))
        if "service-desc" not in catalog["linkset"][0]:
            fails.append("api catalog")
        upcoming = json.load(open(os.path.join(tmp, "api/v1/events/upcoming.json"), encoding="utf-8"))
        past = json.load(open(os.path.join(tmp, "api/v1/events/past.json"), encoding="utf-8"))
        if any(e["past"] for e in upcoming["events"]) or any(not e["past"] for e in past["events"]):
            fails.append("event split")
        for dp, _, fs in os.walk(tmp):
            for f in fs:
                if not f.endswith((".json", ".html", ".txt", ".yaml")):
                    continue
                raw = open(os.path.join(dp, f), encoding="utf-8").read()
                if f.endswith(".json"):
                    hits = []
                    walk(json.loads(raw), f, hits)
                    fails.extend(hits[:8])
                elif "/workspace/" in raw or "tips.db" in raw:
                    fails.append("local path in " + f)
        print(f"api files ok: {news['count']} news, {letters['count']} newsletters, {len(info['endpoints'])} endpoints")
    if fails:
        print("FAILED")
        for f in fails[:30]:
            print(" -", f)
        sys.exit(1)
    print("ok")

if __name__ == "__main__":
    main()
