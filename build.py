#!/usr/bin/env python3
"""Builds the static site in site/ from data/news.json, data/events.json, data/orgchart.json and sources.json.
  .venv/bin/python build.py            # public build: ONLY editor-approved content (what publish.sh would push)
  .venv/bin/python build.py --preview  # local review build: also shows pending items, clearly marked "Pending editor review"
All paths are relative, so the site works at https://jqrgen.github.io/nordic-crypto/ and on a local server.
No tracking, no third-party scripts, no external fonts.
Languages (i18n/): English at the root, nynorsk /nn/, bokmål /nb/, svensk /sv/, dansk /da/, suomi /fi/, íslenska /is/.
Every page is built once per language; data/ (JSON), assets/ and screen/ (English) exist only at the root."""
import json, os, re, shutil, subprocess, html, sys, calendar, datetime as dt
from zoneinfo import ZoneInfo
import i18n
ROOT = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(ROOT, *a)
BASE = "https://jqrgen.github.io/nordic-crypto/"
SITE = os.environ.get("NC_SITE_DIR") or P("site")   # NC_SITE_DIR: scratch build dir (tipworker/publish_tip_page.sh)
PREVIEW = "--preview" in sys.argv
SITE_NAME = "Nordic Crypto"
def load(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
def snippets(url, title):
    try: return json.loads(subprocess.check_output(["node", P("tools", "snippets.js"), url, title]))
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
EXTRA_C_CODES = ["NORDIC", "EU"]
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
def flags_js(): return json.dumps({c: flag(c) for c in COUNTRY_CODES + ["NORDIC"]})

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
CSS += """
.langsw{position:relative;margin-left:auto;font-size:14px;display:flex;gap:10px;align-items:baseline}
.langsw details{position:relative}.langsw summary{cursor:pointer;list-style:none;border:1px solid var(--ink);padding:2px 8px}
.langsw summary::-webkit-details-marker{display:none}
.langsw ul{position:absolute;right:0;z-index:20;margin:4px 0 0;padding:4px 0;list-style:none;background:#fff;border:1px solid var(--ink);min-width:150px}
.langsw li a{display:block;padding:4px 12px;text-decoration:none}.langsw li a:hover,.langsw li a:focus{background:var(--soft)}
.langsw li a[aria-current]{font-weight:700}.langsw .quick{font-size:13.5px}
@media(max-width:640px){.langsw{margin-left:0;width:100%}}
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
"""

NAV = [("", "nav_news"), ("calendar", "nav_calendar"), ("org-chart", "nav_org"), ("academia", "nav_academia"), ("sources", "nav_sources"), ("about", "nav_about"), ("tip", "nav_tip")]
COOKIE_PATH = "/" + BASE.split("://", 1)[1].split("/", 1)[1]   # /nordic-crypto/
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
    """Signup form (posts to the Worker; works without JavaScript via a 303 back to /newsletter/). Honeypot 'website'."""
    ep = newsletter_endpoint()
    if not ep: return ""
    NL_N[0] += 1; i = NL_N[0]
    return (f'<form class="nlform{" nlc" if compact else ""}" method="post" action="{E(ep)}/api/subscribe" data-ep="{E(ep)}">'
            f'<input type="hidden" name="site" value="nordic-crypto"><input type="hidden" name="lang" value="{LANG}">'
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
def build_newsletter():
    """/newsletter/ in every language: what you get, the form, the privacy note and the Kaupr disclosure. Only when on."""
    if not newsletter_endpoint(): return
    sub = NL_CFG.get("substack_url")
    body = f"""<h1>{E(t("nl_title"))}</h1>
<p class="lead">{E(t("nl_lead"))}</p>
{newsletter_form()}
<div class="prose"><p class="notice">{t("nl_priv")}</p>
{f'<p><a href="{E(sub)}" rel="noopener">Substack</a></p>' if sub else ''}
<p class="meta">{t("nl_kaupr")}</p></div>"""
    page("newsletter", t("nl_title"), "newsletter", body, t("nl_desc"))
LANGSEL_JS = None
def langsel_script():
    global LANGSEL_JS
    if LANGSEL_JS is None: LANGSEL_JS = open(P("tools", "langselect.js"), encoding="utf-8").read()
    return LANGSEL_JS
def page(slug, title, nav, body, desc, extra_script="", langs=None):
    """Writes site/<lang>/<slug>/index.html for the current LANG (English at the root)."""
    depth = (slug.count("/") + 1 if slug else 0) + (0 if LANG == "en" else 1)
    root = "../" * depth or "./"           # site root (data/, assets/, screen/)
    rel = root + lp()                      # home of this language
    url = BASE + lp() + (slug + "/" if slug else "")
    s = snippets(url, f"{title} – {SITE_NAME}" if slug else f"{SITE_NAME} – {t('site_desc_suffix')}")
    nav_html = "".join(f'<a href="{rel}{n + "/" if n else ""}"{" aria-current=page" if n == nav else ""}>{E(t(k))}</a>' for n, k in NAV)
    langs = langs or i18n.LANGS
    alt = "".join(f'<link rel="alternate" hreflang="{i18n.HTML_LANG[l]}" href="{BASE}{lp(l)}{slug + "/" if slug else ""}">' for l in langs) + \
        f'<link rel="alternate" hreflang="x-default" href="{BASE}{slug + "/" if slug else ""}">'
    sw = "".join(f'<li><a href="{root}{lp(l)}{slug + "/" if slug else ""}" hreflang="{l}" lang="{l}" data-lang="{l}"{" aria-current=true" if l == LANG else ""}>{E(i18n.NAME[l])}</a></li>' for l in langs)
    q = i18n.QUICK.get(LANG)
    quick = (f'<a class="quick" href="{root}{lp(q)}{slug + "/" if slug else ""}" hreflang="{q}" lang="{q}" data-lang="{q}">{E(i18n.NAME[q])}</a>' if q in langs else "")
    switcher = (f'<div class="langsw">{quick}<details><summary aria-label="{E(t("lang_choose"))}">🌐 {E(i18n.NAME[LANG])}</summary>'
                f'<ul role="list" aria-label="{E(t("lang_label"))}">{sw}</ul></details></div>')
    banner = f'<div class="preview" role="note"><div class="wrap">{t("preview_banner")}</div></div>' if PREVIEW else ""
    # language auto-selection: only on the English home page (site root), see tools/langselect.js
    pick = ""
    if LANG == "en" and not slug:
        pick = ("<script>" + langsel_script().replace("__GEO__", json.dumps((geo_endpoint() + "/api/geo") if geo_endpoint() else None))
                .replace("__COOKIE_PATH__", COOKIE_PATH).replace("__LANGS__", json.dumps(i18n.LANGS)) + "</script>")
    setck = ("<script>(function(){document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[data-lang]');if(!a)return;"
             f"document.cookie='nc_lang='+a.getAttribute('data-lang')+';path={COOKIE_PATH};max-age=31536000;SameSite=Lax'+(location.protocol==='https:'?';Secure':'')}})}})();</script>")
    nlfoot = (f'<div class="nlfoot"><b>{E(t("nl_foot"))}</b> {newsletter_form(True)} <a href="{rel}newsletter/">{E(t("nl_more"))}</a></div>' if newsletter_endpoint() and slug != "newsletter" else "")
    doc = f"""<!doctype html>
<html lang="{i18n.HTML_LANG[LANG]}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{pick}<title>{E(title)}{" – " + SITE_NAME if slug else ""}</title>
<meta name="description" content="{E(desc)}"><link rel="canonical" href="{url}">{alt}{'<meta name="robots" content="noindex">' if PREVIEW else ''}
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{url}"><meta property="og:type" content="website"><meta property="og:locale" content="{i18n.OG_LOCALE[LANG]}">{''.join(f'<meta property="og:locale:alternate" content="{i18n.OG_LOCALE[l]}">' for l in langs if l != LANG)}
<meta name="referrer" content="strict-origin-when-cross-origin">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%230f5ea8'/%3E%3Crect x='4' width='3' height='16' fill='white'/%3E%3Crect y='6.5' width='16' height='3' fill='white'/%3E%3C/svg%3E">
<style>{CSS}{s['css']}</style></head>
<body>{banner}<header class="top"><div class="wrap"><a class="brand" href="{rel}">Nordic <span>Crypto</span></a><nav class="main" aria-label="{E(t("main_menu"))}">{nav_html}</nav>{switcher}</div></header>
<main class="wrap">
{body}
{s['top']}
</main>
<footer><div class="wrap">{nlfoot}{t("footer", site=SITE_NAME, rel=rel)}</div></footer>
{s['script']}{setck}{extra_script}{newsletter_script()}
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

def build():
    global LANG
    subprocess.run([sys.executable, P("tools", "apply_approvals.py")], check=True)
    subprocess.run([sys.executable, P("tools", "import_orgchart.py")], check=True)
    news = load(P("data", "news.json"), {"items": []}); org = load(P("data", "orgchart.json"), {"entities": [], "relations": []})
    cfg = load(P("sources.json")); status = load(P("state", "source_status.json"), {})
    if os.path.exists(SITE): shutil.rmtree(SITE)
    os.makedirs(os.path.join(SITE, "data"))
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    if PREVIEW: open(os.path.join(SITE, ".preview"), "w").write("local preview build – never publish\n")
    for i in news["items"]:  # translated summaries: public only once the editor approved them (summary_i18n_review)
        if not PREVIEW and i.get("summary_i18n_review", "approved") != "approved": i.pop("summary_i18n", None)
    approved = [i for i in news["items"] if i.get("status") == "published" and (i.get("summary") or "").strip()]
    pending = [i for i in news["items"] if i.get("status") == "pending"] if PREVIEW else []
    ctx = {"news": news, "org": org, "cfg": cfg, "status": status, "approved": approved, "pending": pending}
    LANG = "en"; ctx["stories"] = build_stories(write=False)
    items = sorted(approved + pending + ctx["stories"], key=lambda i: i["published"], reverse=True); ctx["items"] = items
    keys = ("id", "url", "title", "title_en", "source", "source_name", "country", "language", "published", "topics", "summary", "summary_i18n", "paywall", "links", "status", "own_story")
    pub_items = [{k: i.get(k) for k in keys if k in i} for i in items]
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
    for LANG in i18n.LANGS:
        build_lang(ctx)
    LANG = "en"
    os.makedirs(os.path.join(SITE, "screen"), exist_ok=True)
    open(os.path.join(SITE, "screen", "index.html"), "w", encoding="utf-8").write(
        open(P("templates", "screen.html"), encoding="utf-8").read().replace("__BASE__", BASE).replace("__FLAGS__", flags_js()).replace("__PREVIEW__", "true" if PREVIEW else "false"))
    for old, new in (("kalender", "calendar"), ("skjerm", "screen"), ("organisasjonskart", "org-chart"), ("kilder", "sources"), ("om", "about"), ("akademia", "academia")): redirect(old, new)
    active = sorted({(s.get("outlet") and next((x["name"] for x in cfg["sources"] if x["id"] == s.get("outlet")), s["name"]) or s["name"]).split(" (")[0] + "|" + s["country"]
                     for s in cfg["sources"] if s.get("enabled") and s["type"] not in ("bing", "search") and status.get(s["id"], {}).get("ok", True)})
    seen = set(); act = []
    for a in active:
        n, c = a.split("|")
        if n not in seen: seen.add(n); act.append({"name": n, "country": "NO" if n == "Kaupr" else c})
    json.dump({"active": act}, open(os.path.join(SITE, "data", "sources.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(SITE, "robots.txt"), "w").write("User-agent: *\n" + ("Disallow: /\n" if PREVIEW else "Allow: /\n"))
    sitemap()
    miss = sorted(i18n.MISSING)
    if miss: print(f"i18n: {len(miss)} missing strings fell back to English: {miss[:12]}{' …' if len(miss) > 12 else ''}")
    print(f"build{' (PREVIEW)' if PREVIEW else ''}: {len(items)} stories ({len(approved)} approved, {len(pending)} pending), "
          f"{len(ents)} org rows ({sum(e['type']=='person' for e in ents)} people), {len(rels)} relations, {len(i18n.LANGS)} languages -> {SITE}")

def sitemap():
    urls = []
    for dp, _, fs in os.walk(SITE):
        if "index.html" in fs:
            r = os.path.relpath(dp, SITE).replace(os.sep, "/"); r = "" if r == "." else r + "/"
            if r.split("/")[0] in ("kalender", "skjerm", "organisasjonskart", "kilder", "om", "akademia"): continue
            urls.append(BASE + r)
    open(os.path.join(SITE, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{u}</loc></url>\n" for u in sorted(urls)) + "</urlset>\n")

def build_lang(ctx):
    items, pending = ctx["items"], ctx["pending"]
    # ---- News ----
    srcs = sorted({(i["source"], i["source_name"]) for i in items}, key=lambda x: x[1].lower())
    lis = []
    for i in items:
        pend = i.get("status") not in ("published", "owner"); own = i.get("status") == "owner"
        tags = "".join(f'<span class="tag">{E(topic_label(x))}</span>' for x in i["topics"])
        pw = f' · <span class="pw">{E(t("paywall"))}</span>' if i.get("paywall") else ""
        src_l = i18n.SRC_LANG.get(i.get("language") or "", "en")
        if LANG == "en" or i.get("own_story"):  # English: our English headline + the original below; own stories: our title
            head, head_l = (i.get("title_en") or i["title"]), ("en" if i.get("title_en") or i.get("own_story") else src_l)
            orig = (f'<p class="orig">{E(t("orig_title", l=t("lname_" + i["language"]) if i18n.has("en", "lname_" + (i.get("language") or "")) else (i.get("language") or "")))}<span lang="{src_l}">{E(i["title"])}</span></p>'
                    if i.get("title_en") and LANG == "en" else "")
        else:  # other languages: the external headline exactly as in the source
            head, head_l, orig = i["title"], src_l, ""
        lname = i.get("language") or ""
        lang = f' · {E(t("lang_" + lname))}' if lname and i18n.has("en", "lang_" + lname) and lname != i18n.SAME_LANG[LANG] else ""
        if pend:
            summ = f'<p class="sum pend">{E(t("sum_pending"))}</p>'
        else:
            txt, tl = L18(i, "summary")
            summ = f'<p class="sum"{lang_attr(tl)}>{E(txt)}</p>'
        hl = "" if head_l == LANG else f' lang="{head_l}"'
        lis.append(f'<li data-src="{E(i["source"])}" data-c="{E(i.get("country"))}" data-topics="{E(" ".join(i["topics"]))}">'
                   f'<h3><a href="{E(i["url"])}"{"" if i.get("own_story") else " rel=noopener target=_blank"}{hl}>{E(head)}</a></h3>{orig}'
                   f'<div class="meta">{flag(i.get("country"))} {E(cname(i.get("country")))} · <b>{E(i["source_name"])}</b> · <time datetime="{E(i["published"])}">{endate(i["published"])}</time>{lang}{pw} {tags}'
                   + (f' <span class="tag pend">{E(t("pending"))}</span>' if pend else "") + (f' <span class="tag pend">{E(t("owner"))}</span>' if own else "")
                   + (f' <span class="tag">{E(t("our_story"))}</span>' if i.get("own_story") else "") + f'</div>{summ}'
                   + "".join(f'<div class="meta">↳ <a href="{E(l["url"])}" rel="noopener" target="_blank">{E(l["label"])}</a></div>' for l in i.get("links", []) or []) + '</li>')
    opts = "".join(f'<option value="{E(k)}">{E(n)}</option>' for k, n in srcs)
    tchips = "".join(f'<button type="button" class="chip tchip" data-t="{k}" aria-pressed="false">{E(topic_label(k))}</button>' for k in TOPICS)
    news = ctx["news"]; upd = endate(news["updated"]) if news.get("updated") else ""
    root = "../" if LANG != "en" else ""
    body = f"""<h1>{E(t("home_h1"))}</h1>
<p class="meta"><a href="{root}screen/">{E(t("home_screen"))}</a></p>
<p class="lead">{E(t("home_lead", upd=upd, n=len(items), pend=t("home_pend", n=len(pending)) if pending else ""))}</p>
<div class="filters" role="group" aria-label="{E(t("filters"))}"><span class="lbl">{E(t("country"))}</span><div class="chips">{country_chips()}</div>
<label for="fsrc">{E(t("source"))}</label><select id="fsrc"><option value="">{E(t("all_sources"))}</option>{opts}</select>
<span class="lbl">{E(t("topic"))}</span><div class="chips">{tchips}</div><span id="count" class="meta" aria-live="polite"></span></div>
<ol class="news" id="news">{''.join(lis) or f'<li class="empty">{E(t("no_stories"))}</li>'}</ol>
<p class="notice">{E(t("home_notice"))}</p>"""
    js = """<script>
(function(){var NS=%s,sel=document.getElementById('fsrc'),tc=[].slice.call(document.querySelectorAll('.tchip')),cc=[].slice.call(document.querySelectorAll('.cchip')),lis=[].slice.call(document.querySelectorAll('#news li[data-src]')),cnt=document.getElementById('count');
function on(a,k){return a.filter(function(c){return c.getAttribute('aria-pressed')==='true'}).map(function(c){return c.dataset[k]})}
function apply(push){var s=sel.value,t=on(tc,'t'),c=on(cc,'c'),n=0;
lis.forEach(function(li){var ok=(!s||li.dataset.src===s)&&(!c.length||c.indexOf(li.dataset.c)>=0)&&(!t.length||t.some(function(x){return (' '+li.dataset.topics+' ').indexOf(' '+x+' ')>=0}));li.hidden=!ok;if(ok)n++});
cnt.textContent=NS.replace('{n}',n);if(push){var p=new URLSearchParams();if(c.length)p.set('country',c.join(','));if(s)p.set('source',s);if(t.length)p.set('topic',t.join(','));history.replaceState(null,'',p.toString()?'#'+p:location.pathname)}}
var p=new URLSearchParams(location.hash.slice(1));if(p.get('source'))sel.value=p.get('source');
(p.get('topic')||'').split(',').forEach(function(x){tc.forEach(function(c){if(c.dataset.t===x)c.setAttribute('aria-pressed','true')})});
(p.get('country')||'').split(',').forEach(function(x){cc.forEach(function(c){if(c.dataset.c===x)c.setAttribute('aria-pressed','true')})});
sel.addEventListener('change',function(){apply(1)});tc.concat(cc).forEach(function(c){c.addEventListener('click',function(){c.setAttribute('aria-pressed',c.getAttribute('aria-pressed')==='true'?'false':'true');apply(1)})});apply(0)})();
</script>""" % json.dumps(i18n.strings(LANG).get("n_stories") or i18n.strings("en")["n_stories"])
    page("", t("home_title"), "", body, t("home_desc"), js)
    build_stories(write=True)
    build_org(ctx)
    build_sources(ctx)
    build_calendar(ctx)
    build_academia()
    build_changelog()
    build_tip()
    build_newsletter()
    build_rules(ctx)
    about = open(P("templates", f"about.{LANG}.html" if LANG != "en" else "about.html"), encoding="utf-8").read().replace("{{UP}}", up1())
    page("about", t("about_title"), "about", about, t("about_desc"))

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
        if write:
            note = t("story_only_en")
            body = (f'<p class="meta"><a href="../../">{E(t("back_news"))}</a></p>' + (f'<p class="notice">{E(note)}</p>' if note and art_l == "en" and LANG != "en" else "")
                    + f'<article class="prose"{lang_attr(art_l)}><h1>{E(title)}</h1>'
                    f'<p class="meta">{flag(country)} {E(cname(country))} · Nordic Crypto · {endate(pub)}'
                    + (f' <span class="tag pend">{E(t("owner"))}</span>' if status == "owner" else "") + '</p>'
                    + "".join(f"<p>{md_inline(x)}</p>" for x in paras)
                    + f'<h2>{E(t("sources_h"))}</h2><ul>' + "".join(f"<li>{md_inline(s)}</li>" for s in srcs) + '</ul></article>'
                    + f'<p class="notice">{t("story_notice", rel="../../")}</p>')
            page("stories/" + slug, title, "stories", body, paras[0][:200] if paras else title)
        first = (st.get("summaries") or {}).get(slug) or (first_sentence(paras[0]) if paras else "")
        out.append({"id": "story-" + slug, "url": f"stories/{slug}/", "title": title, "source": "nordic-crypto", "source_name": "Nordic Crypto",
                    "country": country, "language": "English", "published": pub, "topics": ["regulation"], "summary": first,
                    "summary_i18n": (st.get("summaries_i18n") or {}).get(slug) or {}, "status": status, "own_story": True})
    return out

def events_for_site():
    ev = load(P("data", "events.json"), {"events": []}); ap = (load(P("queue", "approved.json"), {}) or {}).get("events", {})
    now = dt.datetime.now(OSLO); out = []  # "finished" is judged in Oslo time
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
        if e["status"] == "published": e["note"] = ap.get("notes", {}).get(e["id"])  # archive/public: editor's note only
        e["note_i18n"] = (ap.get("notes_i18n") or {}).get(e["id"]) if e.get("note") else None
        e["past"] = dt.datetime.fromisoformat(e.get("end") or e["start"]) < now
        out.append({k: e.get(k) for k in ("id", "title", "title_orig", "start", "end", "place", "city", "country", "online", "organiser", "url", "source", "paid", "sponsored", "note", "note_i18n", "past", "status")})
    # Archive (committed to git): every event ever approved. jQrgen's rule: finished events are NEVER deleted, they move to
    # "Past events". Fetch and build may only add or update archive entries, never remove them. Pending/preview events are not archived.
    arkf = P("archive", "events.json"); ark = load(arkf, {"events": []}); by = {e["id"]: e for e in ark["events"]}
    for e in out:
        if e["status"] == "published": by[e["id"]] = {k: v for k, v in e.items() if k != "past"}
    ark["_how_to"] = "Add-only archive of every editor-approved event (written by build.py). Never delete entries; finished events are shown under 'Past events'."
    ark["events"] = sorted(by.values(), key=lambda e: dt.datetime.fromisoformat(e["start"]))
    os.makedirs(os.path.dirname(arkf), exist_ok=True)
    json.dump(ark, open(arkf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    seen = {e["id"] for e in out}
    for e in ark["events"]:  # archived events that have dropped out of data/events.json (e.g. finished ones)
        if e["id"] in seen or e["id"] in ap.get("reject", []): continue  # rejected: hidden, but kept in the archive
        e = dict(e); e["note_i18n"] = e.get("note_i18n") or ((ap.get("notes_i18n") or {}).get(e["id"]) if e.get("note") else None)
        e["past"] = dt.datetime.fromisoformat(e.get("end") or e["start"]) < now; out.append(e)
    return sorted(out, key=lambda e: dt.datetime.fromisoformat(e["start"])), now

def build_calendar(ctx):
    evs, now = ctx["events"]
    up = [e for e in evs if not e["past"]]; past = [e for e in evs if e["past"] and e.get("status") == "published"][::-1]  # all finished, newest first
    def when(e):
        a = dt.datetime.fromisoformat(e["start"]); b = dt.datetime.fromisoformat(e["end"]) if e.get("end") else None
        s = f'{i18n.WD[LANG][a.weekday()]} {i18n.short_date(LANG, a)}, {i18n.hm(LANG, a)}'
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
<h2 id="past">{E(t("past_h"))}</h2><p class="meta">{E(t("past_note"))}</p><ol class="news past">{''.join(li(e) for e in past) or f'<li class="empty">{E(t("no_past"))}</li>'}</ol>
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
    if LANG == "en": subprocess.run([sys.executable, P("tools", "import_academia.py")], check=True)
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
    def row(c, inner): return f'<li data-c="{E(c)}">{inner}</li>'
    def bycountry(rows, fn):
        if not rows: return f'<p class="empty">{E(t("ac_empty"))}</p>'
        return '<ol class="news">' + "".join(row(r["country"], fn(r)) for c in COUNTRY_CODES for r in rows if r["country"] == c) + '</ol>'
    courses = bycountry(secs["courses"], lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["code"])} {E(r["name"])}</a></h3>'
        f'<div class="meta">{flag(r["country"])} <b>{E(r["institution"])}</b> · <span{en}>{E(r["level"])}</span>' + (f' · <b{en}>{E(r["term"])}</b>' if r.get("term") else "") + f'</div><p class="sum"{en}>{E(r["about"])}</p>{foot(r)}')
    groups = bycountry(secs["groups"], lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["name"])}</a> '
        f'<span class="tag {"act" if r["active"] else "inact"}">{E(t("active") if r["active"] else t("inactive"))}</span></h3>'
        f'<div class="meta">{flag(r["country"])} <b>{E(r["institution"])}</b></div><p class="sum"{en}>{E(r["about"])} {E(r["activity"])}</p>{foot(r)}')
    def au(a): return ", ".join(a[:4]) + (t("et_al") if len(a) > 4 else "")
    pubs = bycountry(sorted(secs["publications"], key=lambda r: -(r.get("year") or 0)), lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["title"])}</a></h3>'
        f'<div class="meta">{flag(r["country"])} {E(au(r["authors"]))} ({E(r["year"])}). <i>{E(r.get("venue") or "")}</i>'
        + (f' · {E(r["institution"])}' if r.get("institution") else "") + '</div>'
        f'<div class="meta">DOI: <a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["doi"])}</a> · <a href="{E(r["db"])}" rel="noopener" target="_blank">{E(t("ac_record", db=r.get("db_name") or t("database")))}</a></div>{foot(r)}')
    research = bycountry(secs["research"], lambda r: f'<h3><a href="{E(r["url"])}" rel="noopener" target="_blank">{E(r["name"])}</a></h3>'
        f'<div class="meta">{flag(r["country"])} <b>{E(r["institution"])}</b></div><p class="sum"{en}>{E(r["about"])}</p>{foot(r)}')
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
def tip_endpoint():
    """Fixed public tip endpoint (e.g. https://tips.<domain>): env TIP_ENDPOINT or tipserver/config.json -> public_endpoint.
    Takes precedence and is baked into /tip/. Without it, /tip/ reads the current quick-tunnel URL at runtime from
    /tip-endpoint.json (written by tipserver/publish_endpoint.sh whenever the tunnel URL changes)."""
    e = os.environ.get("TIP_ENDPOINT") or (load(P("tipserver", "config.json"), {}) or {}).get("public_endpoint")
    return (e or "").strip().rstrip("/") or None

def write_tip_endpoint_file():
    """site/tip-endpoint.json, so a full publish (which replaces gh-pages with site/) keeps the current endpoint."""
    sys.path.insert(0, P("tipserver")); import endpoint as _ep
    ep, kind = (tip_endpoint(), "fixed") if tip_endpoint() else _ep.current()
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
    routines/nightly-fetch.sh -> tools/reader_tips.py puts open tips in the editor queue as pending; nothing is auto-published."""
    if LANG == "en": write_tip_endpoint_file()
    cfg = load(P("tipserver", "config.json"), {}) or {}
    if tip_endpoint() or cfg.get("quick_tunnel"): return build_tip_server(tip_endpoint())  # GitHub issue form only as fallback link
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

if __name__ == "__main__": build()
