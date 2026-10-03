#!/usr/bin/env python3
"""Builds the static site in site/ from data/news.json, data/events.json, data/orgchart.json and sources.json.
  .venv/bin/python build.py            # public build: ONLY editor-approved content (what publish.sh would push)
  .venv/bin/python build.py --preview  # local review build: also shows pending items, clearly marked "Pending editor review"
All paths are relative, so the site works at https://jqrgen.github.io/nordic-crypto/ and on a local server.
No tracking, no third-party scripts, no external fonts. Everything is in English."""
import json, os, re, shutil, subprocess, html, sys, calendar, datetime as dt
from zoneinfo import ZoneInfo
ROOT = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(ROOT, *a)
BASE = "https://jqrgen.github.io/nordic-crypto/"
SITE = P("site")
PREVIEW = "--preview" in sys.argv
SITE_NAME = "Nordic Crypto"
def load(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
def snippets(url, title):
    try: return json.loads(subprocess.check_output(["node", P("tools", "snippets.js"), url, title]))
    except Exception: return {"top": "", "bar": "", "css": "", "script": ""}
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
OSLO = ZoneInfo("Europe/Oslo")
def endate(iso):
    d = dt.datetime.fromisoformat(iso).astimezone(OSLO); return f"{d.day} {MON[d.month-1]} {d.year}"
COUNTRIES = {"NO": "Norway", "SE": "Sweden", "FI": "Finland", "IS": "Iceland"}
EXTRA_C = {"NORDIC": "Nordic-wide"}
CITYNAME = {"NO": "Oslo", "SE": "Stockholm", "FI": "Helsinki", "IS": "Reykjavík"}
# small inline SVG flags (Nordic crosses) – no emoji fonts or external images needed
_FL = {"NO": ("#BA0C2F", "#fff", "#00205B"), "SE": ("#006AA7", "#FECC00", None), "FI": ("#fff", "#002F6C", None),
       "IS": ("#02529C", "#fff", "#DC1E35")}
def flag(c, big=False):
    if c not in _FL:
        return f'<span class="cc" title="{E(EXTRA_C.get(c, c))}">{E("Nordic" if c == "NORDIC" else c)}</span>'
    bg, a, b = _FL[c]; w, h = (22, 16)
    inner = f'<rect x="7" width="2" height="16" fill="{b}"/><rect y="7" width="22" height="2" fill="{b}"/>' if b else ""
    border = ' stroke="#9ca3af" stroke-width=".6"' if bg == "#fff" else ""
    return (f'<svg class="flag" viewBox="0 0 22 16" width="{w*(1.4 if big else 1):.0f}" height="{h*(1.4 if big else 1):.0f}" role="img" aria-label="{COUNTRIES[c]}">'
            f'<title>{COUNTRIES[c]}</title><rect width="22" height="16" fill="{bg}"{border}/><rect x="6" width="4" height="16" fill="{a}"/><rect y="6" width="22" height="4" fill="{a}"/>{inner}</svg>')
def cname(c): return COUNTRIES.get(c) or EXTRA_C.get(c, c)
FLAGS_JS = json.dumps({c: flag(c) for c in list(COUNTRIES) + ["NORDIC"]})

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
ol.news{list-style:none;margin:0;padding:0}
ol.news li{padding:14px 0;border-bottom:1px solid var(--line)}
ol.news h3{font-size:18px;line-height:1.3;margin:0 0 4px}ol.news h3 a{text-decoration:none}ol.news h3 a:hover{text-decoration:underline}
.orig{font-size:13.5px;color:var(--muted);margin:0 0 3px}
.meta{font-size:13.5px;color:var(--muted)}.meta b{color:var(--ink);font-weight:600}
.tag{display:inline-block;font-size:12px;padding:0 6px;border:1px solid var(--line);margin-left:4px;color:var(--muted)}
.tag.pend{border-color:var(--warm);color:var(--warm);font-weight:600}.tag.paid{border-color:var(--warm);color:var(--warm)}
.sum{margin:6px 0 0;max-width:75ch}.sum.pend{color:var(--warm);font-style:italic}
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
.credit{font-size:12px;color:var(--muted)}
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

NAV = [("", "News"), ("calendar", "Calendar"), ("org-chart", "Who's who"), ("academia", "Academia"), ("sources", "Sources"), ("about", "About")]
def page(slug, title, nav, body, desc, extra_script=""):
    url = BASE + (slug + "/" if slug else "")
    s = snippets(url, f"{title} – {SITE_NAME}" if slug else f"{SITE_NAME} – Nordic crypto news")
    rel = "../" * (slug.count("/") + 1) if slug else "./"
    nav_html = "".join(f'<a href="{rel}{n + "/" if n else ""}"{" aria-current=page" if n == nav else ""}>{E(t)}</a>' for n, t in NAV)
    banner = (f'<div class="preview" role="note"><div class="wrap"><b>Local preview – not published.</b> Everything marked “Pending editor review” '
              f'has not been checked by the editor yet; summaries are not written yet. Only approved items go into the public build.</div></div>') if PREVIEW else ""
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}{" – " + SITE_NAME if slug else ""}</title>
<meta name="description" content="{E(desc)}"><link rel="canonical" href="{url}">{'<meta name="robots" content="noindex">' if PREVIEW else ''}
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{url}"><meta property="og:type" content="website"><meta property="og:locale" content="en_GB">
<meta name="referrer" content="strict-origin-when-cross-origin">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%230f5ea8'/%3E%3Crect x='4' width='3' height='16' fill='white'/%3E%3Crect y='6.5' width='16' height='3' fill='white'/%3E%3C/svg%3E">
<style>{CSS}{s['css']}</style></head>
<body>{banner}<header class="top"><div class="wrap"><a class="brand" href="{rel}">Nordic <span>Crypto</span></a><nav class="main" aria-label="Main menu">{nav_html}</nav></div></header>
<main class="wrap">
{body}
{s['top']}
</main>
<footer><div class="wrap">{SITE_NAME} covers Norway, Sweden, Finland and Iceland. Run by Jørgen S. Notland (jQrgen), Oslo, with AI assistance; summaries are written by an AI editor and jQrgen is the responsible person. Not investment advice. No tracking or cookies. <a href="{rel}about/">About, corrections and removal</a> · <a href="{rel}changelog/">Changelog</a>.</div></footer>
{s['script']}{extra_script}
</body></html>"""
    d = os.path.join(SITE, slug); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(doc)

def redirect(old, new):
    d = os.path.join(SITE, old); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url=../{new}/">'
        f'<link rel="canonical" href="{BASE}{new}/"><title>Moved</title></head><body><p>This page has moved to <a href="../{new}/">{new}</a>.</p></body></html>')

TOPIC_LABEL = {"bitcoin": "Bitcoin", "blockchain": "Blockchain", "crypto": "Crypto", "regulation": "Regulation", "companies": "Companies"}
def country_chips():
    return "".join(f'<button type="button" class="chip cchip" data-c="{c}" aria-pressed="false">{flag(c)}{E(n)}</button>' for c, n in COUNTRIES.items())

def build():
    subprocess.run([sys.executable, P("tools", "apply_approvals.py")], check=True)
    subprocess.run([sys.executable, P("tools", "import_orgchart.py")], check=True)
    news = load(P("data", "news.json"), {"items": []}); org = load(P("data", "orgchart.json"), {"entities": [], "relations": []})
    cfg = load(P("sources.json")); status = load(P("state", "source_status.json"), {})
    if os.path.exists(SITE): shutil.rmtree(SITE)
    os.makedirs(os.path.join(SITE, "data"))
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    if PREVIEW: open(os.path.join(SITE, ".preview"), "w").write("local preview build – never publish\n")
    approved = [i for i in news["items"] if i.get("status") == "published" and (i.get("summary") or "").strip()]
    pending = [i for i in news["items"] if i.get("status") == "pending"] if PREVIEW else []
    items = sorted(approved + pending + build_stories(), key=lambda i: i["published"], reverse=True)
    keys = ("id", "url", "title", "title_en", "source", "source_name", "country", "language", "published", "topics", "summary", "paywall", "links", "status", "own_story")
    pub_items = [{k: i.get(k) for k in keys if k in i} for i in items]
    for i in pub_items:
        if i.get("status") not in ("published", "owner"): i["summary"] = None; i["status"] = "pending"
    json.dump({"updated": news.get("updated"), "preview": PREVIEW, "items": pub_items}, open(os.path.join(SITE, "data", "news.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    ents = [e for e in org["entities"] if e.get("sources") and (e.get("status") == "published" or (PREVIEW and e.get("status") == "pending"))]
    eids = {e["id"] for e in ents}
    rels = [r for r in org["relations"] if r.get("sources") and r["from"] in eids and r["to"] in eids and (r.get("status") == "published" or (PREVIEW and r.get("status") == "pending"))]
    pub_org = {"updated": org.get("updated"), "preview": PREVIEW, "entities": ents, "relations": rels}
    json.dump(pub_org, open(os.path.join(SITE, "data", "orgchart.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for e in ents:  # images: only used ones with a free licence
        im = e.get("image")
        if im and im.get("file") and im.get("license"):
            dst = os.path.join(SITE, im["file"]); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(P(im["file"]), dst)

    # ---- News ----
    srcs = sorted({(i["source"], i["source_name"]) for i in items}, key=lambda x: x[1].lower())
    lis = []
    for i in items:
        pend = i.get("status") not in ("published", "owner"); own = i.get("status") == "owner"
        tags = "".join(f'<span class="tag">{E(TOPIC_LABEL.get(t, t.upper() if len(t) <= 4 else t.capitalize()))}</span>' for t in i["topics"])
        pw = ' · <span class="pw">may require a subscription</span>' if i.get("paywall") else ""
        head = i.get("title_en") or i["title"]
        orig = f'<p class="orig">Original title ({E(i.get("language") or "")}): {E(i["title"])}</p>' if i.get("title_en") else ""
        lang = f' · in {E(i["language"])}' if i.get("language") and i["language"] != "English" else ""
        summ = (f'<p class="sum pend">Pending editor review – an English summary has not been written yet. Read the story at the source.</p>' if pend
                else f'<p class="sum">{E(i["summary"])}</p>')
        lis.append(f'<li data-src="{E(i["source"])}" data-c="{E(i.get("country"))}" data-topics="{E(" ".join(i["topics"]))}">'
                   f'<h3><a href="{E(i["url"])}"{"" if i.get("own_story") else " rel=noopener target=_blank"}{" lang=" + chr(34) + {"Norwegian":"no","Swedish":"sv","Finnish":"fi","Icelandic":"is"}.get(i.get("language") or "", "en") + chr(34) if not i.get("title_en") else ""}>{E(head)}</a></h3>{orig}'
                   f'<div class="meta">{flag(i.get("country"))} {E(cname(i.get("country")))} · <b>{E(i["source_name"])}</b> · <time datetime="{E(i["published"])}">{endate(i["published"])}</time>{lang}{pw} {tags}'
                   + (' <span class="tag pend">Pending editor review</span>' if pend else "") + (' <span class="tag pend">Editor-approved · awaiting jQrgen\'s final approval</span>' if own else "")
                   + (' <span class="tag">Our story</span>' if i.get("own_story") else "") + f'</div>{summ}'
                   + "".join(f'<div class="meta">↳ <a href="{E(l["url"])}" rel="noopener" target="_blank">{E(l["label"])}</a></div>' for l in i.get("links", []) or []) + '</li>')
    opts = "".join(f'<option value="{E(k)}">{E(n)}</option>' for k, n in srcs)
    tchips = "".join(f'<button type="button" class="chip tchip" data-t="{k}" aria-pressed="false">{v}</button>' for k, v in TOPIC_LABEL.items())
    upd = endate(news["updated"]) if news.get("updated") else ""
    body = f"""<h1>Bitcoin, blockchain and crypto news from the Nordics</h1>
<p class="meta"><a href="screen/">Office screen mode (full screen, portrait or landscape) →</a></p>
<p class="lead">Links to stories from Norway, Sweden, Finland and Iceland – newspapers, broadcasters, regulators and central banks – each with a short English summary written by our editor. Read the full story at the source. Last updated {upd}. {len(items)} stories{f" ({len(pending)} pending editor review)" if pending else ""}.</p>
<div class="filters" role="group" aria-label="Filters"><span class="lbl">Country</span><div class="chips">{country_chips()}</div>
<label for="fsrc">Source</label><select id="fsrc"><option value="">All sources</option>{opts}</select>
<span class="lbl">Topic</span><div class="chips">{tchips}</div><span id="count" class="meta" aria-live="polite"></span></div>
<ol class="news" id="news">{''.join(lis) or '<li class="empty">No published stories yet.</li>'}</ol>
<p class="notice">Summaries are our own, written in English from the headline and the public teaser. We do not reproduce article text and we do not get around paywalls. Stories marked “may require a subscription” are from outlets with a paywall. Nothing here is investment advice.</p>"""
    js = """<script>
(function(){var sel=document.getElementById('fsrc'),tc=[].slice.call(document.querySelectorAll('.tchip')),cc=[].slice.call(document.querySelectorAll('.cchip')),lis=[].slice.call(document.querySelectorAll('#news li[data-src]')),cnt=document.getElementById('count');
function on(a,k){return a.filter(function(c){return c.getAttribute('aria-pressed')==='true'}).map(function(c){return c.dataset[k]})}
function apply(push){var s=sel.value,t=on(tc,'t'),c=on(cc,'c'),n=0;
lis.forEach(function(li){var ok=(!s||li.dataset.src===s)&&(!c.length||c.indexOf(li.dataset.c)>=0)&&(!t.length||t.some(function(x){return (' '+li.dataset.topics+' ').indexOf(' '+x+' ')>=0}));li.hidden=!ok;if(ok)n++});
cnt.textContent=n+' stories';if(push){var p=new URLSearchParams();if(c.length)p.set('country',c.join(','));if(s)p.set('source',s);if(t.length)p.set('topic',t.join(','));history.replaceState(null,'',p.toString()?'#'+p:location.pathname)}}
var p=new URLSearchParams(location.hash.slice(1));if(p.get('source'))sel.value=p.get('source');
(p.get('topic')||'').split(',').forEach(function(x){tc.forEach(function(c){if(c.dataset.t===x)c.setAttribute('aria-pressed','true')})});
(p.get('country')||'').split(',').forEach(function(x){cc.forEach(function(c){if(c.dataset.c===x)c.setAttribute('aria-pressed','true')})});
sel.addEventListener('change',function(){apply(1)});tc.concat(cc).forEach(function(c){c.addEventListener('click',function(){c.setAttribute('aria-pressed',c.getAttribute('aria-pressed')==='true'?'false':'true');apply(1)})});apply(0)})();
</script>"""
    page("", "Nordic Crypto – bitcoin, blockchain and crypto news from the Nordics", "", body,
         "Bitcoin, blockchain and crypto news from Norway, Sweden, Finland and Iceland, with English summaries, an events calendar and a who's who.", js)

    # ---- Org chart ----
    regs = []
    for r in org.get("regulation", []):
        regs.append(f'<article data-c="{E(r["country"])}"><h3>{flag(r["country"], True)}{E(cname(r["country"]))}</h3><dl><dt>MiCA</dt><dd>{E(r["mica"])}</dd><dt>Law</dt><dd>{E(r["law"])}</dd>'
                    f'<dt>Authorities</dt><dd>{E(r["regulator"])}</dd><dt>Status</dt><dd>{E(r["status"])}</dd></dl><p class="meta">Sources: '
                    + ", ".join(f'<a href="{E(s["url"])}" rel="noopener" target="_blank">{E(s["source_name"])}</a>' for s in r["sources"]) + '</p></article>')
    cnt_pub = sum(e["status"] == "published" for e in ents); cnt_pend = sum(e["status"] == "pending" for e in ents)
    body = f"""<h1>Who's who in Nordic crypto</h1>
<p class="lead">Regulators, central banks, tax authorities, financial intelligence units, ministries, MiCA-licensed providers, exchanges, issuers and associations in Norway, Sweden, Finland and Iceland – and people in public leadership roles. Every entry and every link between entries has a source. Click a card for details.</p>
{f'<p class="notice warn"><b>Preview:</b> {cnt_pend} of {len(ents)} entries are pending editor review.</p>' if PREVIEW and cnt_pend else ''}
<h2 id="regulation">Regulation by country</h2>
<div class="reg">{''.join(regs)}</div>
{('<details class="notice"><summary>Caveats</summary><ul>' + "".join(f"<li>{E(x)}</li>" for x in org.get("caveats", [])) + '</ul></details>') if org.get("caveats") else ''}
<h2 id="org">Organisation chart</h2>
<div class="filters"><span class="lbl">Country</span><div class="chips">{country_chips()}</div>
<div class="seg" role="group" aria-label="Sector"><button type="button" data-v="both" aria-pressed="true">Both</button><button type="button" data-v="private" aria-pressed="false">Private sector</button><button type="button" data-v="public" aria-pressed="false">Public sector</button></div>
<label for="osearch">Search</label><input type="search" id="osearch" placeholder="Name, role, organisation"></div>
<div id="chart" class="cols"><noscript>The chart needs JavaScript; see the list below.</noscript></div>
<section id="detail" hidden aria-live="polite"></section>
<h2 id="list">Searchable list</h2>
<div class="tablewrap"><table class="list" id="olist"><thead><tr><th>Name</th><th>Country</th><th>Type</th><th>Sector</th><th>Role / description</th><th>Sources</th></tr></thead><tbody></tbody></table></div>
<p class="notice">We only include what the sources say: name, public professional role and organisation. No private information, no organisation numbers or addresses. Photos are only shown when they are freely licensed (Wikimedia Commons), with credit; otherwise we show initials. The Norwegian part reuses the approved industry map from Kryptonytt Norway. Wrong or want to be removed? See <a href="../about/#corrections">corrections and removal</a>.</p>
<script id="orgdata" type="application/json">{json.dumps(pub_org, ensure_ascii=False).replace("</", "<\\/")}</script>
<script>window.FLAGS={FLAGS_JS};window.CNAME={json.dumps(dict(COUNTRIES, **EXTRA_C))};</script>"""
    page("org-chart", "Who's who in Nordic crypto", "org-chart", body,
         "Organisation chart of the Nordic crypto industry and its regulators – private and public sector, by country, with sources.",
         "<script>" + open(P("tools", "orgchart.js"), encoding="utf-8").read() + "</script>")

    # ---- Sources ----
    rows = []
    for c in list(COUNTRIES):
        for s in [x for x in cfg["sources"] if x.get("country") == c]:
            st = status.get(s["id"], {})
            if s["type"] == "search": cls, lab = "ok", "added manually"
            elif s.get("enabled") and st.get("ok", True) is not False: cls, lab = "ok", "monitored" + (f' ({st.get("entries")} items last run)' if st.get("entries") is not None else "")
            elif s.get("search_fallback"): cls, lab = "bad", "feed not working (covered via news search)"
            else: cls, lab = "bad", "not working" if s.get("enabled") else "not used"
            feed = f'<a href="{E(s["feed"])}" rel="noopener">{"feed" if s["type"] in ("rss", "rss-all") else "list page"}</a>' if s.get("feed") and "{q}" not in s["feed"] else ("search" if s.get("feed") else "–")
            rows.append(f'<tr data-c="{c}"><td>{flag(c)}</td><td><a href="{E(s["url"])}" rel="noopener" target="_blank">{E(s["name"])}</a>{" <span class=pw>paywall</span>" if s.get("paywall") else ""}</td><td>{E(s["kind"])}</td><td>{feed}</td>'
                        f'<td class="{cls}">{lab}</td><td>{E(s.get("status", ""))}</td></tr>')
    erows = []
    for s in cfg.get("event_sources", []):
        st = status.get("ev-" + s["id"], {})
        cls, lab = ("ok", "monitored") if s.get("enabled", True) and st.get("ok", True) else ("bad", "not working" if s.get("enabled", True) else "not used")
        erows.append(f'<tr><td>{flag(s.get("country"))}</td><td><a href="{E(s["url"])}" rel="noopener" target="_blank">{E(s["name"])}</a></td><td class="{cls}">{lab}</td><td>{E(s.get("status", ""))}</td></tr>')
    bing = [s for s in cfg["sources"] if s["type"] == "bing"]
    qs = "".join(f'<li>{flag(s["country"])} {E(", ".join(s.get("queries", [])))} – only {E(s["allowed_tld"])} domains</li>' for s in bing)
    body = f"""<h1>Sources we follow</h1>
<p class="lead">Newspapers, broadcasters, regulators, central banks and crypto media in the five countries. We read RSS feeds, public list pages (only links and page metadata) and a news search limited to each country's domains. We respect robots.txt, identify ourselves with our own user agent, wait at least {cfg.get("min_delay_seconds", 2)} seconds between requests to the same site, and never fetch article text behind a paywall. If a site blocks us, we leave it.</p>
<div class="tablewrap"><table class="list"><thead><tr><th></th><th>Source</th><th>Type</th><th>Feed</th><th>Status</th><th>Note</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="notice" id="kaupr"><b>Disclosure about Kaupr:</b> Kaupr (kaupr.io) is one of the news sources we follow, and it also sponsors some of the events in our calendar. Those events are labelled “Sponsored by kaupr.io”.</p>
<h2>News search terms</h2><ul class="prose">{qs}</ul><p class="prose">Links from the search always go straight to the original story.</p>
<h2>Keywords</h2><p class="prose">A story is picked up when its title or teaser mentions, for example: bitcoin, crypto, blockchain, stablecoin, MiCA, CBDC (all languages); krypto, kryptovaluta, blokkjede (Norwegian); kryptotillgångar, blockkedja, e-krona (Swedish); kryptovaluutta, lohkoketju, virtuaalivaluutta (Finnish); rafmynt, sýndareignir, bálkakeðja (Icelandic); or Nordic crypto firms such as Firi, NBX, K33, Safello, Coinmotion, Northcrypto, Myntkaup and Monerium. The editor reviews every hit before it is published.</p>
<h2 id="events">Where we find events</h2>
<div class="tablewrap"><table class="list"><thead><tr><th></th><th>Event source</th><th>Status</th><th>Note</th></tr></thead><tbody>{''.join(erows)}</tbody></table></div>
<p class="meta">Missing a source? Suggest it as an issue on <a href="https://github.com/jQrgen/nordic-crypto/issues" rel="noopener">GitHub</a>.</p>"""
    page("sources", "Sources", "sources", body, "Nordic newspapers, broadcasters, regulators and crypto media that Nordic Crypto follows, with the status of each feed.")

    build_calendar(cfg)
    build_academia()
    build_changelog()
    body = open(P("templates", "about.html"), encoding="utf-8").read()
    page("about", "About Nordic Crypto", "about", body, "About Nordic Crypto: who runs it, how it works, corrections and removal.")
    # ---- Office screen ----
    os.makedirs(os.path.join(SITE, "screen"), exist_ok=True)
    open(os.path.join(SITE, "screen", "index.html"), "w", encoding="utf-8").write(
        open(P("templates", "screen.html"), encoding="utf-8").read().replace("__BASE__", BASE).replace("__FLAGS__", FLAGS_JS).replace("__PREVIEW__", "true" if PREVIEW else "false"))
    for old, new in (("kalender", "calendar"), ("skjerm", "screen"), ("organisasjonskart", "org-chart"), ("kilder", "sources"), ("om", "about"), ("akademia", "academia")): redirect(old, new)
    active = sorted({(s.get("outlet") and next((x["name"] for x in cfg["sources"] if x["id"] == s.get("outlet")), s["name"]) or s["name"]).split(" (")[0] + "|" + s["country"]
                     for s in cfg["sources"] if s.get("enabled") and s["type"] not in ("bing", "search") and status.get(s["id"], {}).get("ok", True)})
    seen = set(); act = []
    for a in active:
        n, c = a.split("|")
        if n not in seen: seen.add(n); act.append({"name": n, "country": "NO" if n == "Kaupr" else c})
    json.dump({"active": act}, open(os.path.join(SITE, "data", "sources.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(SITE, "robots.txt"), "w").write("User-agent: *\n" + ("Disallow: /\n" if PREVIEW else "Allow: /\n"))
    print(f"build{' (PREVIEW)' if PREVIEW else ''}: {len(items)} stories ({len(approved)} approved, {len(pending)} pending), "
          f"{len(ents)} org rows ({sum(e['type']=='person' for e in ents)} people), {len(rels)} relations -> {SITE}")

def md_inline(s):
    s = E(s)
    s = re.sub(r"(https?://[^\s<;]+[^\s<;.,)])", r'<a href="\1" rel="noopener" target="_blank">\1</a>', s)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
def first_sentence(s):
    for m in re.finditer(r"[.!?](?=\s+[A-ZÁÉÍÓÚÞÆÖØÅÄ])", s):
        if not re.search(r"\b(No|Nos|Act|Art|Reg|e\.g|i\.e|Mr|Ms|Dr|ehf|hf)\.$", s[:m.end()]): return s[:m.end()]
    return s
def build_stories():
    """Own stories written by the editor (markdown). Public build: only slugs in approved.json stories.approve.
    Preview: also stories.ready_for_owner, tagged as awaiting jQrgen's final approval. The 'Editor notes' part is internal and never rendered."""
    st = (load(P("queue", "approved.json"), {}) or {}).get("stories", {}) or {}
    out = []
    for slug, path in (st.get("files") or {}).items():
        if slug in st.get("approve", []): status = "published"
        elif PREVIEW and slug in st.get("ready_for_owner", []): status = "owner"
        else: continue
        if not os.path.exists(path): print("story missing:", path); continue
        md = open(path, encoding="utf-8").read().split("\nEditor notes")[0]
        title, country, paras, srcs, cur, sec = None, None, [], [], [], None
        for line in md.splitlines():
            l = line.strip()
            if l.startswith("# "): continue
            if l.startswith("## "): title = l[3:]; continue
            if l.startswith("Country:"): country = {"Iceland": "IS", "Norway": "NO", "Sweden": "SE", "Finland": "FI"}.get(l.split("·")[0].split(":", 1)[1].strip(), "NORDIC"); meta = l; continue
            if l == "Sources:": sec = "src"; continue
            if sec == "src" and l.startswith("- "): srcs.append(l[2:]); continue
            if not l:
                if cur: paras.append(" ".join(cur)); cur = []
                continue
            cur.append(l)
        if cur: paras.append(" ".join(cur))
        pub = dt.datetime.fromtimestamp(os.path.getmtime(path), OSLO).replace(microsecond=0).isoformat()
        body = (f'<p class="meta"><a href="../../">← News</a></p><article class="prose"><h1>{E(title)}</h1>'
                f'<p class="meta">{flag(country)} {E(cname(country))} · Nordic Crypto · {endate(pub)}'
                + (' <span class="tag pend">Editor-approved · awaiting jQrgen\'s final approval</span>' if status == "owner" else "") + '</p>'
                + "".join(f"<p>{md_inline(x)}</p>" for x in paras)
                + '<h2>Sources</h2><ul>' + "".join(f"<li>{md_inline(s)}</li>" for s in srcs) + '</ul>'
                + '<p class="notice">Translated and summarised from Icelandic and English sources by our editor. Not investment advice. Corrections: see <a href="../../about/#corrections">corrections and removal</a>.</p></article>')
        page("stories/" + slug, title, "stories", body, paras[0][:200] if paras else title)
        first = (st.get("summaries") or {}).get(slug) or (first_sentence(paras[0]) if paras else "")
        out.append({"id": "story-" + slug, "url": f"stories/{slug}/", "title": title, "source": "nordic-crypto", "source_name": "Nordic Crypto",
                    "country": country, "language": "English", "published": pub, "topics": ["regulation"], "summary": first, "status": status, "own_story": True})
    return out

def events_for_site():
    ev = load(P("data", "events.json"), {"events": []}); ap = (load(P("queue", "approved.json"), {}) or {}).get("events", {})
    now = dt.datetime.now(dt.timezone.utc); out = []
    for e in ev["events"]:
        e = dict(e)
        if e["id"] in ap.get("reject", []): continue
        if e["id"] in ap.get("approve", []): e["status"] = "published"
        elif e["id"] in ap.get("ready_for_owner", []): e["status"] = "owner"  # editor-approved, waits for jQrgen; preview only
        if e["status"] != "published" and not (PREVIEW and e["status"] in ("pending", "owner")): continue
        if not (e.get("place") or e.get("online")) or not e.get("organiser") or not e.get("start"): continue  # rule: date, place and organiser
        e["note"] = ap.get("notes", {}).get(e["id"]) or (e.get("note") if PREVIEW else None)
        if e["id"] in (ap.get("title_en") or {}): e["title_orig"] = e["title"]; e["title"] = ap["title_en"][e["id"]]
        if e["id"] in ap.get("sponsored", []): e["sponsored"] = True
        if e["id"] in ap.get("sponsor", {}): e["sponsored"] = ap["sponsor"][e["id"]]
        if e["id"] in ap.get("paid", {}): e["paid"] = ap["paid"][e["id"]]
        e["past"] = dt.datetime.fromisoformat(e.get("end") or e["start"]) < now
        out.append({k: e.get(k) for k in ("id", "title", "title_orig", "start", "end", "place", "city", "country", "online", "organiser", "url", "source", "paid", "sponsored", "note", "past", "status")})
    return sorted(out, key=lambda e: dt.datetime.fromisoformat(e["start"])), now

def build_calendar(cfg):
    evs, now = events_for_site()
    up = [e for e in evs if not e["past"]]; past = [e for e in evs if e["past"]][-10:][::-1]
    json.dump({"preview": PREVIEW, "events": up}, open(os.path.join(SITE, "data", "events.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    def when(e):
        a = dt.datetime.fromisoformat(e["start"]); b = dt.datetime.fromisoformat(e["end"]) if e.get("end") else None
        t = f'{WD[a.weekday()]} {a.day} {MON[a.month-1]} {a.year}, {a:%H:%M}'
        t += (f'–{b:%H:%M}' if b and b.date() == a.date() else (f' – {b.day} {MON[b.month-1]}' if b else ""))
        return t + f' ({CITYNAME.get(e.get("country"), "local")} time)'
    def badges(e):
        b = []
        if e.get("status") == "owner": b.append('<span class="tag pend">Editor-approved · awaiting jQrgen\'s final approval</span>')
        elif e.get("status") != "published": b.append('<span class="tag pend">Pending editor review</span>')
        if e.get("paid"): b.append('<span class="tag paid">Paid</span>')
        elif e.get("paid") is False: b.append('<span class="tag">Free</span>')
        if e.get("sponsored"): b.append('<span class="tag paid">' + (f'Sponsored by {E(e["sponsored"])}' if isinstance(e["sponsored"], str) else "Sponsored") + '</span>')
        if e.get("online"): b.append('<span class="tag">Online</span>')
        return " ".join(b)
    def li(e):
        return (f'<li id="e-{E(e["id"])}" data-c="{E(e.get("country"))}"><h3><a href="{E(e["url"])}" rel="noopener" target="_blank">{E(e["title"])}</a></h3>'
                f'<div class="meta">{flag(e.get("country"))} <time datetime="{E(e["start"])}"><b>{E(when(e))}</b></time> · {E(e.get("place") or "Online")}{(", " + E(e["city"])) if e.get("city") and e["city"] not in (e.get("place") or "") else ""} {badges(e)}</div>'
                + (f'<p class="orig">Original title: {E(e["title_orig"])}</p>' if e.get("title_orig") else "") + f'<div class="meta">Organiser: {E(e["organiser"])} · Listed at: <a href="{E(e["url"])}" rel="noopener" target="_blank">{E(e["source"])}</a></div>'
                + (f'<p class="sum"><b>Note:</b> {E(e["note"])}</p>' if e.get("note") else "") + '</li>')
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
                row.append(f'<td class="{cls}"><span class="d">{d.day}</span>' + "".join(f'<a href="#e-{E(e["id"])}" data-c="{E(e.get("country"))}" title="{E(cname(e.get("country")))}: {E(e["title"])}">{flag(e.get("country"))}<span>{E(e["title"])}</span></a>' for e in de) + '</td>')
            cells.append("<tr>" + "".join(row) + "</tr>")
        grids.append(f'<table class="cal"><caption>{MONTH[m-1]} {y}</caption><thead><tr>{"".join(f"<th>{d}</th>" for d in WD)}</tr></thead><tbody>{"".join(cells)}</tbody></table>')
    per_c = {c: sum(e.get("country") == c for e in up) for c in COUNTRIES}
    npend = sum(e.get("status") == "pending" for e in up); nown = sum(e.get("status") == "owner" for e in up)
    body = f"""<h1>Calendar: crypto, bitcoin and blockchain events in the Nordics</h1>
<p class="lead">Upcoming meetups, conferences and talks in Norway, Sweden, Finland and Iceland. We only list events where the organiser's own page or a public listing shows the date, place and organiser, and which are genuinely about crypto, bitcoin or blockchain. Paid and sponsored events are labelled. Times are local time in the event's country. Always check the details with the organiser.</p>
{f'<p class="notice warn"><b>Preview:</b> {npend} of {len(up)} upcoming events are pending editor review; {nown} editor-approved and awaiting jQrgen\'s final approval. None of them is in the public build yet.</p>' if PREVIEW and (npend or nown) else ''}
<div class="filters" role="group" aria-label="Filter by country"><span class="lbl">Country</span><div class="chips">{country_chips()}</div><span id="ecount" class="meta" aria-live="polite"></span></div>
<p class="meta">{" · ".join(f"{flag(c)} {E(n)}: {per_c[c]}" for c, n in COUNTRIES.items())}</p>
<div class="calgrid">{''.join(grids)}</div>
<h2>Upcoming</h2><ol class="news" id="evlist">{''.join(li(e) for e in up) or '<li class="empty">No upcoming events registered.</li>'}</ol>
{('<h2>Recent</h2><ol class="news past">' + ''.join(li(e) for e in past) + '</ol>') if past else ''}
<p class="meta">How we find events: <a href="../sources/#events">event sources</a>. Organising something about crypto in the Nordics? Send a link to the organiser's page as an issue on <a href="https://github.com/jQrgen/nordic-crypto/issues" rel="noopener">GitHub</a>.</p>"""
    js = """<script>(function(){var cc=[].slice.call(document.querySelectorAll('.cchip')),n=[].slice.call(document.querySelectorAll('#evlist li[data-c], .calgrid a[data-c], ol.past li[data-c]')),cnt=document.getElementById('ecount');
function apply(){var c=cc.filter(function(x){return x.getAttribute('aria-pressed')==='true'}).map(function(x){return x.dataset.c}),k=0;n.forEach(function(el){var ok=!c.length||c.indexOf(el.dataset.c)>=0;el.hidden=!ok;if(ok&&el.parentNode.id==='evlist')k++});cnt.textContent=k+' upcoming';history.replaceState(null,'',c.length?'#country='+c.join(','):location.pathname)}
var h=new URLSearchParams(location.hash.slice(1));(h.get('country')||'').split(',').forEach(function(x){cc.forEach(function(b){if(b.dataset.c===x)b.setAttribute('aria-pressed','true')})});
cc.forEach(function(b){b.addEventListener('click',function(){b.setAttribute('aria-pressed',b.getAttribute('aria-pressed')==='true'?'false':'true');apply()})});apply()})();</script>"""
    page("calendar", "Calendar – crypto, bitcoin and blockchain events in the Nordics", "calendar", body,
         "Upcoming crypto, bitcoin and blockchain events in Norway, Sweden, Finland and Iceland, with date, place and organiser.", js)
    print(f"calendar: {len(up)} upcoming {per_c}, {len(past)} recent")

def build_academia():
    """Academia page from data/academia.json. Public build: only rows approved in queue/approved.json -> academia.approve
    (key = doi for publications, url for the rest). Preview: also rows awaiting the editor, clearly marked."""
    subprocess.run([sys.executable, P("tools", "import_academia.py")], check=True)
    ac = load(P("data", "academia.json"), {}) or {}
    def keep(rows, key):  # only editor-approved rows reach the page, in preview too; pending/unverified/out stay in data/
        return [dict(r) for r in rows if r.get("status") == "approved"]
    secs = {k: keep(ac.get(k, []), "doi" if k == "publications" else "url") for k in ("courses", "groups", "publications", "research")}
    json.dump(dict({"updated": ac.get("updated"), "preview": PREVIEW}, **secs), open(os.path.join(SITE, "data", "academia.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    def st(r):
        return ('<span class="tag pend">Editor-approved · awaiting jQrgen\'s final approval</span>' if PREVIEW else "")
    def dom(u): return re.sub(r"^https?://(www[0-9]?\.)?", "", u).split("/")[0]
    def foot(r):
        return f'<div class="meta">Source: <a href="{E(r["source"])}" rel="noopener" target="_blank">{E(dom(r["source"]))}</a> · checked {E(r["checked"])} {st(r)}</div>'
    def row(c, inner): return f'<li data-c="{E(c)}">{inner}</li>'
    def bycountry(rows, fn):
        if not rows: return '<p class="empty">None listed yet – candidates are still with the researcher and the editor.</p>'
        return '<ol class="news">' + "".join(row(r["country"], fn(r)) for c in COUNTRIES for r in rows if r["country"] == c) + '</ol>'
    courses = bycountry(secs["courses"], lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["code"])} {E(r["name"])}</a></h3>'
        f'<div class="meta">{flag(r["country"])} <b>{E(r["institution"])}</b> · {E(r["level"])}' + (f' · <b>{E(r["term"])}</b>' if r.get("term") else "") + f'</div><p class="sum">{E(r["about"])}</p>{foot(r)}')
    groups = bycountry(secs["groups"], lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["name"])}</a> '
        f'<span class="tag {"act" if r["active"] else "inact"}">{"Active" if r["active"] else "Inactive"}</span></h3>'
        f'<div class="meta">{flag(r["country"])} <b>{E(r["institution"])}</b></div><p class="sum">{E(r["about"])} {E(r["activity"])}</p>{foot(r)}')
    def au(a): return ", ".join(a[:4]) + (" et al." if len(a) > 4 else "")
    pubs = bycountry(sorted(secs["publications"], key=lambda r: -(r.get("year") or 0)), lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["title"])}</a></h3>'
        f'<div class="meta">{flag(r["country"])} {E(au(r["authors"]))} ({E(r["year"])}). <i>{E(r.get("venue") or "")}</i>'
        + (f' · {E(r["institution"])}' if r.get("institution") else "") + '</div>'
        f'<div class="meta">DOI: <a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["doi"])}</a> · <a href="{E(r["db"])}" rel="noopener" target="_blank">{E(r.get("db_name", "database"))} record</a></div>{foot(r)}')
    research = bycountry(secs["research"], lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["name"])}</a></h3>'
        f'<div class="meta">{flag(r["country"])} <b>{E(r["institution"])}</b></div><p class="sum">{E(r["about"])}</p>{foot(r)}')
    allrows = sum(len(v) for v in secs.values()); npend = allrows if PREVIEW else 0
    per_c = {c: sum(r["country"] == c for v in secs.values() for r in v) for c in COUNTRIES}
    body = f"""<h1>Academia: blockchain and crypto at Nordic universities</h1>
<p class="lead">Courses and programmes, student associations, research groups and publications about blockchain, bitcoin and crypto in Norway, Sweden, Finland and Iceland. Every row links to its source and shows when we last checked it.</p>
{f'<p class="notice warn"><b>Preview:</b> only the {allrows} editor-approved rows are shown; all await jQrgen\'s final approval. Rows the editor has not approved yet are kept off this page.</p>' if PREVIEW else ''}
<div class="filters" role="group" aria-label="Filter by country"><span class="lbl">Country</span><div class="chips">{country_chips()}</div><span id="acount" class="meta" aria-live="polite"></span></div>
<p class="meta">{" · ".join(f"{flag(c)} {E(n)}: {per_c[c]}" for c, n in COUNTRIES.items())} · <a href="#courses">Courses</a> · <a href="#groups">Student groups</a> · <a href="#publications">Publications</a> · <a href="#research">Research groups</a></p>
<h2 id="courses">Courses and programmes</h2><p class="meta">Listed only when blockchain or crypto is a substantial part of the syllabus on the course's own page.</p>{courses}
<h2 id="groups">Student associations and initiatives</h2><p class="meta">“Active” means we found dated activity in the last 12 months; otherwise “Inactive”.</p>{groups}
<h2 id="publications">Publications</h2><p class="meta">Articles with at least one author at an institution in the country, linked by DOI or national research database (Cristin, SwePub, Research.fi, IRIS). Every link is checked to resolve before it is listed.</p>{pubs}
<h2 id="research">Research groups and projects</h2>{research}
<p class="notice">Missing a course, group or paper, or is something out of date? Tell us via <a href="../about/#corrections">corrections</a>. We list institutions and public academic work only, never students' private details.</p>"""
    js = """<script>(function(){var cc=[].slice.call(document.querySelectorAll('.cchip')),n=[].slice.call(document.querySelectorAll('ol.news li[data-c]')),cnt=document.getElementById('acount');
function apply(){var c=cc.filter(function(x){return x.getAttribute('aria-pressed')==='true'}).map(function(x){return x.dataset.c}),k=0;n.forEach(function(el){var ok=!c.length||c.indexOf(el.dataset.c)>=0;el.hidden=!ok;if(ok)k++});cnt.textContent=k+' rows';history.replaceState(null,'',c.length?'#country='+c.join(','):location.pathname+location.hash.replace(/#country=.*/,''))}
var h=new URLSearchParams(location.hash.slice(1));(h.get('country')||'').split(',').forEach(function(x){cc.forEach(function(b){if(b.dataset.c===x)b.setAttribute('aria-pressed','true')})});
cc.forEach(function(b){b.addEventListener('click',function(){b.setAttribute('aria-pressed',b.getAttribute('aria-pressed')==='true'?'false':'true');apply()})});apply()})();</script>"""
    page("academia", "Academia – blockchain and crypto at Nordic universities", "academia", body,
         "Blockchain and crypto courses, student groups, research groups and publications in Norway, Sweden, Finland and Iceland.", js)
    print(f"academia: {allrows} editor-approved rows shown {per_c}")

def build_changelog():
    """Changelog page from changelog.json (site changes only, newest first). Entries dated "launch" use launch_date,
    which stays null until jQrgen approves publishing (publish.sh --yes sets it); until then they show as preview."""
    cl = load(P("changelog.json"), {"entries": []}); launch = cl.get("launch_date")
    rows = []
    for e in cl.get("entries", []):
        d = launch if e.get("date") == "launch" else e.get("date")
        rows.append(dict(e, date=d))
    rows.sort(key=lambda e: e["date"] or "9999-99-99", reverse=True)
    json.dump({"launch_date": launch, "entries": [{k: e.get(k) for k in ("id", "date", "title", "description")} for e in rows]},
              open(os.path.join(SITE, "data", "changelog.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    def when(d):
        if not d: return '<span class="tag pend">Preview – not launched yet</span>'
        x = dt.date.fromisoformat(d); return f'<time datetime="{d}"><b>{x.day} {MONTH[x.month-1]} {x.year}</b></time>'
    lis = "".join(f'<li id="{E(e["id"])}"><h3>{E(e["title"])}</h3><div class="meta">{when(e["date"])}</div><p class="sum">{E(e["description"])}</p></li>' for e in rows)
    body = f"""<h1>Changelog</h1>
<p class="lead">Changes to the Nordic Crypto site itself – new pages, sections and features – newest first. Daily news is not listed here.</p>
{'' if launch else '<p class="notice warn"><b>Preview:</b> the site has not launched yet. Entries get the launch date once jQrgen approves publishing.</p>'}
<ol class="news">{lis or '<li class="empty">No changes recorded yet.</li>'}</ol>
<p class="meta">Data: <a href="../data/changelog.json">changelog.json</a>.</p>"""
    page("changelog", "Changelog", "changelog", body, "Changes to the Nordic Crypto site: new pages, sections and features, newest first.")
    print(f"changelog: {len(rows)} entries, launch date {launch or 'not set (preview)'}")

if __name__ == "__main__": build()
