#!/usr/bin/env python3
"""Builds the static site in site/ from data/news.json, data/events.json, data/orgchart.json and sources.json.
Also writes the public JSON API under site/api/v1/ (see tools/api_feed.py), /api/ docs, /llms.txt and OpenAPI.
  .venv/bin/python build.py            # public build: ONLY editor-approved content (what publish.sh would push)
  .venv/bin/python build.py --preview  # local review build: also shows pending items, clearly marked "Pending editor review"
All paths are relative, so the site works at the public origin (site_url.BASE) and on a local server.
Share buttons are plain links. No advertising trackers and no external fonts. Cloudflare Web Analytics
(aggregate visits, no cookies) is injected only when analytics.json or CF_WEB_ANALYTICS_TOKEN has a real token.
Languages (i18n/ALL_LANGS): English at the root, then one directory per code. Nordic nn, nb, sv, da, fi, is plus the wider UI set. Missing strings fall back to English.
Every page is built once per language; data/ (JSON), assets/ and screen/ (English) exist only at the root."""
import json, os, re, shutil, subprocess, html, sys, calendar, datetime as dt
from zoneinfo import ZoneInfo
import i18n
import site_url
import event_block
from tools.frontpage_blurbs import card_text, load as load_blurbs, opening_sentences, substantive
ROOT = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(ROOT, *a)
BASE = site_url.BASE
SITE = os.environ.get("NC_SITE_DIR") or P("site")   # NC_SITE_DIR: scratch build dir (tipworker/publish_tip_page.sh)
PREVIEW = "--preview" in sys.argv
SITE_NAME = "Nordic Crypto"
CUSTOM_DOMAIN = site_url.HOST   # GitHub Pages CNAME; publish.sh will not push gh-pages without it
def write_cname():
    """site/CNAME, so a publish keeps the custom domain (a missing file clears it on GitHub Pages)."""
    open(os.path.join(SITE, "CNAME"), "w", encoding="utf-8").write(CUSTOM_DOMAIN + "\n")
def load(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
def snippets(url, title):
    try: return json.loads(subprocess.check_output(["node", P("tools", "snippets.js"), url, title, LANG]))
    except Exception: return {"top": "", "bar": "", "css": "", "script": ""}
OSLO = ZoneInfo("Europe/Oslo")
LANG = "en"   # language being built (set by build() for each pass)
def t(key, **kw): return i18n.t(LANG, key, **kw)
def lp(lang=None): lang = lang or LANG; return "" if lang == "en" else lang + "/"
def up1(): return "../../" if LANG != "en" else "../"   # from a top-level page (e.g. calendar/) to the site root (data/, assets/)
def endate(iso):
    return i18n.short_date(LANG, dt.datetime.fromisoformat(iso).astimezone(OSLO))
COUNTRY_CODES = ["NO", "SE", "DK", "FI", "IS"]
class _C(dict):  # country names in the current language
    def __getitem__(self, c): return t("c_" + c)
    def items(self): return [(c, t("c_" + c)) for c in COUNTRY_CODES]
    def __iter__(self): return iter(COUNTRY_CODES)
    def __contains__(self, c): return c in COUNTRY_CODES
    def __len__(self): return len(COUNTRY_CODES)
COUNTRIES = _C()
EXTRA_C_CODES = ["NORDIC", "EU", "FO", "GL", "AX"]
# small inline SVG flags (Nordic crosses) – no emoji fonts or external images needed
_FL = {"NO": ("#BA0C2F", "#fff", "#00205B"), "SE": ("#006AA7", "#FECC00", None), "DK": ("#C8102E", "#fff", None), "FI": ("#fff", "#002F6C", None),
       "IS": ("#02529C", "#fff", "#DC1E35")}
def flag(c, big=False):
    if c not in _FL:
        return f'<span class="cc" title="{E(cname(c))}">{E("Nordic" if c == "NORDIC" else c)}</span>'
    bg, a, b = _FL[c]; w, h = (22, 16)
    inner = f'<rect x="7" width="2" height="16" fill="{b}"/><rect y="7" width="22" height="2" fill="{b}"/>' if b else ""
    border = ' stroke="#9ca3af" stroke-width=".6"' if bg == "#fff" else ""
    return (f'<svg class="flag" viewBox="0 0 22 16" width="{w*(1.4 if big else 1):.0f}" height="{h*(1.4 if big else 1):.0f}" role="img" aria-label="{E(cname(c))}">'
            f'<title>{E(cname(c))}</title><rect width="22" height="16" fill="{bg}"{border}/><rect x="6" width="4" height="16" fill="{a}"/><rect y="6" width="22" height="4" fill="{a}"/>{inner}</svg>')
def cname(c): return t("c_" + c) if c in COUNTRY_CODES or c in EXTRA_C_CODES else (c or "")
def flags_js(): return json.dumps({c: flag(c) for c in COUNTRY_CODES + EXTRA_C_CODES})

CSS = """
:root{--ink:#111;--muted:#4B5563;--line:#d1d5db;--paper:#fff;--accent:#0f5ea8;--warm:#b45309;--soft:#f5f7fa;--pub:#1d4ed8;--priv:#047857}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--paper)}
a{color:inherit}a:hover{text-decoration-thickness:2px}
.wrap{max-width:1140px;margin:0 auto;padding:0 16px}
header.top{border-bottom:3px solid var(--ink)}
header.top .wrap{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 22px;padding-top:14px;padding-bottom:10px}
.brand{font-weight:800;font-size:22px;letter-spacing:-.01em;text-decoration:none}.brand span{color:var(--accent)}
nav.main{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:15px}
nav.main a{text-decoration:none;padding:2px 0;border-bottom:2px solid transparent}nav.main a[aria-current]{border-color:var(--accent);font-weight:600}
.preview{background:#fef3c7;border-bottom:2px solid var(--warm);font-size:14px}.preview .wrap{padding-top:6px;padding-bottom:6px}
h1{font-size:28px;line-height:1.2;margin:22px 0 4px}h2{font-size:20px;margin:28px 0 8px}
.lead{color:var(--muted);margin:4px 0 10px;max-width:72ch}
.filters{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin:14px 0;padding:10px 12px;background:var(--soft);border:1px solid var(--line)}
.filters label,.filters .lbl{font-size:14px;color:var(--muted)}
select,input[type=search]{font:inherit;font-size:15px;padding:5px 8px;border:1px solid var(--ink);background:#fff;border-radius:0;max-width:100%}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font:inherit;font-size:13.5px;padding:3px 10px;border:1px solid var(--ink);background:#fff;cursor:pointer;display:inline-flex;align-items:center;gap:5px}
.chip[aria-pressed=true]{background:var(--ink);color:#fff}
.flag{vertical-align:-2px;flex:none;border-radius:1px}
.cc{display:inline-block;font-size:11px;font-weight:700;padding:0 4px;border:1px solid var(--line);color:var(--muted);vertical-align:1px}
ol.news{list-style:none;margin:0;padding:0;text-align:left}
ol.news li{display:flex;flex-direction:row;align-items:flex-start;gap:16px;padding:14px 0;border-bottom:1px solid var(--line);text-align:start}
ol.news .storybody{min-width:0;flex:1;text-align:start}
ol.news h3{font-size:18px;line-height:1.3;margin:0 0 4px}ol.news h3 a{text-decoration:none}ol.news h3 a:hover{text-decoration:underline}
.ill{margin:0 0 10px;text-align:start}
.ill img{display:block;width:100%;max-width:720px;height:auto;background:var(--soft)}
ol.news .ill{flex:0 0 220px;width:220px;margin:0}
ol.news .ill img{width:220px;height:124px;object-fit:cover;object-position:left center}
@media(max-width:640px){ol.news li{flex-direction:column}ol.news .ill{flex:none;width:100%;max-width:480px}ol.news .ill img{width:100%;height:auto;max-height:240px}}
.orig{font-size:13.5px;color:var(--muted);margin:0 0 3px}
.meta{font-size:13.5px;color:var(--muted)}.meta b{color:var(--ink);font-weight:600}
.src{display:inline-flex;align-items:center;justify-content:flex-start;gap:6px;vertical-align:middle;text-align:start}
.src-logo{height:18px;width:auto;max-width:96px;object-fit:contain;flex:none;background:#fff;padding:1px}
.covrow,.readat-row,.also,.covbars,.covsort,.covlist,.covgroup,.cov-by-country,.cov-by-time{text-align:start}
.covrow{display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-start;gap:6px 8px;margin:6px 0 0}
.cov-logo{display:inline-flex;align-items:center;justify-content:flex-start;gap:6px;text-decoration:none}
.cov-more{font-size:13px;color:var(--ink);border:1px solid var(--line);padding:1px 6px;background:#fff;text-decoration:none}
.cov-more:hover,.cov-more:focus-visible{border-color:var(--ink)}
.readat{display:inline-block;padding:8px 14px;background:var(--ink);color:#fff;text-decoration:none;font-weight:700}
.readat:hover,.readat:focus-visible{background:#000}
.also{margin:8px 0}
.covbars{margin:0 0 14px}
.covbar{display:grid;grid-template-columns:minmax(7rem,12rem) minmax(4rem,16rem) 2rem;justify-content:start;align-items:center;gap:8px;margin:3px 0;font-size:14px;max-width:100%}
@media(max-width:640px){.covbar{grid-template-columns:minmax(6rem,9rem) minmax(3rem,1fr) 2rem}}
.covbar .track{display:block;height:8px;background:var(--line)}
.covbar .fill{display:block;height:8px;background:var(--accent)}
.covbar .covn{font-variant-numeric:tabular-nums}
.covsort{margin:8px 0}
.covgroup{margin:0 0 12px}
.covgroup h3{display:flex;justify-content:flex-start;gap:8px;align-items:baseline;font-size:16px;margin:0 0 4px}
.covlist{list-style:none;padding:0;margin:0}
.covlist li{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:flex-start;gap:6px 12px;border-bottom:1px solid var(--line);padding:8px 0}
.covlist .cov-title{flex:1 1 16rem;min-width:12rem}
.cov-open{font-weight:600}
.tag{display:inline-block;font-size:12px;padding:0 6px;border:1px solid var(--line);margin-left:4px;color:var(--muted)}
.tag.pend{border-color:var(--warm);color:var(--warm);font-weight:600}.tag.paid{border-color:var(--warm);color:var(--warm)}
.sum{margin:6px 0 0;max-width:75ch;line-height:1.45;text-align:left}.sum.pend{color:var(--warm);font-style:italic}
.pw{font-size:12px;color:var(--warm)}
.calgrid{display:none}@media(min-width:760px){.calgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(460px,1fr));gap:20px;margin:16px 0}}
table.cal{border-collapse:collapse;width:100%;table-layout:fixed;font-size:13px}table.cal caption{text-align:left;font-weight:600;padding:4px 0}
table.cal th{font-weight:500;color:var(--muted);padding:2px}table.cal td{border:1px solid var(--line);vertical-align:top;height:64px;padding:2px 4px;overflow:hidden}
table.cal td.out{opacity:.35}table.cal td.today .d{background:var(--accent);color:#fff;padding:0 4px}table.cal td.has{background:color-mix(in srgb,var(--accent) 7%,transparent)}
table.cal td a{display:flex;gap:3px;align-items:flex-start;font-size:11.5px;line-height:1.2;margin-top:3px;text-decoration:none}table.cal td a span{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:break-word;hyphens:auto}table.cal td a:hover{text-decoration:underline}
table.cal td a .flag{width:13px;height:10px;margin-top:1px}ol.past{opacity:.7}
.empty{padding:20px;color:var(--muted)}
footer{margin-top:40px;border-top:1px solid var(--line);padding:18px 0 30px;font-size:13.5px;color:var(--muted)}
.notice{border-left:4px solid var(--accent);background:var(--soft);padding:8px 12px;font-size:14px;margin:12px 0}
.notice.warn{border-color:var(--warm);background:#fffbeb}
/* org chart */
.seg{display:inline-flex;border:1px solid var(--ink)}.seg button{font:inherit;font-size:14px;padding:5px 12px;border:0;background:#fff;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--ink);color:#fff}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:12px}
.cols.only-private,.cols.only-public{grid-template-columns:1fr}
.cols.only-private .col-public,.cols.only-public .col-private{display:none}
@media (max-width:760px){.cols{grid-template-columns:1fr}}
.col>h2{margin:0 0 8px;padding:6px 10px;color:#fff;font-size:17px}
.col-private>h2{background:var(--priv)}.col-public>h2{background:var(--pub)}
.cgrp{margin:0 0 6px}.cgrp>h3{display:flex;align-items:center;gap:8px;font-size:16px;margin:16px 0 4px;padding-bottom:3px;border-bottom:2px solid var(--line)}
.grp{margin:0 0 10px}.grp h4{font-size:12.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:8px 0 6px}
.card{border:1px solid var(--line);background:#fff;padding:8px 10px;margin:0 0 8px;cursor:pointer;text-align:left;width:100%;font:inherit;display:block}
.card:hover,.card:focus-visible{border-color:var(--ink);outline:none}
.card.hl{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent)}.card.dim{opacity:.35}
.card .nm{font-weight:700}.card .ds{font-size:13.5px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.people{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.person{display:flex;align-items:center;gap:6px;font-size:13px;border:1px solid var(--line);padding:3px 8px 3px 3px;background:var(--soft);cursor:pointer;font-family:inherit;max-width:100%}
.person.hl{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent)}
.av{width:34px;height:34px;border-radius:50%;object-fit:cover;flex:none;display:inline-flex;align-items:center;justify-content:center;background:#e5e7eb;color:#374151;font-weight:700;font-size:13px}
.av.big{width:96px;height:96px;font-size:28px}
.xl{font-size:11.5px;padding:0 5px;margin-left:4px;border:1px solid}.xl.pub{color:var(--pub)}.xl.priv{color:var(--priv)}
#detail{position:sticky;bottom:0;background:#fff;border:2px solid var(--ink);padding:12px 14px;margin-top:14px;max-height:60vh;overflow:auto}
#detail[hidden]{display:none}#detail h3{margin:0 0 4px;font-size:19px}#detail .close{float:right;font:inherit;border:1px solid var(--ink);background:#fff;cursor:pointer}
#detail ul{padding-left:18px;margin:6px 0}#detail .row{display:flex;gap:14px;align-items:flex-start}
.credit{font-size:12px;color:var(--muted);text-align:start;margin:4px 0 0}
.tablewrap{overflow-x:auto}
table.list{width:100%;border-collapse:collapse;font-size:14.5px}table.list th,table.list td{border-bottom:1px solid var(--line);padding:6px 6px;text-align:left;vertical-align:top}
table.list th{font-size:13px;color:var(--muted)}
.ok{color:#047857;font-weight:600}.bad{color:#b91c1c;font-weight:600}
.prose{max-width:72ch}
.tag.act{border-color:#047857;color:#047857;font-weight:600}.tag.inact{border-color:#9ca3af;color:#6b7280}
.reg{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin:10px 0}
.reg article{border:1px solid var(--line);padding:10px 12px;background:#fff}.reg h3{display:flex;gap:8px;align-items:center;margin:0 0 6px;font-size:17px}
.reg dl{margin:0;font-size:14px}.reg dt{font-weight:600;margin-top:6px}.reg dd{margin:0}
"""
CSS += """
.langsw{position:relative;margin-left:auto;font-size:14px;display:flex;gap:10px;align-items:baseline}
.langsw details{position:relative}.langsw summary{cursor:pointer;list-style:none;border:1px solid var(--ink);padding:2px 8px}
.langsw summary::-webkit-details-marker{display:none}
.langsw ul{position:absolute;right:0;z-index:20;margin:4px 0 0;padding:4px 0;list-style:none;background:#fff;border:1px solid var(--ink);min-width:12.5rem;max-height:70vh;overflow:auto}
html[dir=rtl] .langsw ul{right:auto;left:0}
.langsw li a{display:block;padding:4px 12px;text-decoration:none;text-align:left}.langsw li a:hover,.langsw li a:focus{background:var(--soft)}
.langsw li a[aria-current]{font-weight:700}.langsw .quick{font-size:13.5px}
.navtoggle{display:none}
.langpick,.langglobe{display:none}
.vh{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
/* Phones: iOS Safari paints an empty bordered box for an absolutely positioned list inside <details>.
   A native <select> is the control there. The list below is only the no-JS fallback, in normal flow. */
@media(max-width:960px),(hover:none) and (pointer:coarse){
 .langsw{margin-left:0;width:auto;max-width:100%;justify-content:flex-start;align-items:center;flex-wrap:wrap;text-align:left}
 .langsw ul{position:static;right:auto;left:auto;width:100%;min-width:0;max-height:60vh;overflow:auto}
 .langsw li a{padding:10px 12px}
}
@media(max-width:960px){
 .js .brandrow{width:100%}
 .js header.top .wrap{align-items:flex-start;justify-content:flex-start}
 .js header.top .wrap{gap:8px 10px}
 .js .navtoggle{display:inline-flex;align-items:center;justify-content:center;order:2;flex:none;width:44px;height:44px;padding:0;border:1px solid var(--ink);background:#fff;color:inherit;cursor:pointer;border-radius:0}
 .js .navtoggle .navbars{display:inline-flex;flex-direction:column;justify-content:center;gap:4px;width:18px}
 .js .navtoggle .navbars span{display:block;height:2px;background:currentColor}
 .js .navtoggle:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
 .js nav.main{display:none;order:4;flex:1 0 100%;flex-direction:column;align-items:stretch;gap:0;margin:0;text-align:left}
 .js nav.main.is-open{display:flex}
 .js nav.main a{display:block;width:100%;text-align:left;padding:11px 2px;border-bottom:1px solid var(--line)}
 .js .langsw{order:3;flex:1 1 auto;min-width:0;flex-wrap:nowrap}
}
@media(max-width:960px),(hover:none) and (pointer:coarse){
 .js .langsw details{display:none}
 .js .langglobe{display:inline;font-size:16px;line-height:1}
 .js .langpick{display:inline-flex;align-items:center;justify-content:flex-start;min-width:0;max-width:100%;text-align:left}
 .js .langpick select{font-size:16px;line-height:1.3;min-height:44px;width:10.5rem;max-width:100%;text-align:left;text-align-last:left;padding:8px 28px 8px 10px}
 .js .langpick select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
 .js .langsw .quick{font-size:16px;padding:10px 0;text-align:left}
}
@media(max-width:640px){.langsw{margin-left:0}}
html.nc-pick body{visibility:hidden}
.logo{width:28px;height:28px;object-fit:contain;flex:none;background:#fff}
.logo.big{width:64px;height:64px}
.card .nm{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.av.org{border-radius:4px;width:28px;height:28px;font-size:11px}
.imap-cats{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin:12px 0}
.imap-cat{border:1px solid var(--line);padding:8px 10px 10px;background:#fff}
.imap-cat>h3{font-size:15px;margin:0 0 8px;padding-bottom:4px;border-bottom:2px solid var(--accent);display:flex;justify-content:space-between;gap:8px}
.imap-cat.pub>h3{border-color:var(--pub)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:6px}
.tile{display:flex;flex-direction:column;align-items:center;gap:4px;padding:6px 4px;border:1px solid var(--line);text-decoration:none;font-size:11.5px;line-height:1.2;text-align:center;min-height:86px;background:#fff;overflow-wrap:anywhere}
.tile:hover,.tile:focus-visible{border-color:var(--ink);outline:none}
.tile .logo,.tile .av{width:40px;height:40px}.tile .fl{display:flex;gap:3px;align-items:center;color:var(--muted);font-size:10.5px}
.imap[data-view=country] .imap-bycat,.imap[data-view=cat] .imap-bycountry{display:none}
.rules-c .seg{margin:8px 0}
.nlform{margin:12px 0}.nlform input[type=email]{padding:6px;width:100%;max-width:320px}.nlform button{padding:7px 14px;font-size:15px}.nlform .hp{position:absolute;left:-9999px}
.nlmsg{display:block;margin-top:6px}.nlmsg.ok{color:#14532d}.nlmsg.warn{color:#9a3412}.nlfoot{margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid var(--line)}.nlfoot .nlform{display:inline}.nlc label{position:absolute;left:-9999px}
.ssembed{margin:14px 0}.ssload{font:inherit;font-weight:600;border:0;cursor:pointer}.ssembed iframe{display:block;width:480px;max-width:100%;height:320px}.ssembed .meta{margin-top:6px}.nlhome{margin:28px 0 8px;padding-top:12px;border-top:1px solid var(--line)}
.nlsub{display:inline-block;padding:6px 14px;border-radius:6px;background:#0f5ea8;color:#fff!important;text-decoration:none;font-weight:600}.nlsub:hover,.nlsub:focus{background:#0b4a85}
.brandrow{display:flex;align-items:center;gap:10px 14px;flex-wrap:wrap}
.hdrsub{display:inline-block;padding:5px 12px;border-radius:6px;background:#0f5ea8;color:#fff!important;text-decoration:none;font-weight:600;font-size:14px;line-height:1.3;white-space:nowrap}.hdrsub:hover,.hdrsub:focus{background:#0b4a85}
.hdrbtns{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-width:0}
.hdrx{display:inline-block;padding:4px 10px;border:1px solid var(--ink);border-radius:6px;color:var(--ink)!important;background:#fff;text-decoration:none;font-weight:600;font-size:13px;line-height:1.3;white-space:nowrap}.hdrx:hover,.hdrx:focus{background:#f1f1f1}.hdrx .xs{display:none}
.xfollow,.tgfollow{display:inline-block;padding:5px 12px;border:1px solid var(--ink);border-radius:6px;color:var(--ink)!important;text-decoration:none;font-weight:600;text-align:start}.xfollow:hover,.xfollow:focus,.tgfollow:hover,.tgfollow:focus{background:#f1f1f1}
nav.community{display:flex;flex-wrap:wrap;justify-content:flex-start;align-items:center;gap:8px 10px;margin:8px 0 12px;text-align:start;width:fit-content;max-width:100%}
footer,footer .wrap,.nlfoot,.nlhome{text-align:start}
@media(max-width:640px){.brandrow{width:100%;justify-content:space-between;flex-wrap:nowrap}.brandrow .brand{white-space:nowrap;flex:none}.hdrsub{font-size:13px;padding:5px 10px;white-space:normal;text-align:center;min-width:0}.hdrbtns{flex-wrap:nowrap;justify-content:flex-end}.hdrx{flex:none}}
@media(max-width:480px){.hdrx{padding:4px 9px}.hdrx .xf{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}.hdrx .xs{display:inline}}
.nlissues{list-style:none;margin:8px 0 18px;padding:0}.nlissues li{display:flex;gap:14px;align-items:flex-start;padding:14px 0;border-bottom:1px solid var(--line)}
.nlissues .th{flex:none;width:200px;max-width:40%}.nlissues img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;border:1px solid var(--line)}
.nlissues h3{font-size:18px;line-height:1.3;margin:0 0 4px}.nlissues h3 a{text-decoration:none}.nlissues h3 a:hover{text-decoration:underline}.nlissues .sum{margin-top:4px}
.issue h1{overflow-wrap:break-word}
.nlvideo{margin:16px 0 20px;max-width:960px}.nlvideo video{display:block;width:100%;height:auto;aspect-ratio:16/9;background:#000}.nlvideo figcaption{margin-top:6px}
.issuetext{overflow-wrap:break-word}.issuetext h2{font-size:19px}.issuetext ul{padding-left:20px}.issuetext li{margin:4px 0}.issuetext hr{border:0;border-top:1px solid var(--line);margin:22px 0}
.bridge{margin:6px 0 0;font-weight:600;text-align:left}
@media(max-width:520px){.nlissues li{flex-direction:column;gap:8px}.nlissues .th{width:100%;max-width:100%}h1{font-size:24px}}
"""
CSS += """
.appbar{margin:10px 0 14px;text-align:left}
a.applink{display:inline-block;padding:8px 14px;border:2px solid var(--ink);font-weight:700;font-size:18px;line-height:1.3;text-decoration:none;text-align:left}
a.applink:hover,a.applink:focus-visible{background:var(--soft)}
.markets h1{font-size:32px}
.markets .lead,.markets p,.markets h2,.markets h3,.mkcard,.mkagg,.mkasset{text-align:left}
.mkcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin:0 0 8px}
.mkcard{border:1px solid var(--line);padding:12px 14px;background:#fff;text-align:left}
.mkcard .px{font-size:28px;font-weight:700;line-height:1.15;margin:6px 0;font-variant-numeric:tabular-nums;text-align:left}
.mkcard .unit{font-size:16px;font-weight:600;color:var(--muted)}
.mkcard .ba{display:flex;flex-wrap:wrap;justify-content:flex-start;gap:6px 18px;font-size:18px;margin:0}
.mkasset>h2{display:flex;align-items:center;justify-content:flex-start;gap:10px;font-size:26px;margin:22px 0 4px;text-align:left}
.mkasset>h2 img{width:28px;height:28px;flex:none;display:block}
.mkagg{border-left:4px solid var(--ink);padding:8px 12px;margin:8px 0 10px;background:var(--soft);text-align:left}
.mkagg .px{font-size:22px;font-weight:700;margin:2px 0 4px;text-align:left;font-variant-numeric:tabular-nums}
.mkq{font-size:16px;color:var(--muted);margin:12px 0 6px;font-weight:600;text-align:left}
@media(min-width:1100px){.markets h1{font-size:40px}.mkcard .px{font-size:34px}.mkcard .ba{font-size:20px}.mkagg .px{font-size:26px}}
.pushopt{text-align:start;margin:0 0 16px;padding:0 0 14px;border-bottom:1px solid var(--line);max-width:72ch}
.pushopt h2{font-size:16px;margin:0 0 6px;text-align:start}
.pushopt p,.pushopt label{text-align:start}
.pushopt .push-topics{display:flex;flex-wrap:wrap;justify-content:flex-start;gap:6px 16px;margin:8px 0}
.pushopt .push-c{display:inline-flex;align-items:center;justify-content:flex-start;gap:6px;font-size:14.5px;text-align:start}
.pushopt button.push-btn{font:inherit;font-weight:600;padding:7px 12px;border:1px solid var(--ink);background:#fff;cursor:pointer;text-align:start}
.pushopt button.push-btn:hover,.pushopt button.push-btn:focus-visible{background:var(--soft)}
.pushopt .push-status{min-height:1.3em;margin:8px 0;text-align:start}
"""
CSS += """
nav.main a.nav-quiet{font-size:14px}
.talks,.talks h1,.talks h2,.talks p,.talks article,.talks label,.talks select,.talks .filters{text-align:start}
.talks article{padding:16px 0;border-bottom:1px solid var(--line);max-width:74ch}
.talks h2{font-size:20px;margin:0 0 4px}
.talks .talk-play{display:inline-block;margin:8px 0;padding:8px 14px;font:inherit;font-weight:600;text-align:start;border:1px solid var(--ink);background:#fff;cursor:pointer}
.talks .talk-play:hover,.talks .talk-play:focus-visible{background:var(--soft)}
.talks iframe{display:block;width:100%;max-width:720px;aspect-ratio:16/9;height:auto;border:0;background:#111;margin:8px 0}
.talks .filters{display:flex;flex-wrap:wrap;justify-content:flex-start;align-items:center;gap:8px 16px}
.talks .filters select{font:inherit;text-align:start;max-width:100%}
"""

NAV = [("", "nav_news"), ("markets", "nav_markets"), ("calendar", "nav_calendar"), ("talks", "nav_talks"), ("org-chart", "nav_org"), ("academia", "nav_academia"), ("sources", "nav_sources"), ("newsletter", "nav_newsletter"), ("about", "nav_about"), ("tip", "nav_tip")]
COOKIE_PATH = site_url.PATH   # "/" on the public domain; a path prefix if BASE ever has one
def geo_endpoint():
    """Country lookup: GET <tipworker>/api/geo (Cloudflare request.cf.country). Only when the Worker is deployed,
    i.e. tipserver/config.json -> public_endpoint is a workers.dev URL (or env GEO_ENDPOINT)."""
    e = os.environ.get("GEO_ENDPOINT")
    if e is not None: return e.strip().rstrip("/") or None
    ep = tip_endpoint()
    return ep if ep and ".workers.dev" in ep else None
# ---- Newsletter signup (newsletter/config.json; OFF until the Worker is deployed and jQrgen approves) ----
NL_CFG = load(P("newsletter", "config.json"), {}) or {}
def newsletter_endpoint():
    """Worker base URL for POST /api/subscribe, or None = no signup form anywhere on the site.
    On only when newsletter/config.json enabled is true (or env NC_NEWSLETTER=1 for test builds) AND an endpoint is known:
    env NEWSLETTER_ENDPOINT, config endpoint, or the deployed workers.dev tip Worker."""
    if not (NL_CFG.get("enabled") is True or os.environ.get("NC_NEWSLETTER") == "1"): return None
    e = os.environ.get("NEWSLETTER_ENDPOINT") or NL_CFG.get("endpoint") or geo_endpoint()
    return (e or "").strip().rstrip("/") or None
NL_N = [0]
def newsletter_form(compact=False):
    """Signup form (posts to the Worker; works without JavaScript via a 303 back to /newsletter/). Honeypot 'website'.
    The Worker still accepts the original seven site languages, so a newer UI language posts English."""
    ep = newsletter_endpoint()
    if not ep: return ""
    NL_N[0] += 1; i = NL_N[0]
    return (f'<form class="nlform{" nlc" if compact else ""}" method="post" action="{E(ep)}/api/subscribe" data-ep="{E(ep)}">'
            f'<input type="hidden" name="site" value="nordic-crypto"><input type="hidden" name="lang" value="{LANG if LANG in ("en", "nn", "nb", "sv", "da", "fi", "is") else "en"}">'
            f'<label for="nl-email-{i}">{E(t("nl_email"))}</label> <input id="nl-email-{i}" name="email" type="email" required maxlength="254" autocomplete="email" inputmode="email">'
            f'<span class="hp" aria-hidden="true"><label for="nl-w-{i}">website</label><input id="nl-w-{i}" name="website" tabindex="-1" autocomplete="off"></span>'
            f' <button type="submit">{E(t("nl_btn"))}</button><span class="nlmsg" role="status" aria-live="polite"></span></form>')
def newsletter_script():
    if not newsletter_endpoint(): return ""
    m = {k: t("nl_" + k) for k in ("sending", "sent", "confirmed", "unsub", "e_email", "e_rate", "e_link", "e_fail")}
    return """<script>(function(){var M=%s,F=[].slice.call(document.querySelectorAll('form.nlform'));if(!F.length)return;
function say(f,k){var s=f.querySelector('.nlmsg');s.textContent=M[k]||M.e_fail;s.className='nlmsg '+(k.indexOf('e_')===0?'warn':'ok')}
var E={email:'e_email',rate:'e_rate',invalid_link:'e_link'},q=new URLSearchParams(location.search),f0=document.querySelector('main form.nlform')||F[0];
if(q.get('sent'))say(f0,'sent');else if(q.get('confirmed'))say(f0,'confirmed');else if(q.get('unsubscribed'))say(f0,'unsub');else if(q.get('error'))say(f0,E[q.get('error')]||'e_fail');
F.forEach(function(f){f.addEventListener('submit',function(ev){ev.preventDefault();var b=f.querySelector('button'),d={};new FormData(f).forEach(function(v,k){d[k]=v});
b.disabled=true;say(f,'sending');fetch(f.getAttribute('data-ep')+'/api/subscribe',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(d)})
.then(function(r){return r.json().then(function(j){b.disabled=false;if(r.ok){say(f,'sent');f.reset()}else say(f,E[j.error]||'e_fail')})}).catch(function(){b.disabled=false;say(f,'e_fail')})})})})();</script>""" % json.dumps(m, ensure_ascii=False)
def substack_subscribe_url():
    """Substack signup page (newsletter/config.json substack_url + /subscribe), or None. Independent of the own form:
    the Substack link is shown even while enabled is false (Substack handles signup and privacy itself)."""
    u = (NL_CFG.get("substack_url") or "").strip().rstrip("/")
    if not u.startswith("https://"): return None
    return u if u.endswith("/subscribe") else u + "/subscribe"
def newsletter_on(): return bool(newsletter_endpoint() or substack_subscribe_url())
def substack_button():
    sub = substack_subscribe_url()
    return f'<a class="nlsub" href="{E(sub)}" rel="noopener">{E(t("nl_sub_btn"))}</a>' if sub else ""
def substack_embed():
    """Substack's embeddable signup form (<substack_url>/embed), responsive (max-width:100%). newsletter/config.json substack_embed:
    "click" (default) = the iframe loads only after the reader clicks, so no third-party content or cookies load with the page
    (the About page promises no third-party scripts); "auto" = loads with the page (switch only after the privacy texts are updated);
    "off" = not shown."""
    u = (NL_CFG.get("substack_url") or "").strip().rstrip("/"); mode = NL_CFG.get("substack_embed", "click")
    if not u.startswith("https://") or mode == "off": return ""
    src = u + "/embed"; tt = E(t("nl_embed_title"))
    if mode == "auto":
        return f'<div class="ssembed"><iframe src="{E(src)}" title="{tt}" width="480" height="320" style="border:1px solid #EEE;background:white" frameborder="0" scrolling="no" loading="lazy"></iframe></div>'
    return (f'<div class="ssembed" data-src="{E(src)}" data-title="{tt}"><button type="button" class="nlsub ssload">{E(t("nl_embed_btn"))}</button>'
            f'<p class="meta">{E(t("nl_embed_note"))}</p></div>'
            "<script>(function(){document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('.ssload');if(!b)return;"
            "var w=b.closest('.ssembed'),f=document.createElement('iframe');f.src=w.getAttribute('data-src');f.title=w.getAttribute('data-title');"
            "f.width='480';f.height='320';f.setAttribute('frameborder','0');f.setAttribute('scrolling','no');f.style.border='1px solid #EEE';f.style.background='white';"
            "w.innerHTML='';w.appendChild(f)})})();</script>")
def header_sub_button():
    """'Subscribe on Substack' button at the top of every page (same Substack link as the footer, label without the arrow)."""
    sub = substack_subscribe_url()
    return f'<a class="hdrsub" href="{E(sub)}" rel="noopener">{E(t("nl_sub_btn").replace("→", "").strip())}</a>' if sub else ""
# Nordic Crypto brand accounts (not jQrgen's personal profiles). Plain links only: no widgets, scripts or embeds.
SITE_X = "https://x.com/xcryptonordic"
SITE_TELEGRAM = "https://t.me/nordiccryptochat"
def header_x_button():
    """Small 'Follow on X' link next to the header Substack button; on narrow phones it shrinks to an 'X' pill (full label kept for screen readers)."""
    return (f'<a class="hdrx" href="{SITE_X}" rel="noopener" title="{E(t("x_title"))}">'
            f'<span class="xf">{E(t("x_btn"))}</span><span class="xs" aria-hidden="true">X</span></a>')
def x_link():
    """'Follow Nordic Crypto on X' link. The brand account @xcryptonordic."""
    return f'<a class="xfollow" href="{SITE_X}" rel="noopener noreferrer" title="{E(t("x_title"))}">{E(t("x_follow"))}</a>'
def telegram_link():
    """'Nordic Crypto on Telegram' link. The brand chat, t.me/nordiccryptochat."""
    return f'<a class="tgfollow" href="{SITE_TELEGRAM}" rel="noopener noreferrer" title="{E(t("tg_title"))}">{E(t("tg_follow"))}</a>'
def community_links():
    """Left-aligned brand links for the footer, About and the newsletter. The source-code link stays separate."""
    return f'<nav class="community" aria-label="{E(t("social_aria"))}">{telegram_link()}{x_link()}</nav>'
def community_section():
    """About-page block. Strings come from i18n and fall back to English."""
    return f'<h2 id="community">{E(t("social_h"))}</h2><p>{E(t("social_lead"))}</p>{community_links()}'
# ---- Newsletter issues (newsletter/published/issues.json; text, poster, subtitles and video per issue) ----
# The subtitle track is not "default": issue videos have the English subtitles burned in, the track is for assistive tech and players.
NL_PUB = P("newsletter", "published")
def nl_issues():
    """Published issues, newest first."""
    d = load(os.path.join(NL_PUB, "issues.json"), {}) or {}
    return sorted(d.get("issues", []), key=lambda i: (i.get("date") or "", i.get("number") or 0), reverse=True)
NL_VIDEO_OK = {}
def nl_video_file(iss):
    """Local path of the issue video (newsletter/published/<id>/video.mp4, not in git). When missing, downloads the
    public release copy (video.url) and checks sha256. None when unavailable (the page then shows only the download link)."""
    v = iss.get("video") or {}; iid = iss["id"]
    if iid in NL_VIDEO_OK: return NL_VIDEO_OK[iid]
    f = os.path.join(NL_PUB, iid, v.get("file") or "video.mp4"); ok = None
    import hashlib
    def good(path):
        if not os.path.exists(path): return False
        if v.get("bytes") and os.path.getsize(path) != v["bytes"]: return False
        if not v.get("sha256"): return True
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""): h.update(b)
        return h.hexdigest() == v["sha256"]
    if good(f): ok = f
    elif v.get("url"):
        try:
            import urllib.request
            print(f"newsletter: downloading the video for issue {iid} from {v['url']}")
            tmp = f + ".part"; urllib.request.urlretrieve(v["url"], tmp)
            if good(tmp): os.replace(tmp, f); ok = f
            else: os.remove(tmp); print(f"newsletter: WARNING, downloaded video for {iid} failed the size/sha256 check")
        except Exception as ex: print(f"newsletter: WARNING, no video for issue {iid}: {ex}")
    else: print(f"newsletter: WARNING, no video file for issue {iid}")
    NL_VIDEO_OK[iid] = ok; return ok
def nl_copy_assets(iss):
    """Copies poster, subtitles and video ONCE into site/newsletter/<id>/ (all languages link to that copy)."""
    v = iss.get("video") or {}; d = os.path.join(SITE, "newsletter", iss["id"]); os.makedirs(d, exist_ok=True)
    for k in ("poster", "subs"):
        if v.get(k) and os.path.exists(os.path.join(NL_PUB, iss["id"], v[k])): shutil.copy(os.path.join(NL_PUB, iss["id"], v[k]), os.path.join(d, v[k]))
    vf = nl_video_file(iss) if v else None
    if vf: shutil.copy(vf, os.path.join(d, v.get("file") or "video.mp4"))
def nl_i18n(iss, key):
    """English lives on the issue; other languages in <key>_i18n (same shape as summary_i18n). Returns (text, lang)."""
    if LANG != "en":
        v = (iss.get(key + "_i18n") or {}).get(LANG)
        if v: return v, LANG
    return iss.get(key) or "", iss.get("lang", "en")
def nl_issue_html(iss):
    """issue.<lang>.html when that translation exists, otherwise the English issue.html. Returns (html, lang)."""
    iid = iss["id"]
    if LANG != "en":
        p = os.path.join(NL_PUB, iid, f"issue.{LANG}.html")
        if os.path.exists(p): return open(p, encoding="utf-8").read(), LANG
    return open(os.path.join(NL_PUB, iid, "issue.html"), encoding="utf-8").read(), iss.get("lang", "en")
def nl_meta(iss, with_video=True, text_lang=None):
    v = iss.get("video") or {}
    parts = [E(t("nl_issue_n", n=iss.get("number"))), f'<time datetime="{E(iss["date"])}">{E(i18n.short_date(LANG, dt.date.fromisoformat(iss["date"])))}</time>']
    if with_video and v.get("duration"): parts.append(E(t("nl_issue_video", m=max(1, round(v["duration"] / 60)))))
    if text_lang and text_lang != LANG and i18n.has("en", "lang_English"): parts.append(E(t("lang_English") if text_lang == "en" else text_lang))
    return " · ".join(parts)
def nl_body_bridge(iss, text_lang):
    """When the issue HTML is not in the page language, explain the issue in the page language."""
    if not text_lang or text_lang == LANG:
        return ""
    phrase = t("lang_English") if text_lang == "en" and i18n.has("en", "lang_English") else text_lang
    what, wl = nl_i18n(iss, "subtitle")
    if not (what or "").strip():
        return f'<p class="notice">{E(t("nl_issue_en"))}</p>'
    return f'<p class="notice">{E(t("nl_bridge", where=phrase))} <span{lang_attr(wl)}>{E(what)}</span></p>'
def build_issue(iss):
    """/newsletter/<id>/: the issue text in the reader's language when issue.<lang>.html exists (otherwise English,
    with a short note). The video is one shared English file (HTML5 <video>, poster, English subtitles; no third-party player)."""
    iid = iss["id"]; v = iss.get("video") or {}; slug = f"newsletter/{iid}"
    depth = 2 + (0 if LANG == "en" else 1); root = "../" * depth; a = f"{root}newsletter/{iid}/"
    title, tl = nl_i18n(iss, "title"); subtitle, sl = nl_i18n(iss, "subtitle")
    txt, hl = nl_issue_html(iss); txt = site_url.expand(txt).replace(BASE, root + lp())  # site links stay in the reader's language
    tla, sla, hla = lang_attr(tl), lang_attr(sl), lang_attr(hl)
    per = iss.get("period") or []
    per_s = (" · " + E(t("nl_issue_period", a=i18n.short_dm(LANG, dt.date.fromisoformat(per[0])), b=i18n.short_date(LANG, dt.date.fromisoformat(per[1]))))) if len(per) == 2 else ""
    cnt = (" · " + E(t("nl_issue_count", s=iss["stories"], e=iss["events"]))) if iss.get("stories") else ""
    vid = ""
    if v:
        mb = f'{v.get("bytes", 0) / 1e6:.1f}'; mb = mb if LANG == "en" else mb.replace(".", ",")
        dl = f'<a href="{E(v["url"])}" rel="noopener" download>{E(t("nl_video_dl", mb=mb))}</a>' if v.get("url") else ""
        subs = f' · <a href="{a}{E(v["subs"])}" download>{E(t("nl_video_subs"))}</a>' if v.get("subs") else ""
        if nl_video_file(iss):
            poster = f' poster="{a}{E(v["poster"])}"' if v.get("poster") else ""
            track = f'<track kind="subtitles" srclang="en" label="{E(t("lname_English"))}" src="{a}{E(v["subs"])}">' if v.get("subs") else ""
            vid = (f'<figure class="nlvideo"><video controls preload="metadata" playsinline{poster} width="{v.get("width", 1920)}" height="{v.get("height", 1080)}">'
                   f'<source src="{a}{E(v.get("file") or "video.mp4")}" type="video/mp4">{track}<p>{E(t("nl_video_fallback"))} {dl}</p></video>'
                   f'<figcaption class="meta">{E(t("nl_video_note"))}<br>{dl}{subs}</figcaption></figure>')
        elif dl: vid = f'<p class="notice">{dl}</p>'
    sub = substack_button()
    body = f"""<article class="issue">
<p class="meta"><a href="../">← {E(t("nl_all_issues"))}</a></p>
<h1{tla}>{E(title)}</h1>
<p class="lead"{sla}>{E(subtitle)}</p>
<p class="meta">{nl_meta(iss, False)}{per_s}{cnt}</p>
{nl_body_bridge(iss, hl)}
{vid}
<div class="prose issuetext"{hla}>
{txt}</div>
<section class="nlhome">{f'<p><b>{E(t("nl_get_next"))}</b> {sub}</p>' if sub else ''}
{community_links()}
<p>{t("nl_write", href="../../columnist/")}</p></section>
<p class="meta"><a href="../">← {E(t("nl_all_issues"))}</a></p>
</article>"""
    page(slug, title, "newsletter", body, subtitle or t("nl_desc"))
def build_newsletter():
    """/newsletter/ in every language (the Newsletter tab): the issues (newest first, each with its own page), the own
    form (only when on), the Substack signup link (whenever substack_url is set), the privacy note and the Kaupr disclosure."""
    issues = nl_issues()
    if not newsletter_on() and not issues: return
    root = "../" * (1 + (0 if LANG == "en" else 1))
    lis = []
    for iss in issues:
        if LANG == "en": nl_copy_assets(iss)
        build_issue(iss)
        v = iss.get("video") or {}
        title, tl = nl_i18n(iss, "title"); subtitle, sl = nl_i18n(iss, "subtitle"); _, hl = nl_issue_html(iss)
        th = (f'<a class="th" href="{E(iss["id"])}/" tabindex="-1" aria-hidden="true"><img src="{root}newsletter/{E(iss["id"])}/{E(v["poster"])}" alt="" width="320" height="180" loading="lazy"></a>'
              if v.get("poster") else "")
        lis.append(f'<li>{th}<div><h3{lang_attr(tl)}><a href="{E(iss["id"])}/">{E(title)}</a></h3><div class="meta">{nl_meta(iss)}</div>'
                   f'<p class="sum"{lang_attr(sl)}>{E(subtitle)}</p></div></li>')
    form = newsletter_form()
    sub = substack_button()
    priv = f'<p class="notice">{t("nl_priv")}</p>' if form else ""
    subnote = f'<p class="notice">{t("nl_sub_note")}</p>' if sub and not form else ""
    body = f"""<h1>{E(t("nl_title"))}</h1>
<p class="lead">{E(t("nl_lead"))}</p>
{form}
{f'<p>{sub}</p>' if sub else ''}
{community_links()}
<h2 id="issues">{E(t("nl_issues_h"))}</h2>
<p class="meta">{E(t("nl_issues_lead"))}</p>
<ol class="nlissues">{''.join(lis) or f'<li class="empty">{E(t("nl_issues_none"))}</li>'}</ol>
<p>{t("nl_write", href="../columnist/")}</p>
{substack_embed()}
<div class="prose">{priv}{subnote}
<p class="meta">{t("nl_kaupr")}</p></div>"""
    page("newsletter", t("nl_title"), "newsletter", body, t("nl_desc"))
_ANALYTICS_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
def analytics_token():
    """Public Cloudflare Web Analytics site token. Empty until analytics.json or CF_WEB_ANALYTICS_TOKEN is set."""
    raw = (os.environ.get("CF_WEB_ANALYTICS_TOKEN") or "").strip()
    if not raw:
        raw = str((load(P("analytics.json"), {}) or {}).get("token") or "").strip()
    if not raw or "REPLACE" in raw.upper() or raw.upper() in {"TOKEN", "XXX", "YOUR_TOKEN"}:
        return ""
    if not _ANALYTICS_TOKEN.fullmatch(raw):
        print("analytics: token ignored (paste the public Cloudflare Web Analytics site token)")
        return ""
    return raw
def analytics_snippet():
    """Beacon only after the privacy texts name Cloudflare Web Analytics, and only with a real token."""
    tok = analytics_token()
    if not tok:
        return ""
    payload = E(json.dumps({"token": tok}, separators=(",", ":")))
    return f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon="{payload}"></script>'
LANGSEL_JS = None
def langsel_script():
    global LANGSEL_JS
    if LANGSEL_JS is None: LANGSEL_JS = open(P("tools", "langselect.js"), encoding="utf-8").read()
    return LANGSEL_JS
def push_endpoint():
    """Worker origin for browser push, or None when it is not deployed yet.
    Env PUSH_ENDPOINT wins (empty string hides it). Otherwise workers/push/public.json public_endpoint."""
    e = os.environ.get("PUSH_ENDPOINT")
    if e is not None:
        return e.strip().rstrip("/") or None
    cfg = load(P("workers", "push", "public.json"), {}) or {}
    return (cfg.get("public_endpoint") or "").strip().rstrip("/") or None
_PUSH_JS = None
def push_panel(root):
    """Opt-in block. Left-aligned (start-aligned in RTL). The same button turns notifications off.

    Without a configured Worker URL the page only says the service is not switched on.
    There is no button and no request to a missing backend."""
    if not push_endpoint():
        return (
            f'<section class="pushopt" id="notifications">'
            f'<h2>{E(t("push_title"))}</h2>'
            f'<p>{E(t("push_unavailable"))}</p>'
            f'</section>'
        )
    countries = "".join(
        f'<label class="push-c"><input type="checkbox" name="country" value="{c}"> {flag(c)}{E(t("c_" + c))}</label>'
        for c in COUNTRY_CODES)
    return (
        f'<section class="pushopt" id="notifications" data-root="{E(root)}">'
        f'<h2>{E(t("push_title"))}</h2>'
        f'<p>{E(t("push_lead"))}</p>'
        f'<div class="push-topics" role="group" aria-label="{E(t("push_topics"))}">'
        f'<label class="push-c"><input type="checkbox" name="country" value="ALL" checked> {E(t("push_all"))}</label>'
        f'{countries}</div>'
        f'<p class="meta">{E(t("push_lang_note"))}</p>'
        f'<p><button type="button" class="push-btn">{E(t("push_on"))}</button></p>'
        f'<p class="push-status" role="status" aria-live="polite"></p>'
        f'<p class="meta">{E(t("push_privacy"))}</p>'
        f'<p class="meta">{E(t("push_ios"))}</p>'
        f'<noscript><p>{E(t("push_noscript"))}</p></noscript>'
        f'</section>'
    )
def push_script():
    global _PUSH_JS
    if not push_endpoint():
        return ""
    if _PUSH_JS is None:
        _PUSH_JS = open(P("assets", "push", "client.js"), encoding="utf-8").read()
    keys = ("on", "off", "on_status", "off_status", "unsupported", "denied", "unavailable", "working", "fail", "saved")
    cfg = {"endpoint": push_endpoint() or "", "lang": LANG, "strings": {k: t("push_" + k) for k in keys}}
    return "<script>window.NC_PUSH=" + json.dumps(cfg, ensure_ascii=False) + ";</script><script>\n" + _PUSH_JS + "\n</script>"
def write_push_assets():
    """Service worker and manifest at the site root, so the scope covers every language directory."""
    os.makedirs(os.path.join(SITE, "assets", "push"), exist_ok=True)
    shutil.copy(P("assets", "push", "sw.js"), os.path.join(SITE, "sw.js"))
    for name in ("icon-192.png", "icon-512.png"):
        shutil.copy(P("assets", "push", name), os.path.join(SITE, "assets", "push", name))
    manifest = {
        "name": SITE_NAME,
        "short_name": SITE_NAME,
        "description": "Bitcoin, blockchain and crypto news from the Nordics",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#0f5ea8",
        "icons": [
            {"src": "assets/push/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "assets/push/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ],
    }
    with open(os.path.join(SITE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
def page(slug, title, nav, body, desc, extra_script="", langs=None, head_extra=""):
    """Writes site/<lang>/<slug>/index.html for the current LANG (English at the root)."""
    depth = (slug.count("/") + 1 if slug else 0) + (0 if LANG == "en" else 1)
    root = "../" * depth or "./"           # site root (data/, assets/, screen/)
    rel = root + lp()                      # home of this language
    url = BASE + lp() + (slug + "/" if slug else "")
    s = snippets(url, f"{title} – {SITE_NAME}" if slug else f"{SITE_NAME} – {t('site_desc_suffix')}")
    def _nav_a(n, k):
        quiet = ' class="nav-quiet"' if n == "talks" else ""
        href = rel + (n + "/" if n else "")
        current = " aria-current=page" if n == nav else ""
        return f'<a{quiet} href="{href}"{current}>{E(t(k))}</a>'
    nav_html = "".join(_nav_a(n, k) for n, k in NAV)
    langs = langs or i18n.LANGS
    alt = "".join(f'<link rel="alternate" hreflang="{i18n.HTML_LANG[l]}" href="{BASE}{lp(l)}{slug + "/" if slug else ""}">' for l in langs) + \
        f'<link rel="alternate" hreflang="x-default" href="{BASE}{slug + "/" if slug else ""}">'
    def _sw(l):
        rtl = ' dir="rtl"' if i18n.rtl(l) else ""
        cur = " aria-current=true" if l == LANG else ""
        return (f'<li><a href="{root}{lp(l)}{slug + "/" if slug else ""}" hreflang="{l}" lang="{l}"{rtl} data-lang="{l}"{cur}>{E(i18n.NAME[l])}</a></li>')
    sw = "".join(_sw(l) for l in langs)
    def _opt(l):
        rtl = ' dir="rtl"' if i18n.rtl(l) else ""
        sel = " selected" if l == LANG else ""
        mark = "✓ " if l == LANG else ""
        href = f"{root}{lp(l)}{slug + '/' if slug else ''}"
        return (f'<option value="{E(href)}" hreflang="{l}" lang="{l}"{rtl} data-lang="{l}"{sel}>{mark}{E(i18n.NAME[l])}</option>')
    q = i18n.QUICK.get(LANG)
    quick = (f'<a class="quick" href="{root}{lp(q)}{slug + "/" if slug else ""}" hreflang="{q}" lang="{q}" data-lang="{q}">{E(i18n.NAME[q])}</a>' if q in langs else "")
    # Phones use a native <select> (the iOS picker). Desktop keeps the <details> list. Both list native names.
    pick_html = (f'<span class="langglobe" aria-hidden="true">🌐</span><label class="langpick"><span class="vh">{E(t("lang_choose"))}</span>'
                 f'<select class="langsel">{"".join(_opt(l) for l in langs)}</select></label>')
    switcher = (f'<div class="langsw">{quick}{pick_html}<details><summary aria-label="{E(t("lang_choose"))}">🌐 {E(i18n.NAME[LANG])}</summary>'
                f'<ul role="list" aria-label="{E(t("lang_label"))}">{sw}</ul></details></div>')
    nav_btn = (f'<button type="button" class="navtoggle" aria-expanded="false" aria-controls="sitenav" aria-label="{E(t("main_menu"))}">'
               f'<span class="navbars" aria-hidden="true"><span></span><span></span><span></span></span></button>')
    banner = f'<div class="preview" role="note"><div class="wrap">{t("preview_banner")}</div></div>' if PREVIEW else ""
    # language auto-selection: only on the English home page (site root), see tools/langselect.js
    pick = ""
    if LANG == "en" and not slug:
        pick = ("<script>" + langsel_script().replace("__GEO__", json.dumps((geo_endpoint() + "/api/geo") if geo_endpoint() else None))
                .replace("__COOKIE_PATH__", COOKIE_PATH).replace("__LANGS__", json.dumps(i18n.LANGS)) + "</script>")
    setck = ("<script>(function(){function setLang(c){if(!c)return;"
             f"document.cookie='nc_lang='+c+';path={COOKIE_PATH};max-age=31536000;SameSite=Lax'+(location.protocol==='https:'?';Secure':'');"
             "try{localStorage.setItem('nc_lang',c)}catch(err){}}"
             "document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[data-lang]');if(a)setLang(a.getAttribute('data-lang'))});"
             "document.addEventListener('change',function(e){var s=e.target;if(!s||!s.matches||!s.matches('select.langsel'))return;var o=s.options[s.selectedIndex];if(!o)return;setLang(o.getAttribute('data-lang'));if(o.value)location.href=o.value});"
             "var b=document.querySelector('.navtoggle'),n=document.getElementById('sitenav');if(b&&n){b.addEventListener('click',function(){var open=n.classList.toggle('is-open');b.setAttribute('aria-expanded',open?'true':'false')});"
             "document.addEventListener('keydown',function(e){if(e.key==='Escape'&&n.classList.contains('is-open')){n.classList.remove('is-open');b.setAttribute('aria-expanded','false');b.focus()}})}})();</script>")
    nlfoot = (f'<div class="nlfoot"><b>{E(t("nl_foot"))}</b> {" ".join(x for x in (newsletter_form(True), substack_button()) if x)} <a href="{rel}newsletter/">{E(t("nl_more"))}</a></div>' if newsletter_on() and slug != "newsletter"
              else "")
    doc = f"""<!doctype html>
<html lang="{i18n.HTML_LANG[LANG]}"{" dir=\"rtl\"" if i18n.rtl(LANG) else ""}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script>document.documentElement.classList.add("js")</script>
{pick}<title>{E(title)}{" – " + SITE_NAME if slug else ""}</title>
<meta name="description" content="{E(desc)}"><link rel="canonical" href="{url}"><link rel="manifest" href="{root}manifest.json">{alt}{head_extra}{'<meta name="robots" content="noindex">' if PREVIEW else ''}
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{url}"><meta property="og:type" content="website"><meta property="og:locale" content="{i18n.OG_LOCALE[LANG]}">{''.join(f'<meta property="og:locale:alternate" content="{i18n.OG_LOCALE[l]}">' for l in langs if l != LANG)}
<meta name="referrer" content="strict-origin-when-cross-origin">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%230f5ea8'/%3E%3Crect x='4' width='3' height='16' fill='white'/%3E%3Crect y='6.5' width='16' height='3' fill='white'/%3E%3C/svg%3E">
<style>{CSS}{s['css']}</style></head>
<body>{banner}<header class="top"><div class="wrap"><div class="brandrow"><a class="brand" href="{rel}">Nordic <span>Crypto</span></a><span class="hdrbtns">{header_sub_button()}{header_x_button()}</span></div>{nav_btn}<nav id="sitenav" class="main" aria-label="{E(t("main_menu"))}">{nav_html}</nav>{switcher}</div></header>
<main class="wrap">
{body}
{s['top']}
</main>
<footer><div class="wrap">{nlfoot}{community_links()}{push_panel(root)}{t("footer", site=SITE_NAME, rel=rel, root=root)}</div></footer>
{s['script']}{setck}{extra_script}{newsletter_script()}{push_script()}{analytics_snippet()}
</body></html>"""
    d = os.path.join(SITE, lp(), slug); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(doc)

def redirect(old, new):
    d = os.path.join(SITE, old); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url=../{new}/">'
        f'<link rel="canonical" href="{BASE}{new}/"><title>Moved</title></head><body><p>This page has moved to <a href="../{new}/">{new}</a>.</p></body></html>')

TOPICS = ["bitcoin", "blockchain", "crypto", "regulation", "companies", "mica", "aml", "defi", "nft", "cbdc"]
def topic_label(k): return t("topic_" + k) if i18n.has("en", "topic_" + k) else (k.upper() if len(k) <= 4 else k.capitalize())
def country_chips():
    return "".join(f'<button type="button" class="chip cchip" data-c="{c}" aria-pressed="false">{flag(c)}{E(n)}</button>' for c, n in COUNTRIES.items())
def L18(obj, key, i18n_key=None):
    """Own text in the current language: obj[i18n_key][LANG] if present, else obj[key] (English). Returns (text, lang)."""
    v = ((obj.get(i18n_key or key + "_i18n") or {}).get(LANG)) if LANG != "en" else None
    return (v, LANG) if v else (obj.get(key), "en")
def lang_attr(l): return "" if l == LANG else f' lang="{l}"'
def _source_logos():
    sys.path.insert(0, P("tools"))
    import source_logos
    return source_logos
def copy_repo_file(rel):
    srcp = P(rel)
    if not rel or not os.path.exists(srcp): return
    dst = os.path.join(SITE, rel); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(srcp, dst)
def attach_source_logos(items):
    """Put a checked outlet logo on each story. No logo: the name stays text only."""
    sl = _source_logos()
    for i in items:
        lg = sl.for_source(i.get("source"), preview=PREVIEW)
        if not lg:
            i.pop("source_logo", None); continue
        pub = {k: lg[k] for k in ("file", "source", "source_url", "license", "author") if lg.get(k)}
        if lg.get("pending"): pub["pending"] = True
        i["source_logo"] = pub
        copy_repo_file(lg.get("file"))
def _coverage():
    sys.path.insert(0, P("tools"))
    import coverage
    return coverage
def story_outlets(item):
    """Primary outlet, then every other outlet. Logos are copied when a checked file exists."""
    if item.get("own_story"):
        return []
    rows = _coverage().all_outlets(item)
    sl = _source_logos()
    for row in rows:
        lg = sl.for_source(row.get("outlet"), preview=PREVIEW)
        if not lg:
            row.pop("logo", None); continue
        row["logo"] = {k: lg[k] for k in ("file", "source", "source_url", "license", "author") if lg.get(k)}
        if lg.get("pending"): row["logo"]["pending"] = True
        copy_repo_file(lg.get("file"))
    return rows
def n_sources_label(n, more=False):
    if more: return t("n_sources_more", n=n)
    if n == 1: return t("n_sources_1")
    return t("n_sources", n=n)
def coverage_row(rows, root, page_href):
    """Compact logo row plus a count. One outlet: nothing, the meta line already names it."""
    if len(rows) < 2: return ""
    show, bits = rows[:6], []
    for s in show:
        lg = s.get("logo") or {}
        img = f'<img class="src-logo" src="{root}{E(lg["file"])}" alt="" height="18">' if lg.get("file") else ""
        bits.append(f'<a class="cov-logo" href="{E(s.get("url"))}" rel="noopener" target="_blank" title="{E(s.get("outlet_name"))}" aria-label="{E(s.get("outlet_name"))}">{img or E(s.get("outlet_name") or "")}</a>')
    rest = len(rows) - len(show)
    label = n_sources_label(rest, more=True) if rest else n_sources_label(len(rows))
    bits.append(f'<a class="cov-more" href="{E(page_href)}">{E(label)}</a>')
    return f'<div class="covrow">{"".join(bits)}</div>'
def _cov_when(iso):
    if not iso: return ""
    try: d = dt.datetime.fromisoformat(iso).astimezone(OSLO)
    except ValueError: return ""
    return f"{endate(iso)} {d.strftime('%H:%M')}"
def _bar(label_html, count, share):
    pct = max(0, min(100, round((share or 0) * 100)))
    return (f'<div class="covbar"><span class="covlab">{label_html}</span>'
            f'<span class="track" role="presentation"><span class="fill" style="width:{pct}%"></span></span>'
            f'<span class="covn">{count}</span></div>')
def coverage_bars(rows):
    br = _coverage().breakdown(rows)
    countries = []
    for r in br["by_country"]:
        c = r.get("country") or ""
        if c in COUNTRY_CODES or c in EXTRA_C_CODES: lab = f"{flag(c)} {E(cname(c))}"
        else: lab = E(c or t("cov_unknown"))
        countries.append(_bar(lab, r["count"], r["share"]))
    types = "".join(_bar(E(t("cov_" + r["type"])), r["count"], r["share"]) for r in br["by_source_type"])
    return (f'<h2>{E(t("cov_breakdown"))}</h2><h3>{E(t("cov_by_country"))}</h3><div class="covbars">{"".join(countries)}</div>'
            f'<h3>{E(t("cov_by_type"))}</h3><div class="covbars">{types}</div>')
def _outlet_li(s, root):
    lg = s.get("logo") or {}
    img = f'<img class="src-logo" src="{root}{E(lg["file"])}" alt="" height="18">' if lg.get("file") else ""
    primary = f' <span class="tag">{E(t("cov_primary"))}</span>' if s.get("primary") else ""
    pw = f' · <span class="pw">{E(t("paywall"))}</span>' if s.get("paywall") else ""
    c = s.get("country") or ""
    where = (flag(c) + " " + E(c)) if c else ""
    lang = i18n.SRC_LANG.get(s.get("lang") or "", "")
    lang_attr_s = f' lang="{E(lang)}"' if lang else ""
    return (f'<li data-country="{E(c)}" data-time="{E(s.get("published") or "")}">'
            f'<a class="cov-logo" href="{E(s.get("url"))}" rel="noopener" target="_blank">{img}<b>{E(s.get("outlet_name") or "")}</b></a>'
            f'{primary}<span class="cov-where">{where}</span>'
            f'<span class="cov-title"{lang_attr_s}>{E(s.get("title") or "")}</span>'
            f'<time datetime="{E(s.get("published") or "")}">{E(_cov_when(s.get("published")))}</time>{pw} '
            f'<a class="cov-open" href="{E(s.get("url"))}" rel="noopener" target="_blank">{E(t("cov_open"))}</a></li>')
def coverage_block(rows, root):
    """Full outlet list, grouped by country, with a by-time list the buttons reveal. Left-aligned."""
    order = ["NO", "SE", "DK", "FI", "IS", "NORDIC", "EU"]
    groups = {}
    for s in rows: groups.setdefault(s.get("country") or "", []).append(s)
    blocks = []
    for c in sorted(groups, key=lambda c: (order.index(c) if c in order else 50, c)):
        if c in COUNTRY_CODES or c in EXTRA_C_CODES: head = f"{flag(c)} {E(cname(c))}"
        else: head = E(c or t("cov_unknown"))
        prim = [s for s in groups[c] if s.get("primary")]
        rest = sorted([s for s in groups[c] if not s.get("primary")], key=lambda s: s.get("published") or "", reverse=True)
        blocks.append(f'<section class="covgroup"><h3>{head} <span class="meta">{len(groups[c])}</span></h3>'
                      f'<ul class="covlist">{"".join(_outlet_li(s, root) for s in prim + rest)}</ul></section>')
    flat = "".join(_outlet_li(s, root) for s in sorted(rows, key=lambda s: s.get("published") or "", reverse=True))
    extras = [s for s in rows if not s.get("primary")]
    also = ""
    if extras:
        links = ", ".join(f'<a href="{E(s["url"])}" rel="noopener" target="_blank">{E(s.get("outlet_name") or "")}</a>' for s in extras)
        also = f'<p class="also">{E(t("also_covered"))}: {links}</p>'
    primary = rows[0]
    read = (f'<p class="readat-row"><a class="readat" href="{E(primary.get("url"))}" rel="noopener" target="_blank">'
            f'{E(t("read_at", name=primary.get("outlet_name") or ""))}</a></p>')
    return (read + also + coverage_bars(rows)
            + f'<h2>{E(t("cov_h"))}</h2>'
            + f'<div class="seg covsort" role="group" aria-label="{E(t("cov_sort"))}">'
            + f'<button type="button" data-covsort="country" aria-pressed="true">{E(t("cov_sort_country"))}</button>'
            + f'<button type="button" data-covsort="time" aria-pressed="false">{E(t("cov_sort_time"))}</button></div>'
            + f'<div class="cov-by-country">{"".join(blocks)}</div><div class="cov-by-time" hidden><ul class="covlist">{flat}</ul></div>')
COV_SORT_JS = """<script>
(function(){var box=document.querySelector('.covsort');if(!box)return;var c=document.querySelector('.cov-by-country'),tm=document.querySelector('.cov-by-time');
box.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('button');if(!b)return;var mode=b.getAttribute('data-covsort');
[].forEach.call(box.querySelectorAll('button'),function(x){x.setAttribute('aria-pressed',x===b?'true':'false')});
if(c)c.hidden=mode!=='country';if(tm)tm.hidden=mode!=='time';});})();
</script>"""
def source_mark(i, root=""):
    """Outlet logo, then the source name, in one left-aligned (or RTL start-aligned) row. Text only when there is no logo."""
    name = i.get("source_name") or ""
    lg = i.get("source_logo")
    if lg is None and i.get("source"):
        lg = _source_logos().for_source(i.get("source"), preview=PREVIEW)
    img = ""
    if lg and lg.get("file"):
        pend = f' title="{E(t("pending"))}"' if lg.get("pending") else ""
        img = f'<img class="src-logo" src="{root}{E(lg["file"])}" alt="" height="18" loading="lazy"{pend}>'
    return f'<span class="src">{img}<b>{E(name)}</b></span>'

def _illustrations():
    sys.path.insert(0, P("tools"))
    import illustrations
    return illustrations
def ill_labels():
    return {k: t(k) for k in ("ill_photo", "ill_drawing", "ill_licence", "ill_source", "ill_cropped")}
def asset_prefix(slug):
    """Path from this page to the site root, where assets/ lives."""
    depth = (slug.count("/") + 1 if slug else 0) + (0 if LANG == "en" else 1)
    return "../" * depth
def story_path(i):
    """Our page for this story. Own stories already have a relative url."""
    if i.get("own_story"):
        u = i.get("url") or ""
        if u and not str(u).startswith("http"):
            return u
    return f"stories/{i['id']}/"
def news_head(i):
    """Headline for a card or story page. External headlines stay in the source language."""
    src_l = i18n.SRC_LANG.get(i.get("language") or "", "en")
    if LANG == "en" or i.get("own_story"):
        head = i.get("title_en") or i["title"]
        head_l = "en" if i.get("title_en") or i.get("own_story") else src_l
        orig = ""
        if i.get("title_en") and LANG == "en":
            lname = t("lname_" + i["language"]) if i18n.has("en", "lname_" + (i.get("language") or "")) else (i.get("language") or "")
            orig = f'<p class="orig">{E(t("orig_title", l=lname))}<span lang="{src_l}">{E(i["title"])}</span></p>'
        return head, head_l, orig
    return i["title"], src_l, ""
def story_figure(i, slug, href=None):
    rec = i.get("illustration")
    if not rec:
        return ""
    return _illustrations().figure_html(rec, asset_prefix(slug), ill_labels(), href=href)

def build():
    global LANG
    subprocess.run([sys.executable, P("tools", "apply_approvals.py")], check=True)
    subprocess.run([sys.executable, P("tools", "import_orgchart.py")], check=True)
    news = load(P("data", "news.json"), {"items": []}); org = load(P("data", "orgchart.json"), {"entities": [], "relations": []})
    cfg = load(P("sources.json")); status = load(P("state", "source_status.json"), {})
    if os.path.exists(SITE): shutil.rmtree(SITE)
    os.makedirs(os.path.join(SITE, "data"))
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    write_cname()
    if PREVIEW: open(os.path.join(SITE, ".preview"), "w").write("local preview build – never publish\n")
    for i in news["items"]:  # translated summaries: public only once the editor approved them (summary_i18n_review)
        if not PREVIEW and i.get("summary_i18n_review", "approved") != "approved": i.pop("summary_i18n", None)
    approved = [i for i in news["items"] if i.get("status") == "published" and (i.get("summary") or "").strip()]
    pending = [i for i in news["items"] if i.get("status") == "pending"] if PREVIEW else []
    ctx = {"news": news, "org": org, "cfg": cfg, "status": status, "approved": approved, "pending": pending, "blurbs": load_blurbs()}
    LANG = "en"; ctx["stories"] = build_stories(write=False)
    items = sorted(approved + pending + ctx["stories"], key=lambda i: i["published"], reverse=True); ctx["items"] = items
    attach_source_logos(items)
    _illustrations().attach(items)
    seen_ill = set()
    for i in items:
        rec = i.get("illustration") or {}
        if rec.get("file") and rec["file"] not in seen_ill:
            seen_ill.add(rec["file"])
            copy_repo_file(rec["file"])
    keys = ("id", "url", "title", "title_en", "source", "source_name", "source_logo", "country", "language", "published", "topics", "summary", "summary_i18n", "paywall", "links", "status", "own_story", "illustration")
    cov = _coverage(); sl = _source_logos()
    pub_items = []
    for i in items:
        pub = {k: i.get(k) for k in keys if k in i}
        rows = cov.all_outlets(i)
        extras = []
        for r in rows[1:]:
            ex = {k: r.get(k) for k in ("outlet", "outlet_name", "url", "title", "published", "lang", "country", "source_type") if r.get(k) not in (None, "")}
            ex["paywall"] = bool(r.get("paywall"))
            lg = sl.for_source(r.get("outlet"), preview=PREVIEW)
            if lg:
                ex["source_logo"] = {k: lg[k] for k in ("file", "source", "source_url", "license", "author") if lg.get(k)}
                if lg.get("pending"): ex["source_logo"]["pending"] = True
                copy_repo_file(lg.get("file"))
            extras.append(ex)
        pub["also_covered_by"] = extras
        pub["coverage"] = cov.breakdown(rows)
        pub_items.append(pub)
    for i in pub_items:
        if i.get("status") not in ("published", "owner"): i["summary"] = None; i.pop("summary_i18n", None); i["status"] = "pending"
    json.dump({"updated": news.get("updated"), "preview": PREVIEW, "items": pub_items}, open(os.path.join(SITE, "data", "news.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ents = [e for e in org["entities"] if e.get("sources") and (e.get("status") == "published" or (PREVIEW and e.get("status") == "pending"))]
    eids = {e["id"] for e in ents}
    rels = [r for r in org["relations"] if r.get("sources") and r["from"] in eids and r["to"] in eids and (r.get("status") == "published" or (PREVIEW and r.get("status") == "pending"))]
    for e in ents:  # profile links: only editor-approved ones (preview: pending ones too, marked)
        e["profiles"] = [p for p in (e.get("profiles") or []) if p.get("status") == "published" or PREVIEW]
        for k in ("logo", "image"):  # logos/photos: only editor-checked ones (review "ok"; legacy entries without review were approved via Kryptonytt)
            im = e.get(k)
            if im and not PREVIEW and im.get("review", "ok") != "ok": e.pop(k)
    pub_org = {"updated": org.get("updated"), "preview": PREVIEW, "entities": ents, "relations": rels}
    json.dump(pub_org, open(os.path.join(SITE, "data", "orgchart.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for e in ents:  # images and logos: only used ones with a recorded source
        for k in ("image", "logo"):
            im = e.get(k)
            if im and im.get("file") and (im.get("license") or im.get("source_url")) and os.path.exists(P(im["file"])):
                dst = os.path.join(SITE, im["file"]); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(P(im["file"]), dst)
    ctx.update(ents=ents, rels=rels, pub_org=pub_org)
    ctx["events"] = events_for_site()
    json.dump({"preview": PREVIEW, "events": [e for e in ctx["events"][0] if not e["past"]]}, open(os.path.join(SITE, "data", "events.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.path.insert(0, P("tools"))
    import markets as markets_mod
    try:
        ctx["markets"] = markets_mod.fetch()
    except Exception as ex:
        print("markets: fetch failed:", ex)
        ctx["markets"] = markets_mod.empty_failure(str(ex).split("\n")[0][:300])
    for LANG in i18n.LANGS:
        build_lang(ctx)
    LANG = "en"
    os.makedirs(os.path.join(SITE, "screen"), exist_ok=True)
    open(os.path.join(SITE, "screen", "index.html"), "w", encoding="utf-8").write(
        open(P("templates", "screen.html"), encoding="utf-8").read().replace("__BASE__", BASE).replace("__HOST__", site_url.HOST).replace("__FLAGS__", flags_js()).replace("__PREVIEW__", "true" if PREVIEW else "false").replace("__ANALYTICS__", analytics_snippet()))
    for old, new in (("kalender", "calendar"), ("skjerm", "screen"), ("organisasjonskart", "org-chart"), ("kilder", "sources"), ("om", "about"), ("akademia", "academia")): redirect(old, new)
    active = sorted({(s.get("outlet") and next((x["name"] for x in cfg["sources"] if x["id"] == s.get("outlet")), s["name"]) or s["name"]).split(" (")[0] + "|" + s["country"]
                     for s in cfg["sources"] if s.get("enabled") and s["type"] not in ("bing", "search") and status.get(s["id"], {}).get("ok", True)})
    seen = set(); act = []
    for a in active:
        n, c = a.split("|")
        if n not in seen: seen.add(n); act.append({"name": n, "country": "NO" if n == "Kaupr" else c})
    json.dump({"active": act}, open(os.path.join(SITE, "data", "sources.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    robots = "User-agent: *\n" + ("Disallow: /\n" if PREVIEW else "Allow: /\n")
    if not PREVIEW:
        robots += f"Sitemap: {BASE}sitemap.xml\n"
    open(os.path.join(SITE, "robots.txt"), "w").write(robots)
    write_push_assets()
    emit_api(ctx)
    sitemap()
    write_cname()
    miss = sorted(i18n.MISSING)
    if miss: print(f"i18n: {len(miss)} missing strings fell back to English: {miss[:12]}{' …' if len(miss) > 12 else ''}")
    print(f"build{' (PREVIEW)' if PREVIEW else ''}: {len(items)} stories ({len(approved)} approved, {len(pending)} pending), "
          f"{len(ents)} org rows ({sum(e['type']=='person' for e in ents)} people), {len(rels)} relations, {len(i18n.LANGS)} languages -> {SITE}")

def emit_api(ctx):
    """Public JSON API (api/v1/), human docs at /api/, OpenAPI and llms.txt. Same approved data as the HTML."""
    sys.path.insert(0, P("tools"))
    import api_feed
    ev = ctx.get("events") or ([], None)
    events = ev[0] if isinstance(ev, tuple) else ev
    info = api_feed.write(
        SITE, preview=PREVIEW, base=BASE,
        items=ctx.get("items") or [], events=events or [],
        entities=ctx.get("ents") or [], relations=ctx.get("rels") or [],
        org_updated=(ctx.get("org") or {}).get("updated"),
        regulation=(ctx.get("org") or {}).get("regulation") or [],
        caveats=(ctx.get("org") or {}).get("caveats") or [],
        sources_cfg=ctx.get("cfg") or {},
        news_updated=(ctx.get("news") or {}).get("updated"),
        markets=ctx.get("markets"),
    )
    global LANG
    was = LANG
    LANG = "en"
    page("api", "Data API", "api", api_feed.docs_fragment(info), api_feed.DOCS_DESC, langs=["en"], head_extra=api_feed.head_links(BASE))
    LANG = was
    return info

def lang_template(stem):
    """HTML body for this language. A missing translation uses the English file (UI stub, not a new translation)."""
    if LANG != "en":
        path = P("templates", f"{stem}.{LANG}.html")
        if os.path.exists(path):
            return open(path, encoding="utf-8").read()
    return open(P("templates", f"{stem}.html"), encoding="utf-8").read()

def build_ethics():
    """Press ethics: Nordic Crypto follows Vær Varsom-plakaten. Own wording, not a copy of the code."""
    body = lang_template("ethics")
    page("ethics", t("ethics_title"), "ethics", body, t("ethics_desc"))

def sitemap():
    urls = []
    for dp, _, fs in os.walk(SITE):
        if "index.html" in fs:
            r = os.path.relpath(dp, SITE).replace(os.sep, "/"); r = "" if r == "." else r + "/"
            if r.split("/")[0] in ("kalender", "skjerm", "organisasjonskart", "kilder", "om", "akademia"): continue
            urls.append(BASE + r)
    for rel in ("api/v1/index.json", "api/v1/openapi.json", "api/v1/markets.json", "api/v1/markets/aggregated.json", "llms.txt"):
        if os.path.exists(os.path.join(SITE, rel)):
            urls.append(BASE + rel)
    open(os.path.join(SITE, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{u}</loc></url>\n" for u in sorted(set(urls))) + "</urlset>\n")

def _mk_when(iso):
    return (iso or "").replace("T", " ").replace("+00:00", " UTC")

def _mk_volume(row, base, quote, summed):
    """Volume lines. A missing field is omitted. A published zero is shown."""
    bits = []
    def add(key, unit, day):
        if row.get(key) in (None, ""):
            return
        tmpl = ("mk_vol_sum_24h" if day else "mk_vol_sum_plain") if summed else ("mk_vol_24h" if day else "mk_vol_plain")
        bits.append(t(tmpl, n=M_format(row[key]), unit=unit, count=row.get(key + "_exchanges") or 0))
    add("volume_base_24h", base, True)
    add("volume_quote_24h", quote, True)
    add("volume_base", base, False)
    add("volume_quote", quote, False)
    if not bits:
        return ""
    return '<p class="meta vol">' + " · ".join(E(b) for b in bits) + "</p>"

def M_format(value):
    import markets as M
    return M.format_price(value)

def _mk_agg(pair):
    if not pair:
        return ""
    q = pair["quote"]
    if pair.get("price"):
        price = f'<p class="px">{E(M_format(pair["price"]))} <span class="unit">{E(q)}</span></p>'
    else:
        price = f'<p class="px">{E(t("mk_agg_none"))}</p>'
    if pair.get("method") == "mean_last":
        how = t("mk_agg_last", n=pair.get("last_count") or 0)
    elif pair.get("method") == "mean_bid_ask_mid":
        how = t("mk_agg_mid", n=pair.get("mid_count") or 0)
    else:
        how = t("mk_agg_none")
    span = ""
    if pair.get("min") is not None and pair.get("max") is not None:
        span = " " + t("mk_agg_minmax", min=M_format(pair["min"]), max=M_format(pair["max"]), q=q)
    bits = [how + span, t("mk_agg_exchanges", n=pair.get("exchange_count") or 0)]
    if pair.get("updated_at"):
        bits.append(t("mk_agg_updated", when=_mk_when(pair["updated_at"])))
    vol = pair.get("volume") or {}
    return (
        f'<div class="mkagg"><p class="meta"><b>{E(t("mk_agg"))}</b> · {E(pair["base"])}/{E(q)}</p>'
        f"{price}<p class=\"meta\">{E(' '.join(bits))}</p>"
        f'{_mk_volume(vol, pair["base"], q, True)}</div>'
    )

def build_markets(ctx):
    """Prices page. Static cards from the build-time fetch; markets.js refreshes the JSON and the CORS exchanges."""
    sys.path.insert(0, P("tools"))
    import markets as M
    body = ctx.get("markets") or {}
    tickers = body.get("tickers") or []
    groups = {}
    for row in tickers:
        groups.setdefault(row["base"], {}).setdefault(row["quote"], []).append(row)
    def asset_key(b):
        return (M.ASSET_ORDER.index(b) if b in M.ASSET_ORDER else len(M.ASSET_ORDER), b)
    def quote_key(q):
        return (M.QUOTE_ORDER.index(q) if q in M.QUOTE_ORDER else len(M.QUOTE_ORDER), q)
    def label(b):
        name = M.ASSET_NAMES.get(b)
        return f"{name} ({b})" if name and name != b else b
    root = up1()
    pairs = {(p["base"], p["quote"]): p for p in M.aggregate_pairs(tickers, M.PAGES_BASE, M.CUSTOM_BASE)}
    sections = []
    for base in sorted(groups, key=asset_key):
        logo = M.logo_for(base, M.PAGES_BASE, M.CUSTOM_BASE)
        img = ""
        if logo.get("logo_path"):
            img = f'<img src="{root}{E(logo["logo_path"])}" width="28" height="28" alt="{E(t("mk_logo_alt", name=label(base)))}">'
        bits = [f'<section class="mkasset"><h2>{img}{E(label(base))}</h2>']
        for quote in sorted(groups[base], key=quote_key):
            cards = []
            for row in groups[base][quote]:
                ex = row["exchange"]
                if row.get("last"):
                    price = f'<p class="px">{E(M.format_price(row["last"]))} <span class="unit">{E(row["quote"])}</span></p>'
                else:
                    price = f'<p class="px">{E(t("mk_no_last"))}</p>'
                cards.append(
                    f'<article class="mkcard" data-base="{E(base)}">'
                    f'<p class="meta"><b>{E(ex["name"])}</b> · {flag(ex.get("country"))} {E(cname(ex.get("country")))} · {E(base)}/{E(quote)}</p>'
                    f'{price}'
                    f'<p class="ba"><span>{E(t("mk_bid"))} {E(M.format_price(row.get("bid")))}</span>'
                    f'<span>{E(t("mk_ask"))} {E(M.format_price(row.get("ask")))}</span></p>'
                    f'{_mk_volume(row, base, quote, False)}'
                    f'<p class="meta">{E(t("mk_fetched"))} <time datetime="{E(row.get("fetched_at"))}">{E(_mk_when(row.get("fetched_at")))}</time>'
                    f' · <a href="{E(row.get("source_url"))}" rel="noopener">{E(t("mk_source"))}</a></p>'
                    f'</article>'
                )
            bits.append(f'{_mk_agg(pairs.get((base, quote)))}<h3 class="mkq">{E(t("mk_in", q=quote))}</h3><div class="mkcards">{"".join(cards)}</div>')
        bits.append("</section>")
        sections.append("".join(bits))
    opts = "".join(f'<option value="{E(b)}">{E(label(b))}</option>' for b in sorted(groups, key=asset_key))
    errs = "".join(
        f'<p class="notice warn">{E(t("mk_error", name=ex.get("name") or ex.get("id"), when=_mk_when(ex.get("fetched_at"))))}</p>'
        for ex in (body.get("exchanges") or []) if ex.get("status") != "ok"
    )
    skipped = "".join(
        f'<li><b>{E(s.get("name"))}</b> ({E(s.get("country"))}): {E(s.get("reason"))}</li>'
        for s in (body.get("skipped") or [])
    )
    included = ", ".join(
        f'{ex.get("name")} ({cname(ex.get("country"))})'
        for ex in (body.get("exchanges") or []) if ex.get("status") == "ok"
    )
    strings = {
        "bid": t("mk_bid"), "ask": t("mk_ask"), "fetched": t("mk_fetched"), "source": t("mk_source"),
        "live": t("mk_live"), "file": t("mk_file"), "browser": t("mk_browser"), "empty": t("mk_empty"),
        "no_last": t("mk_no_last"), "in_quote": t("mk_in", q="{q}"), "all": t("mk_all"),
        "error": t("mk_error"),
        "agg": t("mk_agg"), "agg_last": t("mk_agg_last"), "agg_mid": t("mk_agg_mid"),
        "agg_minmax": t("mk_agg_minmax"), "agg_exchanges": t("mk_agg_exchanges"),
        "agg_updated": t("mk_agg_updated"), "agg_none": t("mk_agg_none"),
        "vol_24h": t("mk_vol_24h"), "vol_plain": t("mk_vol_plain"),
        "vol_sum_24h": t("mk_vol_sum_24h"), "vol_sum_plain": t("mk_vol_sum_plain"),
        "logo_alt": t("mk_logo_alt"),
    }
    script = open(P("tools", "markets.js"), encoding="utf-8").read()
    body_html = f"""<div class="markets" id="mk" data-json="{root}api/v1/markets.json">
<h1>{E(t("mk_h1"))}</h1>
<p class="lead">{E(t("mk_lead"))}</p>
<p class="notice">{E(body.get("disclaimer") or t("mk_lead"))}</p>
<p class="appbar"><a class="applink" href="{E(M.IOS_TESTFLIGHT)}" rel="noopener">{E(t("ios_link"))}</a></p>
<p class="meta">{E(t("ios_note"))}</p>
{f'<p class="meta">{E(t("mk_included", names=included))}</p>' if included else ''}
<div class="filters"><label for="mk-asset">{E(t("mk_asset"))}</label>
<select id="mk-asset"><option value="">{E(t("mk_all"))}</option>{opts}</select></div>
<p class="meta" id="mk-status">{E(t("mk_file"))}</p>
<div id="mk-errors">{errs}</div>
<div id="mk-tables">{''.join(sections) or f'<p class="empty">{E(t("mk_empty"))}</p>'}</div>
<h2>{E(t("mk_skipped_h"))}</h2>
<p class="meta">{E(t("mk_skipped_lead"))}</p>
<ul>{skipped}</ul>
<p class="meta">{E(t("mk_refresh"))}</p>
<p class="meta"><a href="{root}api/v1/markets.json">{E(t("mk_json"))}</a>
 · <a href="{root}api/v1/markets/aggregated.json">{E(t("mk_agg_json"))}</a>
 · <a href="{root}api/v1/markets/firi.json">firi</a>
 · <a href="{root}api/v1/markets/nbx.json">nbx</a>
 · <a href="{root}api/v1/markets/coinmotion.json">coinmotion</a>
 · <a href="{root}api/v1/markets/by-asset/BTC.json">BTC</a>
 · <a href="https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json" rel="noopener">{E(t("mk_raw"))}</a></p>
<p class="meta">{E(t("mk_icons"))} <a href="https://github.com/spothq/cryptocurrency-icons" rel="noopener">cryptocurrency-icons</a>.</p>
<noscript><p class="notice">{E(t("mk_noscript"))}</p></noscript>
</div>"""
    page("markets", t("mk_title"), "markets", body_html, t("mk_desc"),
         f"<script>window.NC_MK={json.dumps(strings, ensure_ascii=False)};</script><script>{script}</script>")

def build_lang(ctx):
    items, pending = ctx["items"], ctx["pending"]
    # ---- News ----
    asset = "" if LANG == "en" else "../"
    src_pairs = {}
    for i in items:
        if i.get("source") and i.get("source_name"): src_pairs[i["source"]] = i["source_name"]
        for r in i.get("also_covered_by") or []:
            if isinstance(r, dict) and r.get("outlet"): src_pairs.setdefault(r["outlet"], r.get("outlet_name") or r["outlet"])
    srcs = sorted(src_pairs.items(), key=lambda x: (x[1] or "").lower())
    lis = []
    for i in items:
        pend = i.get("status") not in ("published", "owner"); own = i.get("status") == "owner"
        rows = story_outlets(i)
        multi = len(rows) > 1 and not i.get("own_story")
        if i.get("own_story"): href, ext = i["url"], False
        elif multi: href, ext = f"stories/{i['id']}/", False
        else: href, ext = i["url"], True
        src_ids = " ".join(dict.fromkeys(x for x in [i.get("source")] + [r.get("outlet") for r in rows] if x))
        tags = "".join(f'<span class="tag">{E(topic_label(x))}</span>' for x in i["topics"])
        pw = f' · <span class="pw">{E(t("paywall"))}</span>' if i.get("paywall") else ""
        head, head_l, orig = news_head(i)
        href = story_path(i)
        fig = story_figure(i, "", href)
        lname = i.get("language") or ""
        foreign = bool(lname and i18n.has("en", "lang_" + lname) and lname != i18n.SAME_LANG.get(LANG, "") and head_l != LANG)
        if pend:
            summ = f'<p class="sum pend">{E(t("sum_pending"))}</p>'
            lang = f' · {E(t("lang_" + lname))}' if foreign else ""
        else:
            txt, tl = card_text(i, LANG, ctx["blurbs"])
            # Source language differs from the page: a sentence in the page language, then the summary. Not only «på engelsk».
            if foreign and tl == LANG and (txt or "").strip():
                lang = ""
                summ = (f'<p class="bridge">{E(t("bridge", where=t("lang_" + lname)))}</p>'
                        f'<p class="sum"{lang_attr(tl)}>{E(txt)}</p>')
            else:
                lang = f' · {E(t("lang_" + lname))}' if foreign else ""
                summ = f'<p class="sum"{lang_attr(tl)}>{E(txt)}</p>'
        hl = "" if head_l == LANG else f' lang="{head_l}"'
        lis.append(f'<li data-src="{E(i["source"])}" data-sources="{E(src_ids)}" data-c="{E(i.get("country"))}" data-topics="{E(" ".join(i["topics"]))}">'
                   f'{fig}<div class="storybody">'
                   f'<h3><a href="{E(href)}"{"" if not ext else " rel=noopener target=_blank"}{hl}>{E(head)}</a></h3>{orig}'
                   f'<div class="meta">{flag(i.get("country"))} {E(cname(i.get("country")))} · {source_mark(i, asset)} · <time datetime="{E(i["published"])}">{endate(i["published"])}</time>{lang}{pw} {tags}'
                   + (f' <span class="tag pend">{E(t("pending"))}</span>' if pend else "") + (f' <span class="tag pend">{E(t("owner"))}</span>' if own else "")
                   + (f' <span class="tag">{E(t("our_story"))}</span>' if i.get("own_story") else "") + f'</div>{summ}'
                   + coverage_row(rows, asset, f"stories/{i['id']}/")
                   + "".join(f'<div class="meta">↳ <a href="{E(l["url"])}" rel="noopener" target="_blank">{E(l["label"])}</a></div>' for l in i.get("links", []) or [])
                   + '</div></li>')
    opts = "".join(f'<option value="{E(k)}">{E(n)}</option>' for k, n in srcs)
    tchips = "".join(f'<button type="button" class="chip tchip" data-t="{k}" aria-pressed="false">{E(topic_label(k))}</button>' for k in TOPICS)
    news = ctx["news"]; upd = endate(news["updated"]) if news.get("updated") else ""
    root = "../" if LANG != "en" else ""
    body = f"""<h1>{E(t("home_h1"))}</h1>
<p class="meta"><a href="{root}screen/">{E(t("home_screen"))}</a> · <a href="markets/">{E(t("mk_home_link"))}</a></p>
<p class="appbar"><a class="applink" href="https://testflight.apple.com/join/nQ2fpjZn" rel="noopener">{E(t("ios_link"))}</a></p>
<p class="meta">{E(t("ios_note"))}</p>
<p class="lead">{E(t("home_lead", upd=upd, n=len(items), pend=t("home_pend", n=len(pending)) if pending else ""))}</p>
<div class="filters" role="group" aria-label="{E(t("filters"))}"><span class="lbl">{E(t("country"))}</span><div class="chips">{country_chips()}</div>
<label for="fsrc">{E(t("source"))}</label><select id="fsrc"><option value="">{E(t("all_sources"))}</option>{opts}</select>
<span class="lbl">{E(t("topic"))}</span><div class="chips">{tchips}</div><span id="count" class="meta" aria-live="polite"></span></div>
<ol class="news" id="news">{''.join(lis) or f'<li class="empty">{E(t("no_stories"))}</li>'}</ol>
{f'<section class="nlhome" aria-labelledby="nlhome-h"><h2 id="nlhome-h">{E(t("nl_title"))}</h2>{substack_embed()}{community_links()}</section>' if substack_embed() else f'<section class="nlhome">{community_links()}</section>'}
<p class="notice">{E(t("home_notice"))}</p>"""
    js = """<script>
(function(){var NS=%s,sel=document.getElementById('fsrc'),tc=[].slice.call(document.querySelectorAll('.tchip')),cc=[].slice.call(document.querySelectorAll('.cchip')),lis=[].slice.call(document.querySelectorAll('#news li[data-src]')),cnt=document.getElementById('count');
function on(a,k){return a.filter(function(c){return c.getAttribute('aria-pressed')==='true'}).map(function(c){return c.dataset[k]})}
function apply(push){var s=sel.value,t=on(tc,'t'),c=on(cc,'c'),n=0;
lis.forEach(function(li){var ids=(li.dataset.sources||li.dataset.src||'').split(' ');var ok=(!s||ids.indexOf(s)>=0)&&(!c.length||c.indexOf(li.dataset.c)>=0)&&(!t.length||t.some(function(x){return (' '+li.dataset.topics+' ').indexOf(' '+x+' ')>=0}));li.hidden=!ok;if(ok)n++});
cnt.textContent=NS.replace('{n}',n);if(push){var p=new URLSearchParams();if(c.length)p.set('country',c.join(','));if(s)p.set('source',s);if(t.length)p.set('topic',t.join(','));history.replaceState(null,'',p.toString()?'#'+p:location.pathname)}}
var p=new URLSearchParams(location.hash.slice(1));if(p.get('source'))sel.value=p.get('source');
(p.get('topic')||'').split(',').forEach(function(x){tc.forEach(function(c){if(c.dataset.t===x)c.setAttribute('aria-pressed','true')})});
(p.get('country')||'').split(',').forEach(function(x){cc.forEach(function(c){if(c.dataset.c===x)c.setAttribute('aria-pressed','true')})});
sel.addEventListener('change',function(){apply(1)});tc.concat(cc).forEach(function(c){c.addEventListener('click',function(){c.setAttribute('aria-pressed',c.getAttribute('aria-pressed')==='true'?'false':'true');apply(1)})});apply(0)})();
</script>""" % json.dumps(i18n.strings(LANG).get("n_stories") or i18n.strings("en")["n_stories"])
    page("", t("home_title"), "", body, t("home_desc"), js)
    build_coverage_pages(items, ctx["blurbs"])
    build_stories(write=True)
    build_external_stories(ctx)
    build_markets(ctx)
    build_org(ctx)
    build_sources(ctx)
    build_calendar(ctx)
    build_talks()
    build_academia()
    build_changelog()
    build_tip()
    build_columnist()
    build_newsletter()
    build_rules(ctx)
    build_regulation_videos(ctx)
    about = lang_template("about").replace("{{UP}}", up1()).replace("{{COMMUNITY}}", community_section())
    page("about", t("about_title"), "about", about, t("about_desc"))
    build_ethics()

# ---- Industry map: categories from the org chart data (group + description keywords; overrides in industry_map.json) ----
MAP_CATS = ["exchanges", "wallets", "infra", "payments", "finance", "consulting", "media", "academia", "other", "intl", "public"]
GROUP_CAT = {"Exchanges & brokers": "exchanges", "MiCA-licensed providers (CASPs)": "exchanges", "Mining & data centres": "infra",
             "Stablecoin / e-money token issuers": "payments", "Banks": "finance", "Investors & funds": "finance", "ETP issuers": "finance",
             "Media": "media", "Associations & communities": "media", "International players in the Nordics": "intl"}
def map_category(e, over):
    if e["id"] in over: return over[e["id"]]
    if e.get("sector") == "public": return "public"
    d = (e.get("description") or "").lower() + " " + e["name"].lower()
    g = GROUP_CAT.get(e.get("group"))
    if g in ("exchanges",) and re.search(r"\b(wallet|custod)", d) and not re.search(r"exchange|broker|trading|platform", d): return "wallets"
    if g: return g
    if re.search(r"\b(law firm|legal|lawyer|advokat|audit|accounting|consult|advis)", d): return "consulting"
    if re.search(r"\b(wallet|custod)", d): return "wallets"
    if re.search(r"\b(payment|pay\b|card|remittance|e-money|stablecoin)", d): return "payments"
    if re.search(r"\b(university|research centre|academ)", d): return "academia"
    if re.search(r"\b(mining|miner|data cent|infrastructure|node|protocol|blockchain platform|software|developer|tokenis)", d): return "infra"
    if re.search(r"\b(bank|fund|invest|asset manag|etp|etf)", d): return "finance"
    if re.search(r"\b(media|news|podcast|community|association|meetup)", d): return "media"
    return "other"
def ini(n): return "".join(w[0] for w in re.split(r"[\s-]+", re.sub(r"\(.*?\)", "", n)) if w)[:2].upper()
def logo_html(e, cls="logo", root=""):
    lg = e.get("logo")
    if lg and lg.get("file"):
        return f'<img class="{cls}" src="{root}{E(lg["file"])}" alt="{E(t("js_logo_alt", name=e["name"]))}" loading="lazy" width="40" height="40">'
    return f'<span class="av org" aria-hidden="true">{E(ini(e["name"]))}</span>'
def industry_map(ents):
    over = (load(P("industry_map.json"), {}) or {}).get("category", {})
    orgs = [e for e in ents if e["type"] != "person" and e.get("group") != "Legislation"]
    root = up1()
    by = {}
    for e in orgs: by.setdefault(map_category(e, over), []).append(e)
    def tile(e):
        return (f'<a class="tile" href="#{E(e["id"])}" data-c="{E(e["country"])}" data-go="{E(e["id"])}">{logo_html(e, root=root)}'
                f'<span>{E(e["name"])}</span><span class="fl">{flag(e["country"]) if e["country"] in COUNTRY_CODES else E(e["country"])}</span></a>')
    srt = lambda L: sorted(L, key=lambda e: (([*COUNTRY_CODES, "NORDIC", "EU"].index(e["country"]) if e["country"] in [*COUNTRY_CODES, "NORDIC", "EU"] else 9), e["name"].lower()))
    bycat = "".join(f'<section class="imap-cat{" pub" if c == "public" else ""}" data-cat="{c}"><h3><span>{E(t("cat_" + c))}</span><span class="meta">{len(by[c])}</span></h3><div class="tiles">{"".join(tile(e) for e in srt(by[c]))}</div></section>'
                    for c in MAP_CATS if by.get(c))
    cs = [c for c in [*COUNTRY_CODES, "NORDIC", "EU"] if any(e["country"] == c for e in orgs)]
    bycountry = "".join(f'<section class="imap-cat" data-c="{c}"><h3><span>{flag(c) if c in COUNTRY_CODES else ""} {E(cname(c))}</span><span class="meta">{sum(e["country"] == c for e in orgs)}</span></h3><div class="tiles">'
                        + "".join(tile(e) for cat in MAP_CATS for e in sorted(by.get(cat, []), key=lambda e: e["name"].lower()) if e["country"] == c) + '</div></section>' for c in cs)
    return (f'<h2 id="industry-map">{E(t("map_h"))}</h2><p class="lead">{E(t("map_lead"))} <a href="../rules/">{E(t("rules_link"))}</a></p><p class="notice">{t("map_kaupr")}</p>'
            f'<div class="seg" role="group" aria-label="{E(t("map_group"))}"><button type="button" data-view="cat" aria-pressed="true">{E(t("map_by_cat"))}</button><button type="button" data-view="country" aria-pressed="false">{E(t("map_by_country"))}</button></div>'
            f'<div class="imap" id="imap" data-view="cat"><div class="imap-cats imap-bycat">{bycat}</div><div class="imap-cats imap-bycountry">{bycountry}</div></div>'), {c: len(v) for c, v in by.items()}

def build_org(ctx):
    org, ents, pub_org = ctx["org"], ctx["ents"], ctx["pub_org"]
    regs = []
    for r in org.get("regulation", []):
        regs.append(f'<article data-c="{E(r["country"])}"><h3>{flag(r["country"], True)}{E(cname(r["country"]))}</h3><dl lang="en"><dt>{E(t("reg_mica"))}</dt><dd>{E(r["mica"])}</dd><dt>{E(t("reg_law"))}</dt><dd>{E(r["law"])}</dd>'
                    f'<dt>{E(t("reg_auth"))}</dt><dd>{E(r["regulator"])}</dd><dt>{E(t("reg_status"))}</dt><dd>{E(r["status"])}</dd></dl><p class="meta">{E(t("reg_sources"))} '
                    + ", ".join(f'<a href="{E(s["url"])}" rel="noopener" target="_blank">{E(s["source_name"])}</a>' for s in r["sources"]) + '</p></article>')
    cnt_pend = sum(e["status"] == "pending" for e in ents)
    imap, per_cat = industry_map(ents)
    i18n_js = {k[3:]: t(k) for k in i18n.strings("en") if k.startswith("js_")}
    groups = {g: t("grp_" + g) for g in {e.get("group") for e in ents if e.get("group")} if i18n.has("en", "grp_" + g)}
    dn = t("data_en_note")
    body = f"""<h1>{E(t("org_title"))}</h1>
<p class="lead">{E(t("org_lead"))} <a href="#industry-map">{E(t("map_h"))} ↓</a> · <a href="../rules/">{E(t("rules_link"))}</a></p>
{f'<p class="notice warn">{t("org_preview", p=cnt_pend, n=len(ents))}</p>' if PREVIEW and cnt_pend else ''}
{f'<p class="meta">{E(dn)}</p>' if dn else ''}
<h2 id="regulation">{E(t("org_reg_h"))}</h2>
<div class="reg">{''.join(regs)}</div>
{(f'<details class="notice"><summary>{E(t("caveats"))}</summary><ul lang="en">' + "".join(f"<li>{E(x)}</li>" for x in org.get("caveats", [])) + '</ul></details>') if org.get("caveats") else ''}
<h2 id="org">{E(t("org_chart_h"))}</h2>
<div class="filters"><span class="lbl">{E(t("country"))}</span><div class="chips">{country_chips()}</div>
<div class="seg" id="secseg" role="group" aria-label="{E(t("sector_aria"))}"><button type="button" data-v="both" aria-pressed="true">{E(t("both"))}</button><button type="button" data-v="private" aria-pressed="false">{E(t("private_sector"))}</button><button type="button" data-v="public" aria-pressed="false">{E(t("public_sector"))}</button></div>
<label for="osearch">{E(t("search"))}</label><input type="search" id="osearch" placeholder="{E(t("search_ph"))}"></div>
<div id="chart" class="cols"><noscript>{E(t("chart_noscript"))}</noscript></div>
<section id="detail" hidden aria-live="polite"></section>
{imap}
<h2 id="list">{E(t("list_h"))}</h2>
<div class="tablewrap"><table class="list" id="olist"><thead><tr><th>{E(t("th_name"))}</th><th>{E(t("th_country"))}</th><th>{E(t("th_type"))}</th><th>{E(t("th_sector"))}</th><th>{E(t("th_role"))}</th><th>{E(t("th_sources"))}</th></tr></thead><tbody></tbody></table></div>
<p class="notice">{t("org_notice")}</p>
<p class="notice">{t("org_kaupr")}</p>
<script id="orgdata" type="application/json">{json.dumps(pub_org, ensure_ascii=False).replace("</", "<\\/")}</script>
<script>window.FLAGS={flags_js()};window.CNAME={json.dumps({c: cname(c) for c in COUNTRY_CODES + EXTRA_C_CODES}, ensure_ascii=False)};window.T={json.dumps(i18n_js, ensure_ascii=False)};window.GRP={json.dumps(groups, ensure_ascii=False)};window.ROOT={json.dumps(up1())};window.LANG={json.dumps(LANG)};</script>"""
    page("org-chart", t("org_title"), "org-chart", body, t("org_desc"),
         "<script>" + open(P("tools", "orgchart.js"), encoding="utf-8").read() + "</script>")
    if LANG == "en": print(f"industry map: {per_cat}")

def build_sources(ctx):
    cfg, status = ctx["cfg"], ctx["status"]
    rows = []
    for c in COUNTRY_CODES:
        for s in [x for x in cfg["sources"] if x.get("country") == c]:
            st = status.get(s["id"], {})
            if s["type"] == "search": cls, lab = "ok", t("st_manual")
            elif s.get("enabled") and st.get("ok", True) is not False: cls, lab = "ok", t("st_monitored") + (t("st_items", n=st.get("entries")) if st.get("entries") is not None else "")
            elif s.get("search_fallback"): cls, lab = "bad", t("st_fallback")
            else: cls, lab = "bad", t("st_broken") if s.get("enabled") else t("st_unused")
            feed = f'<a href="{E(s["feed"])}" rel="noopener">{E(t("feed") if s["type"] in ("rss", "rss-all") else t("list_page"))}</a>' if s.get("feed") and "{q}" not in s["feed"] else (E(t("search_w")) if s.get("feed") else "–")
            kind = t("kind_" + s["kind"]) if i18n.has("en", "kind_" + s["kind"]) else s["kind"]
            rows.append(f'<tr data-c="{c}"><td>{flag(c)}</td><td><a href="{E(s["url"])}" rel="noopener" target="_blank">{E(s["name"])}</a>{" <span class=pw>" + E(t("paywall_w")) + "</span>" if s.get("paywall") else ""}</td><td>{E(kind)}</td><td>{feed}</td>'
                        f'<td class="{cls}">{E(lab)}</td><td lang="en">{E(s.get("status", ""))}</td></tr>')
    erows = []
    for s in cfg.get("event_sources", []):
        if event_block.blocked_source(s): continue
        st = status.get("ev-" + s["id"], {})
        cls, lab = ("ok", t("st_monitored")) if s.get("enabled", True) and st.get("ok", True) else ("bad", t("st_broken") if s.get("enabled", True) else t("st_unused"))
        erows.append(f'<tr><td>{flag(s.get("country"))}</td><td><a href="{E(s["url"])}" rel="noopener" target="_blank">{E(s["name"])}</a></td><td class="{cls}">{E(lab)}</td><td lang="en">{E(s.get("status", ""))}</td></tr>')
    bing = [s for s in cfg["sources"] if s["type"] == "bing"]
    qs = "".join(f'<li>{flag(s["country"])} {E(", ".join(s.get("queries", [])))} – {E(t("src_only_tld", tld=s["allowed_tld"]))}</li>' for s in bing)
    body = f"""<h1>{E(t("src_h1"))}</h1>
<p class="lead">{E(t("src_lead", d=cfg.get("min_delay_seconds", 2)))}</p>
<div class="tablewrap"><table class="list"><thead><tr><th></th><th>{E(t("th_source"))}</th><th>{E(t("th_type"))}</th><th>{E(t("th_feed"))}</th><th>{E(t("th_status"))}</th><th>{E(t("th_note"))}</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="notice" id="kaupr">{t("kaupr")}</p>
<h2>{E(t("src_terms_h"))}</h2><ul class="prose">{qs}</ul><p class="prose">{E(t("src_search_note"))}</p>
<h2>{E(t("src_kw_h"))}</h2><p class="prose">{E(t("src_kw"))}</p>
<h2 id="events">{E(t("src_ev_h"))}</h2>
<div class="tablewrap"><table class="list"><thead><tr><th></th><th>{E(t("th_event_source"))}</th><th>{E(t("th_status"))}</th><th>{E(t("th_note"))}</th></tr></thead><tbody>{''.join(erows)}</tbody></table></div>
<p class="meta">{t("src_missing")}</p>"""
    page("sources", t("src_title"), "sources", body, t("src_desc"))

def md_inline(s):
    s = E(s)
    s = re.sub(r"(https?://[^\s<;]+[^\s<;.,)])", r'<a href="\1" rel="noopener" target="_blank">\1</a>', s)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
def first_sentence(s):
    for m in re.finditer(r"[.!?](?=\s+[A-ZÁÉÍÓÚÞÆÖØÅÄ])", s):
        if not re.search(r"\b(No|Nos|Act|Art|Reg|e\.g|i\.e|Mr|Ms|Dr|ehf|hf)\.$", s[:m.end()]): return s[:m.end()]
    return s
def build_coverage_pages(items, blurbs):
    """One page per external story: the primary 'Read at' link, every other outlet, and the coverage bars."""
    root = up1() + "../"
    back = "../../"
    for i in items:
        if i.get("own_story"): continue
        rows = story_outlets(i)
        if not rows: continue
        src_l = i18n.SRC_LANG.get(i.get("language") or "", "en")
        if LANG == "en":
            head = i.get("title_en") or i["title"]
            head_l = "en" if i.get("title_en") else src_l
            orig = (f'<p class="orig">{E(t("orig_title", l=t("lname_" + i["language"]) if i18n.has("en", "lname_" + (i.get("language") or "")) else (i.get("language") or "")))}<span lang="{src_l}">{E(i["title"])}</span></p>'
                    if i.get("title_en") else "")
        else:
            head, head_l, orig = i["title"], src_l, ""
        hl = "" if head_l == LANG else f' lang="{head_l}"'
        pend = i.get("status") not in ("published", "owner")
        if pend:
            summ = f'<p class="sum pend">{E(t("sum_pending"))}</p>'
        else:
            txt, tl = card_text(i, LANG, blurbs)
            summ = f'<p class="sum"{lang_attr(tl)}>{E(txt)}</p>'
        pw = f' · <span class="pw">{E(t("paywall"))}</span>' if i.get("paywall") else ""
        fig = story_figure(i, "stories/" + i["id"])
        rec = i.get("illustration") or {}
        og = f'<meta property="og:image" content="{E(BASE + rec["file"])}">' if rec.get("file") else ""
        picture = fig + (f'<p class="notice">{E(t("ill_not_press"))}</p>' if rec else "")
        body = (f'<p class="meta"><a href="{back}">{E(t("back_news"))}</a></p>'
                + picture
                + f'<article class="prose"><h1{hl}>{E(head)}</h1>{orig}'
                f'<p class="meta">{flag(i.get("country"))} {E(cname(i.get("country")))} · {source_mark(i, root)} · <time datetime="{E(i["published"])}">{endate(i["published"])}</time>{pw}'
                + (f' <span class="tag pend">{E(t("pending"))}</span>' if pend else "") + '</p>'
                + summ + coverage_block(rows, root) + '</article>'
                + f'<p class="notice">{E(t("home_notice"))}</p>')
        page("stories/" + i["id"], head, "", body, (i.get("summary") or head or "")[:200], COV_SORT_JS, head_extra=og)
def build_stories(write=True):
    """Own stories written by the editor (markdown, English). Public build: only slugs in approved.json stories.approve.
    Preview: also stories.ready_for_owner, tagged as awaiting jQrgen's final approval. The 'Editor notes' part is internal and never rendered.
    Per-language summaries for the news list: stories.summaries_i18n {slug: {lang: text}}. The article itself is English only
    (other languages show a note) until the editor adds a translated file in stories.files_i18n {slug: {lang: path}}."""
    st = (load(P("queue", "approved.json"), {}) or {}).get("stories", {}) or {}
    out = []
    for slug, path in (st.get("files") or {}).items():
        if slug in st.get("approve", []): status = "published"
        elif PREVIEW and slug in st.get("ready_for_owner", []): status = "owner"
        else: continue
        tr = ((st.get("files_i18n") or {}).get(slug) or {}).get(LANG)
        src = tr if (tr and LANG != "en" and os.path.exists(tr)) else path
        if not os.path.exists(src): print("story missing:", src); continue
        art_l = LANG if src == tr else "en"
        md = open(src, encoding="utf-8").read().split("\nEditor notes")[0]
        title, country, paras, srcs, cur, sec = None, None, [], [], [], None
        for line in md.splitlines():
            l = line.strip()
            if l.startswith("# "): continue
            if l.startswith("## "): title = l[3:]; continue
            if l.startswith("Country:"): country = {"Iceland": "IS", "Norway": "NO", "Sweden": "SE", "Denmark": "DK", "Finland": "FI"}.get(l.split("·")[0].split(":", 1)[1].strip(), "NORDIC"); continue
            if l == "Sources:": sec = "src"; continue
            if sec == "src" and l.startswith("- "): srcs.append(l[2:]); continue
            if not l:
                if cur: paras.append(" ".join(cur)); cur = []
                continue
            cur.append(l)
        if cur: paras.append(" ".join(cur))
        pub = dt.datetime.fromtimestamp(os.path.getmtime(path), OSLO).replace(microsecond=0).isoformat()
        story = {"id": "story-" + slug, "url": f"stories/{slug}/", "title": title, "source": "nordic-crypto", "source_name": "Nordic Crypto",
                 "country": country, "language": "English", "published": pub, "topics": ["regulation"], "status": status, "own_story": True}
        ill = _illustrations().assign(story)
        if write:
            note = t("story_only_en")
            fig = _illustrations().figure_html(ill, asset_prefix("stories/" + slug), ill_labels())
            og = f'<meta property="og:image" content="{E(BASE + ill["file"])}">' if ill else ""
            body = (f'<p class="meta"><a href="../../">{E(t("back_news"))}</a></p>' + (f'<p class="notice">{E(note)}</p>' if note and art_l == "en" and LANG != "en" else "")
                    + fig
                    + f'<p class="notice">{E(t("ill_not_press"))}</p>'
                    + f'<article class="prose"{lang_attr(art_l)}><h1>{E(title)}</h1>'
                    f'<p class="meta">{flag(country)} {E(cname(country))} · {source_mark({"source": "nordic-crypto", "source_name": "Nordic Crypto"}, up1() + "../")} · {endate(pub)}'
                    + (f' <span class="tag pend">{E(t("owner"))}</span>' if status == "owner" else "") + '</p>'
                    + "".join(f"<p>{md_inline(x)}</p>" for x in paras)
                    + f'<h2>{E(t("sources_h"))}</h2><ul>' + "".join(f"<li>{md_inline(s)}</li>" for s in srcs) + '</ul></article>'
                    + f'<p class="notice">{t("story_notice", rel="../../")}</p>')
            page("stories/" + slug, title, "stories", body, paras[0][:200] if paras else title, head_extra=og)
        editor_sum = ((st.get("summaries") or {}).get(slug) or "").strip()
        opening = opening_sentences(" ".join(paras)) if paras else ""
        first = editor_sum if substantive(editor_sum) else (opening or editor_sum or (first_sentence(paras[0]) if paras else ""))
        out.append({"id": "story-" + slug, "url": f"stories/{slug}/", "title": title, "source": "nordic-crypto", "source_name": "Nordic Crypto",
                    "country": country, "language": "English", "published": pub, "topics": ["regulation"], "summary": first,
                    "summary_i18n": (st.get("summaries_i18n") or {}).get(slug) or {}, "status": status, "own_story": True})
    return out

def build_external_stories(ctx):
    """Pictures and the source link are written by build_coverage_pages, which also keeps the outlet list."""
    return
    """One page per external story: our picture, our summary, a link to the source. No article text."""
    asset = asset_prefix("stories/x")
    for i in ctx["items"]:
        if i.get("own_story") or not i.get("id"):
            continue
        slug = "stories/" + i["id"]
        head, head_l, orig = news_head(i)
        hl = "" if head_l == LANG else f' lang="{head_l}"'
        fig = story_figure(i, slug)
        rec = i.get("illustration") or {}
        og = f'<meta property="og:image" content="{E(BASE + rec["file"])}">' if rec.get("file") else ""
        if i.get("status") not in ("published", "owner"):
            summ = f'<p class="sum pend">{E(t("sum_pending"))}</p>'
        else:
            txt, tl = card_text(i, LANG, ctx.get("blurbs"))
            summ = f'<p class="sum"{lang_attr(tl)}>{E(txt)}</p>' if txt else ""
        pw = f' <span class="pw">{E(t("paywall"))}</span>' if i.get("paywall") else ""
        body = (f'<p class="meta"><a href="../../">{E(t("back_news"))}</a></p>'
                + fig
                + f'<p class="notice">{E(t("ill_not_press"))}</p>'
                + f'<article class="story"><h1{hl}>{E(head)}</h1>{orig}'
                + f'<p class="meta">{flag(i.get("country"))} {E(cname(i.get("country")))} · {source_mark(i, asset)} · <time datetime="{E(i["published"])}">{endate(i["published"])}</time>{pw}</p>'
                + summ
                + f'<p><a href="{E(i["url"])}" rel="noopener">{E(t("read_at", source=i.get("source_name") or ""))}</a></p>'
                + "</article>")
        page(slug, head, "", body, (i.get("summary") or head or "")[:200], head_extra=og)

def events_for_site():
    ev = load(P("data", "events.json"), {"events": []})
    ap_path = P("queue", "approved.json"); approvals_present = os.path.exists(ap_path)
    ap = (load(ap_path, {}) or {}).get("events", {}) or {}
    now = dt.datetime.now(OSLO); out = []  # "finished" is judged in Oslo time
    for e in ev["events"]:
        e = dict(e)
        status = event_block.publication_status(e, ap, PREVIEW, approvals_present, from_archive=False)
        if not status: continue
        e["status"] = status
        if not (e.get("place") or e.get("online")) or not e.get("organiser") or not e.get("start"): continue  # rule: date, place and organiser
        e["note"] = ap.get("notes", {}).get(e["id"]) or (e.get("note") if PREVIEW else None)
        if e["id"] in (ap.get("title_en") or {}): e["title_orig"] = e["title"]; e["title"] = ap["title_en"][e["id"]]
        if e["id"] in ap.get("sponsored", []): e["sponsored"] = True
        if e["id"] in ap.get("sponsor", {}): e["sponsored"] = ap["sponsor"][e["id"]]
        if e["id"] in ap.get("paid", {}): e["paid"] = ap["paid"][e["id"]]
        if e["status"] == "published": e["note"] = ap.get("notes", {}).get(e["id"])  # archive/public: editor's note only
        e["note_i18n"] = (ap.get("notes_i18n") or {}).get(e["id"]) if e.get("note") else None
        site_url.brand_note(e)  # approved.json is local and may still reverse the brand name
        e["past"] = dt.datetime.fromisoformat(e.get("end") or e["start"]) < now
        out.append({k: e.get(k) for k in ("id", "title", "title_orig", "start", "end", "place", "city", "country", "online", "organiser", "url", "source", "paid", "sponsored", "note", "note_i18n", "past", "status")})
    # Archive: events whose ids are in events.approve. A status of "published" on the row is not
    # approval. Finished events stay under "Past events". Predatory listings are removed and not shown.
    arkf = P("archive", "events.json"); ark = load(arkf, {"events": []}); by = {}
    for raw in ark.get("events") or []:
        if event_block.blocked_event(raw): continue
        by[raw["id"]] = raw
    for e in out:
        if e["status"] == "published" and not event_block.blocked_event(e):
            by[e["id"]] = {k: v for k, v in e.items() if k != "past"}
    ark["_how_to"] = "Archive of editor-approved events (written by build.py). An event is published only when its id is in queue/approved.json events.approve. Finished events stay under 'Past events'. Predatory conference listings are removed and are not shown."
    ark["events"] = sorted(by.values(), key=lambda e: dt.datetime.fromisoformat(e["start"]))
    os.makedirs(os.path.dirname(arkf), exist_ok=True)
    json.dump(ark, open(arkf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    seen = {e["id"] for e in out}
    for raw in ark["events"]:  # archived events that have dropped out of data/events.json (e.g. finished ones)
        if raw["id"] in seen: continue
        e = dict(raw)
        status = event_block.publication_status(e, ap, PREVIEW, approvals_present, from_archive=True)
        if not status: continue  # not on the approve list, rejected, or a predatory listing
        e["status"] = status
        e["note_i18n"] = e.get("note_i18n") or ((ap.get("notes_i18n") or {}).get(e["id"]) if e.get("note") else None)
        site_url.brand_note(e)
        e["past"] = dt.datetime.fromisoformat(e.get("end") or e["start"]) < now; out.append(e)
    return sorted(out, key=lambda e: dt.datetime.fromisoformat(e["start"])), now

TALK_COUNTRIES = ["NO", "SE", "DK", "FI", "IS", "FO", "GL", "AX"]
_TALK_LANG = {
    "en": "lname_English", "no": "lname_Norwegian", "nb": "lname_Norwegian", "nn": "lname_Norwegian",
    "sv": "lname_Swedish", "da": "lname_Danish", "fi": "lname_Finnish", "is": "lname_Icelandic",
}

def load_talks():
    """Public talk rows from data/talks.json, newest talk date first (publish date if the talk date is empty)."""
    raw = load(P("data", "talks.json"), {"talks": []}) or {"talks": []}
    rows = [t for t in (raw.get("talks") or []) if isinstance(t, dict) and t.get("id") and t.get("video_url")]
    def key(row):
        return row.get("date") or row.get("published") or ""
    return sorted(rows, key=key, reverse=True)

def _talk_embed(row):
    """Official player URL, only when the stored oEmbed check said embedding is allowed."""
    if not row.get("embed"):
        return None
    sys.path.insert(0, P("tools"))
    import talks as talks_mod
    platform = row.get("platform")
    if platform == "youtube":
        vid = talks_mod.youtube_id(row.get("video_url"))
        return f"https://www.youtube-nocookie.com/embed/{vid}?rel=0" if vid else None
    if platform == "vimeo":
        vid = talks_mod.vimeo_id(row.get("video_url"))
        return f"https://player.vimeo.com/video/{vid}" if vid else None
    return None

def _talk_when(iso):
    if not iso or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
        return ""
    try:
        return i18n.short_date(LANG, dt.date.fromisoformat(iso))
    except ValueError:
        return iso

def _talk_duration(value):
    """ISO 8601 duration from the platform, shown as H:MM:SS. Empty when the platform did not state a length."""
    if not value:
        return ""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not m or not any(m.groups()):
        return value
    hours, minutes, seconds = (int(m.group(1) or 0), int(m.group(2) or 0), int(m.group(3) or 0))
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def _talk_lang_label(code):
    key = _TALK_LANG.get(code or "")
    if key and i18n.has("en", key):
        return t(key)
    return code or ""

def build_talks():
    """ /talks/ : public Nordic crypto talks, newest first. The player is not in the HTML until a click."""
    rows = load_talks()
    years = sorted({(r.get("date") or r.get("published") or "")[:4] for r in rows if (r.get("date") or r.get("published") or "")[:4].isdigit()}, reverse=True)
    langs = []
    for r in rows:
        code = r.get("language") or ""
        if code and code not in langs:
            langs.append(code)
    unknown = any(not r.get("language") for r in rows)
    def chips(codes):
        return "".join(
            f'<button type="button" class="chip tcountry" data-c="{E(c)}" aria-pressed="false">{flag(c)}{E(t("c_" + c) if i18n.has("en", "c_" + c) else c)}</button>'
            for c in codes)
    lang_chips = "".join(
        f'<button type="button" class="chip tlang" data-l="{E(c)}" aria-pressed="false">{E(_talk_lang_label(c))}</button>'
        for c in langs)
    if unknown:
        lang_chips += f'<button type="button" class="chip tlang" data-l="" aria-pressed="false">{E(t("talks_lang_unknown"))}</button>'
    year_opts = f'<option value="">{E(t("talks_year_all"))}</option>' + "".join(f'<option value="{E(y)}">{E(y)}</option>' for y in years)
    def article(r):
        embed = _talk_embed(r)
        held = _talk_when(r.get("date"))
        published = _talk_when(r.get("published"))
        duration = _talk_duration(r.get("duration"))
        speakers = [s for s in (r.get("speakers") or []) if s]
        bits = []
        if held:
            bits.append(f'{E(t("talks_held"))}: <time datetime="{E(r.get("date"))}">{E(held)}</time>')
        if r.get("city") or r.get("country"):
            place = ", ".join(p for p in (r.get("city"), cname(r.get("country")) if r.get("country") else "") if p)
            bits.append(f'{flag(r.get("country"))} {E(place)}' if r.get("country") else E(place))
        if speakers:
            bits.append(f'{E(t("talks_speakers"))}: {E(", ".join(speakers))}')
        if duration:
            bits.append(f'{E(t("talks_duration"))}: {E(duration)}')
        if r.get("language"):
            bits.append(f'{E(t("talks_language"))}: {E(_talk_lang_label(r.get("language")))}')
        meta = " · ".join(bits)
        if embed:
            host = "youtube-nocookie.com" if r.get("platform") == "youtube" else ("player.vimeo.com" if r.get("platform") == "vimeo" else "")
            media = (f'<button type="button" class="talk-play" data-embed="{E(embed)}">{E(t("talks_play"))}</button>'
                     f'<p class="meta">{E(t("talks_embed_note"))}</p>')
        else:
            media = (f'<p><a href="{E(r.get("video_url"))}" rel="noopener" target="_blank">{E(t("talks_watch"))}</a></p>'
                     f'<p class="meta">{E(t("talks_not_embed"))}</p>')
        extra = []
        if r.get("event_name"):
            if r.get("event_url"):
                extra.append(f'{E(t("talks_event"))}: <a href="{E(r["event_url"])}" rel="noopener" target="_blank">{E(r["event_name"])}</a>')
            else:
                extra.append(f'{E(t("talks_event"))}: {E(r["event_name"])}')
        if r.get("calendar_event_id"):
            extra.append(f'<a href="../calendar/#e-{E(r["calendar_event_id"])}">{E(t("talks_calendar"))}</a>')
        if r.get("channel"):
            extra.append(f'{E(t("talks_channel"))}: {E(r["channel"])}')
        if published:
            extra.append(f'{E(t("talks_published"))}: <time datetime="{E(r.get("published"))}">{E(published)}</time>')
        if r.get("source_url"):
            extra.append(f'{E(t("talks_source"))}: <a href="{E(r["source_url"])}" rel="noopener" target="_blank">{E(r["source_url"])}</a>')
        year = (r.get("date") or r.get("published") or "")[:4]
        return (f'<article id="{E(r["id"])}" data-c="{E(r.get("country") or "")}" data-y="{E(year)}" data-l="{E(r.get("language") or "")}">'
                f'<h2><a href="{E(r.get("video_url"))}" rel="noopener" target="_blank">{E(r.get("title") or "")}</a></h2>'
                f'<p class="meta">{meta}</p>{media}'
                + (f'<p class="sum">{E(r.get("description") or "")}</p>' if r.get("description") else "")
                + (f'<p class="meta">{" · ".join(extra)}</p>' if extra else "")
                + '</article>')
    body = f"""<div class="talks"><h1>{E(t("talks_h1"))}</h1>
<p class="lead">{E(t("talks_lead"))}</p>
<div class="filters" role="group" aria-label="{E(t("filters"))}">
<span class="lbl">{E(t("country"))}</span><div class="chips">{chips(TALK_COUNTRIES)}</div>
<label for="talk-year">{E(t("talks_year"))}</label> <select id="talk-year">{year_opts}</select>
<span class="lbl">{E(t("talks_language"))}</span><div class="chips">{lang_chips}</div>
<span id="talk-count" class="meta" aria-live="polite"></span>
</div>
<div id="talk-list">{''.join(article(r) for r in rows) or f'<p class="empty">{E(t("talks_none"))}</p>'}</div>
</div>"""
    js = r"""<script>(function(){var N=%s,arts=[].slice.call(document.querySelectorAll('#talk-list article')),cc=[].slice.call(document.querySelectorAll('.tcountry')),lc=[].slice.call(document.querySelectorAll('.tlang')),year=document.getElementById('talk-year'),cnt=document.getElementById('talk-count');
function on(list,key){return list.filter(function(b){return b.getAttribute('aria-pressed')==='true'}).map(function(b){return b.dataset[key]})}
function apply(push){var c=on(cc,'c'),l=on(lc,'l'),y=year.value,n=0;arts.forEach(function(a){var ok=(!c.length||c.indexOf(a.dataset.c)>=0)&&(!y||a.dataset.y===y)&&(!l.length||l.indexOf(a.dataset.l)>=0);a.hidden=!ok;if(ok)n++});cnt.textContent=N.replace('{n}',n);if(push){var p=new URLSearchParams();if(c.length)p.set('country',c.join(','));if(y)p.set('year',y);if(l.length)p.set('lang',l.join(','));history.replaceState(null,'',p.toString()?'#'+p:location.pathname)}}
var h=new URLSearchParams(location.hash.slice(1));(h.get('country')||'').split(',').forEach(function(x){cc.forEach(function(b){if(b.dataset.c===x)b.setAttribute('aria-pressed','true')})});
(h.get('lang')||'').split(',').forEach(function(x){lc.forEach(function(b){if((b.dataset.l||'')===x)b.setAttribute('aria-pressed','true')})});
if(h.get('year'))year.value=h.get('year');
cc.concat(lc).forEach(function(b){b.addEventListener('click',function(){b.setAttribute('aria-pressed',b.getAttribute('aria-pressed')==='true'?'false':'true');apply(1)})});
year.addEventListener('change',function(){apply(1)});
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('.talk-play');if(!b)return;var src=b.getAttribute('data-embed');if(!src)return;var f=document.createElement('iframe');f.src=src;f.title=b.textContent||'';f.setAttribute('allow','accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share');f.setAttribute('allowfullscreen','');f.setAttribute('referrerpolicy','strict-origin-when-cross-origin');b.replaceWith(f)});
apply(0)})();</script>""" % json.dumps(t("talks_n", n="{n}"))
    page("talks", t("talks_title"), "talks", body, t("talks_desc"), js)
    if LANG == "en":
        print(f"talks: {len(rows)}")

def build_calendar(ctx):
    evs, now = ctx["events"]
    up = [e for e in evs if not e["past"]]; past = [e for e in evs if e["past"] and e.get("status") == "published"][::-1]  # all finished, newest first
    def when(e):
        a = dt.datetime.fromisoformat(e["start"]); b = dt.datetime.fromisoformat(e["end"]) if e.get("end") else None
        # Weekday names exist for the Nordic languages. The wider set uses English until translated.
        # A listing that only publishes calendar days is stored as 00:00–23:59 local. Show the dates, not a clock.
        date_only = a.hour == 0 and a.minute == 0 and (b is None or (b.hour, b.minute) in ((0, 0), (23, 59)))
        if date_only:
            s = f'{i18n.WD.get(LANG, i18n.WD["en"])[a.weekday()]} {i18n.short_date(LANG, a)}'
            if b and b.date() != a.date(): s += f' – {i18n.short_dm(LANG, b)}'
        else:
            s = f'{i18n.WD.get(LANG, i18n.WD["en"])[a.weekday()]} {i18n.short_date(LANG, a)}, {i18n.hm(LANG, a)}'
            s += (f'–{i18n.hm_end(LANG, b)}' if b and b.date() == a.date() else (f' – {i18n.short_dm(LANG, b)}' if b else ""))
        c = e.get("country")
        return s + f' ({t("time_local", city=t("city_" + c)) if c in COUNTRY_CODES else t("city_local")})'
    def badges(e):
        b = []
        if e.get("status") == "owner": b.append(f'<span class="tag pend">{E(t("owner"))}</span>')
        elif e.get("status") != "published": b.append(f'<span class="tag pend">{E(t("pending"))}</span>')
        if e.get("paid"): b.append(f'<span class="tag paid">{E(t("paid"))}</span>')
        elif e.get("paid") is False: b.append(f'<span class="tag">{E(t("free"))}</span>')
        if e.get("sponsored"): b.append('<span class="tag paid">' + (E(t("sponsored_by", x=e["sponsored"])) if isinstance(e["sponsored"], str) else E(t("sponsored"))) + '</span>')
        if e.get("online"): b.append(f'<span class="tag">{E(t("online"))}</span>')
        return " ".join(b)
    def li(e):
        # event titles: English pages keep the editor's English title (+ original); other languages show the organiser's original title
        ttl = e["title"] if LANG == "en" or not e.get("title_orig") else e["title_orig"]
        note, nl = L18(e, "note")
        return (f'<li id="e-{E(e["id"])}" data-c="{E(e.get("country"))}"><h3><a href="{E(e["url"])}" rel="noopener" target="_blank">{E(ttl)}</a></h3>'
                f'<div class="meta">{flag(e.get("country"))} <time datetime="{E(e["start"])}"><b>{E(when(e))}</b></time> · {E(e.get("place") or t("online"))}{(", " + E(e["city"])) if e.get("city") and e["city"] not in (e.get("place") or "") else ""} {badges(e)}</div>'
                + (f'<p class="orig">{E(t("orig_title_ev"))}{E(e["title_orig"])}</p>' if e.get("title_orig") and LANG == "en" else "") + f'<div class="meta">{E(t("organiser"))}: {E(e["organiser"])} · {E(t("listed_at"))}: <a href="{E(e["url"])}" rel="noopener" target="_blank">{E(e["source"])}</a></div>'
                + (f'<p class="sum"{lang_attr(nl)}><b>{E(t("note"))}:</b> {E(note)}</p>' if note else "") + '</li>')
    loc = lambda e: dt.datetime.fromisoformat(e["start"])
    months = sorted({(now.year, now.month)} | {(loc(e).year, loc(e).month) for e in up})[:6]
    grids = []
    for y, m in months:
        cells = []
        for wk in calendar.Calendar(0).monthdatescalendar(y, m):
            row = []
            for d in wk:
                de = [e for e in up if loc(e).date() == d]
                cls = " ".join(c for c in ["out" if d.month != m else "", "today" if d == now.astimezone(OSLO).date() else "", "has" if de else ""] if c)
                row.append(f'<td class="{cls}"><span class="d">{d.day}</span>' + "".join(f'<a href="#e-{E(e["id"])}" data-c="{E(e.get("country"))}" title="{E(cname(e.get("country")))}: {E(e["title"] if LANG == "en" else e.get("title_orig") or e["title"])}">{flag(e.get("country"))}<span>{E(e["title"] if LANG == "en" else e.get("title_orig") or e["title"])}</span></a>' for e in de) + '</td>')
            cells.append("<tr>" + "".join(row) + "</tr>")
        grids.append(f'<table class="cal"><caption>{E(i18n.month_caption(LANG, y, m))}</caption><thead><tr>{"".join(f"<th>{E(d)}</th>" for d in i18n.wd_head(LANG))}</tr></thead><tbody>{"".join(cells)}</tbody></table>')
    per_c = {c: sum(e.get("country") == c for e in up) for c in COUNTRY_CODES}
    npend = sum(e.get("status") == "pending" for e in up); nown = sum(e.get("status") == "owner" for e in up)
    body = f"""<h1>{E(t("cal_h1"))}</h1>
<p class="lead">{E(t("cal_lead"))}</p>
{f'<p class="notice warn">{t("cal_preview", p=npend, n=len(up), o=nown)}</p>' if PREVIEW and (npend or nown) else ''}
<div class="filters" role="group" aria-label="{E(t("countries_aria"))}"><span class="lbl">{E(t("country"))}</span><div class="chips">{country_chips()}</div><span id="ecount" class="meta" aria-live="polite"></span></div>
<p class="meta">{" · ".join(f"{flag(c)} {E(n)}: {per_c[c]}" for c, n in COUNTRIES.items())}</p>
<div class="calgrid">{''.join(grids)}</div>
<h2>{E(t("upcoming_h"))}</h2><ol class="news" id="evlist">{''.join(li(e) for e in up) or f'<li class="empty">{E(t("no_upcoming"))}</li>'}</ol>
<h2 id="past">{E(t("past_h"))}</h2><p class="meta">{E(t("past_note"))}</p><p class="meta">{t("past_talks", href="../talks/")}</p><ol class="news past">{''.join(li(e) for e in past) or f'<li class="empty">{E(t("no_past"))}</li>'}</ol>
<p class="meta">{t("cal_how")}</p>"""
    js = """<script>(function(){var NU=%s,cc=[].slice.call(document.querySelectorAll('.cchip')),n=[].slice.call(document.querySelectorAll('#evlist li[data-c], .calgrid a[data-c], ol.past li[data-c]')),cnt=document.getElementById('ecount');
function apply(){var c=cc.filter(function(x){return x.getAttribute('aria-pressed')==='true'}).map(function(x){return x.dataset.c}),k=0;n.forEach(function(el){var ok=!c.length||c.indexOf(el.dataset.c)>=0;el.hidden=!ok;if(ok&&el.parentNode.id==='evlist')k++});cnt.textContent=NU.replace('{n}',k);history.replaceState(null,'',c.length?'#country='+c.join(','):location.pathname)}
var h=new URLSearchParams(location.hash.slice(1));(h.get('country')||'').split(',').forEach(function(x){cc.forEach(function(b){if(b.dataset.c===x)b.setAttribute('aria-pressed','true')})});
cc.forEach(function(b){b.addEventListener('click',function(){b.setAttribute('aria-pressed',b.getAttribute('aria-pressed')==='true'?'false':'true');apply()})});apply()})();</script>""" % json.dumps(t("n_upcoming", n="{n}"))
    page("calendar", t("cal_title"), "calendar", body, t("cal_desc"), js)
    if LANG == "en": print(f"calendar: {len(up)} upcoming {per_c}, {len(past)} past")

def build_academia():
    """Academia page from data/academia.json. Public build: only rows approved in queue/approved.json -> academia.approve
    (key = doi for publications, url for the rest). Preview: also rows awaiting the editor, clearly marked.
    Row texts (about, level, term) are data in English and are shown with lang="en" on the other language versions."""
    if LANG == "en":
        research = "/workspace/nordic-crypto-research/academia.md"
        if os.path.exists(research):
            subprocess.run([sys.executable, P("tools", "import_academia.py")], check=True)
        else:
            print("academia: research list is missing; leaving data/academia.json unchanged")
    ac = load(P("data", "academia.json"), {}) or {}
    def keep(rows, key):  # only editor-approved rows reach the page, in preview too; pending/unverified/out stay in data/
        return [dict(r) for r in rows if r.get("status") == "approved"]
    secs = {k: keep(ac.get(k, []), "doi" if k == "publications" else "url") for k in ("courses", "groups", "publications", "research")}
    if LANG == "en": json.dump(dict({"updated": ac.get("updated"), "preview": PREVIEW}, **secs), open(os.path.join(SITE, "data", "academia.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    en = lang_attr("en")
    def st(r): return (f'<span class="tag pend">{E(t("owner"))}</span>' if PREVIEW else "")
    def dom(u): return re.sub(r"^https?://(www[0-9]?\.)?", "", u).split("/")[0]
    def foot(r):
        return f'<div class="meta">{E(t("ac_source"))}: <a href="{E(r["source"])}" rel="noopener" target="_blank">{E(dom(r["source"]))}</a> · {E(t("ac_checked", d=r["checked"]))} {st(r)}</div>'
    tr = load(P("data", "academia_i18n.json"), {}) or {}   # optional translations of research 'about' / group 'activity' texts, keyed by url
    def about(r, k="about"):
        x = (tr.get(r["url"]) or {}).get(LANG) if LANG != "en" else None
        return f'<p class="sum">{E(x)}</p>' if x else f'<p class="sum"{en}>{E(" ".join(v for v in (r.get("about"), r.get("activity")) if v) if k == "group" else r["about"])}</p>'
    def row(c, inner): return f'<li data-c="{E(c)}">{inner}</li>'
    def bycountry(rows, fn):
        if not rows: return f'<p class="empty">{E(t("ac_empty"))}</p>'
        return '<ol class="news">' + "".join(row(r["country"], fn(r)) for c in COUNTRY_CODES for r in rows if r["country"] == c) + '</ol>'
    courses = bycountry(secs["courses"], lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["code"])} {E(r["name"])}</a></h3>'
        f'<div class="meta">{flag(r["country"])} <b>{E(r["institution"])}</b> · <span{en}>{E(r["level"])}</span>' + (f' · <b{en}>{E(r["term"])}</b>' if r.get("term") else "") + f'</div><p class="sum"{en}>{E(r["about"])}</p>{foot(r)}')
    groups = bycountry(secs["groups"], lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["name"])}</a> '
        f'<span class="tag {"act" if r["active"] else "inact"}">{E(t("active") if r["active"] else t("inactive"))}</span></h3>'
        f'<div class="meta">{flag(r["country"])} <b>{E(r["institution"])}</b></div>{about(r, "group")}{foot(r)}')
    def au(a):
        a = a or []
        return (", ".join(a[:4]) + (t("et_al") if len(a) > 4 else "")) if a else ""
    def pub_type(r):
        return {"master": "Master's thesis", "phd": "PhD dissertation", "paper": "Paper", "conference": "Conference"}.get(r.get("type") or "paper", r.get("type") or "Paper")
    def pub_meta(r):
        bits = [flag(r["country"])]
        authors = au(r.get("authors"))
        if authors: bits.append(E(authors))
        if r.get("year"): bits.append(f'({E(r["year"])})')
        bits.append(f'<span class="tag">{E(pub_type(r))}</span>')
        if r.get("venue"): bits.append(f'<i>{E(r["venue"])}</i>')
        if r.get("institution"): bits.append(E(r["institution"]))
        return " · ".join(bits)
    def pub_ids(r):
        parts = []
        if r.get("doi"):
            parts.append(f'DOI: <a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["doi"])}</a>')
        db = r.get("db") or r.get("url")
        if db:
            parts.append(f'<a href="{E(db)}" rel="noopener" target="_blank">{E(t("ac_record", db=r.get("db_name") or t("database")))}</a>')
        if r.get("about"):
            parts.append(f'<span{en}>{E(r["about"])}</span>')
        return " · ".join(parts)
    pubs = bycountry(sorted(secs["publications"], key=lambda r: (-(r.get("year") or 0), r.get("title") or "")),
        lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["title"])}</a></h3>'
        f'<div class="meta">{pub_meta(r)}</div>'
        f'<div class="meta">{pub_ids(r)}</div>{foot(r)}')
    research = bycountry(secs["research"], lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["name"])}</a></h3>'
        f'<div class="meta">{flag(r["country"])} <b>{E(r["institution"])}</b></div>{about(r)}{foot(r)}')
    allrows = sum(len(v) for v in secs.values())
    per_c = {c: sum(r["country"] == c for v in secs.values() for r in v) for c in COUNTRY_CODES}
    dn = t("data_en_note")
    body = f"""<h1>{E(t("ac_h1"))}</h1>
<p class="lead">{E(t("ac_lead"))}</p>
{f'<p class="notice warn">{t("ac_preview", n=allrows)}</p>' if PREVIEW else ''}
{f'<p class="meta">{E(dn)}</p>' if dn else ''}
<div class="filters" role="group" aria-label="{E(t("countries_aria"))}"><span class="lbl">{E(t("country"))}</span><div class="chips">{country_chips()}</div><span id="acount" class="meta" aria-live="polite"></span></div>
<p class="meta">{" · ".join(f"{flag(c)} {E(n)}: {per_c[c]}" for c, n in COUNTRIES.items())} · <a href="#courses">{E(t("ac_courses"))}</a> · <a href="#groups">{E(t("ac_groups"))}</a> · <a href="#publications">{E(t("ac_pubs"))}</a> · <a href="#research">{E(t("ac_research"))}</a></p>
<h2 id="courses">{E(t("ac_courses_h"))}</h2><p class="meta">{E(t("ac_courses_m"))}</p>{courses}
<h2 id="groups">{E(t("ac_groups_h"))}</h2><p class="meta">{E(t("ac_groups_m"))}</p>{groups}
<h2 id="publications">{E(t("ac_pubs_h"))}</h2><p class="meta">{E(t("ac_pubs_m"))}</p>{pubs}
<h2 id="research">{E(t("ac_research_h"))}</h2>{research}
<p class="notice">{t("ac_notice")}</p>"""
    js = """<script>(function(){var NR=%s,cc=[].slice.call(document.querySelectorAll('.cchip')),n=[].slice.call(document.querySelectorAll('ol.news li[data-c]')),cnt=document.getElementById('acount');
function apply(){var c=cc.filter(function(x){return x.getAttribute('aria-pressed')==='true'}).map(function(x){return x.dataset.c}),k=0;n.forEach(function(el){var ok=!c.length||c.indexOf(el.dataset.c)>=0;el.hidden=!ok;if(ok)k++});cnt.textContent=NR.replace('{n}',k);history.replaceState(null,'',c.length?'#country='+c.join(','):location.pathname+location.hash.replace(/#country=.*/,''))}
var h=new URLSearchParams(location.hash.slice(1));(h.get('country')||'').split(',').forEach(function(x){cc.forEach(function(b){if(b.dataset.c===x)b.setAttribute('aria-pressed','true')})});
cc.forEach(function(b){b.addEventListener('click',function(){b.setAttribute('aria-pressed',b.getAttribute('aria-pressed')==='true'?'false':'true');apply()})});apply()})();</script>""" % json.dumps(t("n_rows", n="{n}"))
    page("academia", t("ac_title"), "academia", body, t("ac_desc"), js)
    if LANG == "en": print(f"academia: {allrows} editor-approved rows shown {per_c}")

TIP_FORM = "https://github.com/jQrgen/nordic-crypto/issues/new?template=tip.yml"
COL_FORM = "https://github.com/jQrgen/nordic-crypto/issues/new?template=columnist.yml"
def tip_endpoint():
    """Fixed public tip endpoint (e.g. https://tips.<domain>): env TIP_ENDPOINT or tipserver/config.json -> public_endpoint.
    Takes precedence and is baked into /tip/. Without it, /tip/ reads the current quick-tunnel URL at runtime from
    /tip-endpoint.json (written by tipserver/publish_endpoint.sh whenever the tunnel URL changes)."""
    e = os.environ.get("TIP_ENDPOINT") or (load(P("tipserver", "config.json"), {}) or {}).get("public_endpoint")
    return (e or "").strip().rstrip("/") or None

def tip_page_uses_server():
    """/tip/ posts to the box tip server (quick tunnel) only when tipserver/config.json has tip_page_uses_server: true
    (set after jQrgen approves the page) or env TIP_PAGE_SERVER=1 (local preview build). Otherwise the GitHub issue form."""
    return bool(os.environ.get("TIP_PAGE_SERVER") == "1" or (load(P("tipserver", "config.json"), {}) or {}).get("tip_page_uses_server"))

def write_tip_endpoint_file():
    """site/tip-endpoint.json, so a full publish (which replaces gh-pages with site/) keeps the current endpoint."""
    sys.path.insert(0, P("tipserver")); import endpoint as _ep
    ep, kind = (tip_endpoint(), "fixed") if tip_endpoint() else (_ep.current() if tip_page_uses_server() else ("", None))
    old = load(P(".publish", "tip-endpoint.json"), {}) or {}
    upd = old.get("updated") if old.get("endpoint") == ep else dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    json.dump({"endpoint": ep or None, "kind": kind, "updated": upd}, open(os.path.join(SITE, "tip-endpoint.json"), "w"), indent=1)
    open(os.path.join(SITE, "tip-endpoint.json"), "a").write("\n")

TIP_ERRORS = {"Please enter the article URL.": "tip_js_e_url", "The URL must be a full http:// or https:// link.": "tip_js_e_badurl",
              "Too many tips from you in a short time. Please try again later.": "tip_js_e_rate", "The tip is too long (max 4 KB).": "tip_js_e_long"}
def build_tip_server(ep):
    """'Send a tip' page that posts to our own tip intake: the Cloudflare Worker in tipworker/ (public_endpoint, set by
    tipworker/deploy.sh) or the box server tipserver/server.py. Inline JS only, no third-party scripts.
    Endpoint: the fixed `ep` if set, else read at runtime from <root>/tip-endpoint.json (no cache). If the server can't be
    reached, the page says so and offers the public GitHub issue form as a fallback."""
    opts = f'<option value="unsure">{E(t("tip_unsure"))}</option>' + "".join(f'<option value="{c}">{E(n)}</option>' for c, n in COUNTRIES.items())
    body = f"""<h1>{E(t("tip_title"))}</h1>
<p class="lead">{E(t("tip_lead"))}</p>
<div class="prose">
<p>{t("tip_srv_p")}</p>
<p class="notice">{t("tip_srv_priv")}</p>
</div>
<div id="tipmsg" role="status" aria-live="polite"></div>
<noscript><p class="notice warn">{t("tip_noscript", gh=TIP_FORM)}</p></noscript>
<form id="tipform" class="tipform"><fieldset id="tipfs" disabled style="border:0;padding:0;margin:0">
<p><label for="t-url"><b>{E(t("tip_url"))}</b> {E(t("tip_required"))}</label><br><input id="t-url" name="url" type="url" required maxlength="2000" placeholder="https://" style="width:100%;max-width:560px;padding:6px"></p>
<p><label for="t-country"><b>{E(t("tip_country"))}</b></label><br><select id="t-country" name="country" style="padding:6px">{opts}</select></p>
<p><label for="t-note"><b>{E(t("tip_note"))}</b> {E(t("tip_note_opt"))}</label><br><textarea id="t-note" name="note" rows="3" maxlength="1000" style="width:100%;max-width:560px;padding:6px"></textarea></p>
<p><label for="t-name"><b>{E(t("tip_name"))}</b> {E(t("tip_name_opt"))}</label><br><input id="t-name" name="name" maxlength="100" autocomplete="off" style="width:100%;max-width:320px;padding:6px"></p>
<p style="position:absolute;left:-9999px" aria-hidden="true"><label for="t-website">{E(t("tip_honeypot"))}</label><input id="t-website" name="website" tabindex="-1" autocomplete="off"></p>
<p><button type="submit" style="padding:8px 14px;font-size:15px">{E(t("tip_send"))}</button></p>
</fieldset></form>"""
    msgs = {"off": t("tip_js_off", gh=TIP_FORM), "thanks": t("tip_js_thanks"), "fail": t("tip_js_fail"), "err": {k: t(v) for k, v in TIP_ERRORS.items()}}
    js = """<script>(function(){var FIXED=%s,EPF=%s,M=%s,f=document.getElementById('tipform'),fs=document.getElementById('tipfs'),m=document.getElementById('tipmsg'),b=f.querySelector('button');
function say(t,cls,html){m.className='notice'+(cls?' '+cls:'');if(html)m.innerHTML=t;else m.textContent=t}
function off(){say(M.off,'warn',true)}
function tmo(p,ms){var ac=new AbortController(),t=setTimeout(function(){ac.abort()},ms);return {s:ac.signal,done:function(){clearTimeout(t)}}}
function ep(){if(FIXED)return Promise.resolve(FIXED);return fetch(EPF+'?t='+Date.now(),{cache:'no-store',credentials:'omit'}).then(function(r){return r.ok?r.json():{}}).then(function(j){return (j&&typeof j.endpoint==='string'&&/^https:\\/\\/[^\\s\\/]+$/.test(j.endpoint))?j.endpoint:null}).catch(function(){return null})}
fs.disabled=false;
ep().then(function(e){if(!e)return off();var t=tmo(0,8000);fetch(e+'/api/health',{cache:'no-store',credentials:'omit',signal:t.s}).then(function(r){t.done();if(!r.ok)off()}).catch(function(){t.done();off()})});
f.addEventListener('submit',function(ev){ev.preventDefault();if(!f.reportValidity())return;b.disabled=true;
 var d={url:f.url.value,country:f.country.value,note:f.note.value,name:f.name.value,website:f.website.value};
 ep().then(function(e){if(!e)throw 0;var t=tmo(0,12000);
  return fetch(e+'/api/tip',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(d),signal:t.s,credentials:'omit',referrerPolicy:'no-referrer'})
  .then(function(r){t.done();return r.json().catch(function(){return {}}).then(function(j){return {s:r.status,j:j}})})})
 .then(function(x){b.disabled=false;
  if(x.s>=200&&x.s<300&&x.j.ok){f.reset();say(M.thanks)}
  else if(x.s>=500)off(); else {var er=x.j&&x.j.error;say((er&&M.err[er])||er||M.fail,'warn')}})
 .catch(function(){b.disabled=false;off()})})})();</script>""" % (json.dumps(ep), json.dumps(up1() + "tip-endpoint.json"), json.dumps(msgs, ensure_ascii=False))
    page("tip", t("tip_title"), "tip", body, t("tip_desc"), js)

def build_tip():
    """'Send a tip' page. Static: a plain HTML form (GET, no JavaScript, no tracking) that opens the prefilled GitHub issue form
    (.github/ISSUE_TEMPLATE/tip.yml, label 'tip'). There is no public e-mail address, so GitHub is the only channel.
    routines/nightly-fetch.sh -> tools/reader_tips.py puts open tips in the editor queue as pending; nothing is auto-published.

    TODO (jQrgen): disable this public GitHub issue form and the GitHub fallback in build_tip_server. Tips should go
    only to the private Cloudflare intake (tipworker/). Do not switch the page until that intake is the live path."""
    if LANG == "en": write_tip_endpoint_file()
    if tip_endpoint() or tip_page_uses_server(): return build_tip_server(tip_endpoint())  # GitHub issue form only as fallback link
    # the option values stay English: they fill in the GitHub issue form (tip.yml), which tools/reader_tips.py parses
    opts = f'<option value="Not sure">{E(t("tip_unsure"))}</option>' + "".join(f'<option value="{E(t_en)} ({c})">{E(t("c_" + c))}</option>' for c, t_en in ((c, i18n.t("en", "c_" + c)) for c in COUNTRY_CODES))
    body = f"""<h1>{E(t("tip_title"))}</h1>
<p class="lead">{E(t("tip_lead"))}</p>
<div class="prose">
<p>{t("tip_gh_p")}</p>
<p class="notice warn">{t("tip_gh_priv")}</p>
</div>
<form class="tipform" method="get" action="https://github.com/jQrgen/nordic-crypto/issues/new">
<input type="hidden" name="template" value="tip.yml">
<p><label for="t-url"><b>{E(t("tip_url"))}</b> {E(t("tip_required"))}</label><br><input id="t-url" name="url" type="url" required placeholder="https://" style="width:100%;max-width:560px;padding:6px"></p>
<p><label for="t-country"><b>{E(t("tip_country"))}</b></label><br><select id="t-country" name="country" style="padding:6px">{opts}</select></p>
<p><label for="t-note"><b>{E(t("tip_note"))}</b> {E(t("tip_note_opt_gh"))}</label><br><textarea id="t-note" name="note" rows="3" style="width:100%;max-width:560px;padding:6px"></textarea></p>
<p><button type="submit" style="padding:8px 14px;font-size:15px">{E(t("tip_gh_btn"))}</button></p>
<p class="meta">{E(t("tip_gh_meta"))}</p>
</form>
<p class="prose">{t("tip_gh_direct", gh=TIP_FORM)}</p>"""
    page("tip", t("tip_title"), "tip", body, t("tip_desc"))

def build_columnist():
    """'Apply as a columnist' page. Same privacy pattern as the static tip page: a plain HTML form (GET, no JavaScript,
    no tracking) that opens a prefilled public GitHub issue (.github/ISSUE_TEMPLATE/columnist.yml). Nothing is stored
    on this site. The editor reviews every pitch; publication is not guaranteed."""
    body = f"""<h1>{E(t("col_title"))}</h1>
<p class="lead">{E(t("col_lead"))}</p>
<div class="prose">
<p>{t("col_p")}</p>
<p class="notice warn">{t("col_priv")}</p>
</div>
<form class="tipform" method="get" action="https://github.com/jQrgen/nordic-crypto/issues/new">
<input type="hidden" name="template" value="columnist.yml">
<p><label for="c-name"><b>{E(t("col_name"))}</b> {E(t("col_name_opt"))}</label><br><input id="c-name" name="name" maxlength="80" autocomplete="name" style="width:100%;max-width:560px;padding:6px"></p>
<p><label for="c-contact"><b>{E(t("col_contact"))}</b> {E(t("tip_required"))}</label><br><input id="c-contact" name="contact" required maxlength="120" autocomplete="email" style="width:100%;max-width:560px;padding:6px"><br><span class="meta">{E(t("col_contact_help"))}</span></p>
<p><label for="c-langs"><b>{E(t("col_langs"))}</b> {E(t("tip_required"))}</label><br><input id="c-langs" name="languages" required maxlength="120" style="width:100%;max-width:560px;padding:6px"><br><span class="meta">{E(t("col_langs_help"))}</span></p>
<p><label for="c-pitch"><b>{E(t("col_pitch"))}</b> {E(t("tip_required"))}</label><br><textarea id="c-pitch" name="pitch" required rows="5" maxlength="1500" style="width:100%;max-width:560px;padding:6px"></textarea><br><span class="meta">{E(t("col_pitch_help"))}</span></p>
<p><label for="c-sample"><b>{E(t("col_sample"))}</b> {E(t("col_sample_opt"))}</label><br><input id="c-sample" name="sample" type="url" maxlength="300" placeholder="https://" style="width:100%;max-width:560px;padding:6px"></p>
<p><label for="c-why"><b>{E(t("col_why"))}</b> {E(t("tip_required"))}</label><br><textarea id="c-why" name="why" required rows="4" maxlength="800" style="width:100%;max-width:560px;padding:6px"></textarea><br><span class="meta">{E(t("col_why_help"))}</span></p>
<p><button type="submit" style="padding:8px 14px;font-size:15px">{E(t("col_btn"))}</button></p>
<p class="meta">{E(t("col_meta"))}</p>
</form>
<p class="prose">{t("col_direct", gh=COL_FORM)}</p>"""
    page("columnist", t("col_title"), "columnist", body, t("col_desc"))

def build_changelog():
    """Changelog page from changelog.json (site changes only, newest first). Entries dated "launch" use launch_date,
    which stays null until jQrgen approves publishing (publish.sh --yes sets it); until then they show as preview.
    Translations: entries[].i18n {lang: {title, description}}; missing ones are shown in English.
    Entries with "review": "pending" (and no date) only appear in the preview build, tagged as preview."""
    cl = load(P("changelog.json"), {"entries": []}); launch = cl.get("launch_date")
    rows = []
    for e in cl.get("entries", []):
        if e.get("review") == "pending" and not PREVIEW: continue   # not yet approved by the editor/jQrgen
        d = launch if e.get("date") == "launch" else e.get("date")
        rows.append(dict(e, date=d))
    rows.sort(key=lambda e: e["date"] or "9999-99-99", reverse=True)
    if LANG == "en":
        json.dump({"launch_date": launch, "entries": [{k: e.get(k) for k in ("id", "date", "title", "description", "i18n")} for e in rows]},
                  open(os.path.join(SITE, "data", "changelog.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    def when(d):
        if not d: return f'<span class="tag pend">{E(t("cl_prev_tag"))}</span>'
        x = dt.date.fromisoformat(d); return f'<time datetime="{d}"><b>{E(i18n.long_date(LANG, x))}</b></time>'
    def tr(e):
        x = (e.get("i18n") or {}).get(LANG) if LANG != "en" else None
        return (x["title"], x["description"], LANG) if x else (e["title"], e["description"], "en")
    lis = "".join(f'<li id="{E(e["id"])}"{lang_attr(l)}><h3>{E(ti)}</h3><div class="meta">{when(e["date"])}</div><p class="sum">{E(de)}</p></li>' for e in rows for ti, de, l in [tr(e)])
    body = f"""<h1>{E(t("cl_title"))}</h1>
<p class="lead">{E(t("cl_lead"))}</p>
{'' if launch else f'<p class="notice warn">{t("cl_preview")}</p>'}
<ol class="news">{lis or f'<li class="empty">{E(t("cl_none"))}</li>'}</ol>
<p class="meta">{E(t("cl_data"))}: <a href="{up1()}data/changelog.json">changelog.json</a>.</p>"""
    page("changelog", t("cl_title"), "changelog", body, t("cl_desc"))
    if LANG == "en": print(f"changelog: {len(rows)} entries, launch date {launch or 'not set (preview)'}")

def build_rules(ctx):
    """'How the rules are made' (rules/): see tools/rules_page.py (data: rules.json, editor-reviewed)."""
    sys.path.insert(0, P("tools"))
    try: import rules_page
    except ImportError: return
    rules_page.build(sys.modules[__name__], ctx)

def build_regulation_videos(ctx):
    """Country explainer slots (regulation-videos/): see tools/regulation_videos.py."""
    sys.path.insert(0, P("tools"))
    try: import regulation_videos
    except ImportError: return
    regulation_videos.build(sys.modules[__name__], ctx)

if __name__ == "__main__": build()
