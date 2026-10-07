#!/usr/bin/env python3
"""End-to-end tests of the language selection with Playwright (Chromium). The site is served from a local build
(default /tmp/nce, built with GEO_ENDPOINT=https://geo.test.invalid) by routing the public origin
to the files, and the geo endpoint is mocked. Nothing leaves the box.
  GEO_ENDPOINT=https://geo.test.invalid NC_SITE_DIR=/tmp/nce .venv/bin/python build.py && .venv/bin/python tests/e2e_langselect.py [/tmp/nce]"""
import mimetypes, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import site_url
from playwright.sync_api import sync_playwright
SITE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/nce"; BASE = site_url.BASE; GEO = "https://geo.test.invalid/api/geo"
fails, n = [], 0
def serve(route):
    path = route.request.url.split("?")[0].split("#")[0][len(BASE):]
    f = os.path.join(SITE, path); f = os.path.join(f, "index.html") if os.path.isdir(f) or path.endswith("/") or not path else f
    if not os.path.exists(f): return route.fulfill(status=404, body="nf")
    route.fulfill(status=200, body=open(f, "rb").read(), content_type=mimetypes.guess_type(f)[0] or "text/html")
def ctx(b, country=None, langs=("en-US",), cookie=None, geo_fail=False, calls=None):
    c = b.new_context(locale=langs[0], extra_http_headers={"Accept-Language": ",".join(langs)})
    c.add_init_script(f"Object.defineProperty(navigator,'languages',{{get:()=>{json.dumps(list(langs))}}})")
    c.route(site_url.ORIGIN + "/**", serve)
    def geo(route):
        if calls is not None: calls.append(1)
        if geo_fail: return route.abort()
        route.fulfill(status=200, body=json.dumps({"country": country}), content_type="application/json", headers={"Access-Control-Allow-Origin": site_url.ORIGIN})
    c.route(GEO, geo)
    if cookie: c.add_cookies([{"name": "nc_lang", "value": cookie, "url": BASE}])
    return c
def check(name, cond, info=""):
    global n; n += 1
    if not cond: fails.append(f"{name} {info}")
    print(("ok   " if cond else "FAIL ") + name + (f"  ({info})" if info else ""))
def landed(c, url=BASE):
    p = c.new_page(); p.goto(url); p.wait_for_timeout(900); u = p.url; return p, u
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for country, lang in [("NO", "nn"), ("SE", "sv"), ("DK", "da"), ("FI", "fi"), ("IS", "is"), ("US", ""), ("AX", "sv"), ("DE", "de"), ("CN", "zh"), ("JP", "ja")]:
        c = ctx(b, country=country); p, u = landed(c); check(f"first visit from {country} -> /{lang}", u == BASE + (lang + "/" if lang else ""), u); c.close()
    c = ctx(b, country="SE", cookie="nb"); p, u = landed(c); check("cookie nb beats geo SE", u == BASE + "nb/", u); c.close()
    c = ctx(b, country="NO", cookie="en"); p, u = landed(c); check("cookie en beats geo NO (stays on root)", u == BASE, u); c.close()
    calls = []; c = ctx(b, country="SE", calls=calls); p, u = landed(c, BASE + "nb/"); check("direct link /nb/ never redirects", u == BASE + "nb/", u)
    check("no geo lookup on /nb/", not calls, f"{len(calls)} calls"); c.close()
    c = ctx(b, country="SE"); p, u = landed(c, BASE + "org-chart/"); check("non-home English page never redirects", u == BASE + "org-chart/", u); c.close()
    c = ctx(b, geo_fail=True, langs=("nb-NO", "en")); p, u = landed(c); check("geo unreachable -> navigator nb -> /nn/", u == BASE + "nn/", u); c.close()
    c = ctx(b, geo_fail=True, langs=("de-DE",)); p, u = landed(c); check("geo unreachable, German browser -> /de/", u == BASE + "de/", u); c.close()
    c = ctx(b, geo_fail=True, langs=("nl-NL",)); p, u = landed(c); check("geo unreachable, Dutch browser -> English", u == BASE, u); c.close()
    c = ctx(b, country="NO"); p, u = landed(c); check("NO -> nn", u == BASE + "nn/", u)
    p.goto(BASE); p.wait_for_timeout(900); check("back to root in same tab: no second auto-redirect", p.url == BASE, p.url)
    p.goto(BASE + "nn/"); nb = p.locator('a.quick[data-lang="nb"]'); check("nn page has a visible nb quick link", nb.count() == 1 and nb.is_visible())
    c.close()
    c = ctx(b, country="NO"); p = c.new_page(); p.goto(BASE + "sv/"); p.wait_for_timeout(300)
    p.locator('.langsw summary').first.click(); p.locator('.langsw a[data-lang="da"]').first.click(); p.wait_for_load_state(); p.wait_for_timeout(300)
    ck = {x["name"]: x for x in c.cookies()}.get("nc_lang")
    check("switcher click sets nc_lang cookie", bool(ck) and ck["value"] == "da", str(ck and ck["value"]))
    check("cookie scoped to the site path, 1 year, SameSite=Lax", bool(ck) and ck["path"] == site_url.PATH and ck["sameSite"] == "Lax" and ck["expires"] > 3e7 + __import__("time").time(), str(ck and (ck["path"], ck["sameSite"])))
    p2 = c.new_page(); p2.goto(BASE); p2.wait_for_timeout(900); check("after picking da, root opens /da/ despite geo NO", p2.url == BASE + "da/", p2.url); c.close()
    c = ctx(b, country="FI"); p, u = landed(c); check("fi page has a visible sv quick link", p.locator('a.quick[data-lang="sv"]').count() == 1 and p.locator('a.quick[data-lang="sv"]').is_visible()); c.close()
    b.close()
print(f"\n{n - len(fails)}/{n} passed"); sys.exit(1 if fails else 0)
