#!/usr/bin/env python3
"""Real-browser test of the newsletter signup form (Chrome via Playwright) against a local `wrangler dev`
(SUBSCRIBE_TEST=1, so no mail is sent). The built page is served (Playwright route) as https://jqrgen.github.io/<repo>/…
(allowed origin) and as https://evil.example/<repo>/… (refused by CORS); Chrome enforces CORS on the worker's real headers.
Build first into a scratch dir with the flag on, e.g.
  NC_NEWSLETTER=1 NEWSLETTER_ENDPOINT=http://127.0.0.1:8789 NC_SITE_DIR=/tmp/ncn .venv/bin/python build.py
Usage: python3 tipworker/tests/browser_newsletter.py <site_dir> <repo> <page path> <home path> <sent text> [worker]
  e.g. … /tmp/ncn nordic-crypto sv/newsletter/ sv/ "Nästan klart"
       … /tmp/knn kryptonytt nyhetsbrev/ "" "Nesten ferdig"   (Kryptonytt nynorsk)"""
import mimetypes, os, sys, random
from playwright.sync_api import sync_playwright
SITE, REPO, PAGE, HOME, SENT = sys.argv[1:6]; W = (sys.argv[6] if len(sys.argv) > 6 else "http://127.0.0.1:8789").rstrip("/")

def serve(route):
    path = route.request.url.split(f"/{REPO}/", 1)[1].split("?")[0]
    f = os.path.join(SITE, path + ("index.html" if path.endswith("/") or not path else ""))
    if not os.path.isfile(f): return route.fulfill(status=404, body="")
    route.fulfill(status=200, body=open(f, "rb").read(), content_type=mimetypes.guess_type(f)[0] or "text/html")

def run(b, origin, path, sel):
    pg = b.new_page(); pg.route(origin + f"/{REPO}/**", serve)
    pg.goto(f"{origin}/{REPO}/{path}"); f = pg.locator(sel).first
    f.locator("input[type=email]").fill(f"browser{random.randint(1, 10**9)}@example.org"); f.locator("button").click()
    pg.wait_for_function("s=>{var e=document.querySelector(s);return e&&!e.querySelector('button').disabled&&e.querySelector('.nlmsg').textContent.length>0}", arg=sel, timeout=20000)
    msg = f.locator(".nlmsg").inner_text(); pg.close(); return msg

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True, args=["--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults"]); fails = 0
    def ok(c, m):
        global fails; print(("PASS  " if c else "FAIL  ") + m); fails += (not c)
    m = run(b, "https://jqrgen.github.io", PAGE, "main form.nlform"); ok(SENT in m, f"newsletter page, allowed origin: {m!r}")
    m = run(b, "https://jqrgen.github.io", HOME, "footer form.nlform"); ok(SENT in m, f"footer form on home page: {m!r}")
    m = run(b, "https://evil.example", PAGE, "main form.nlform"); ok(SENT not in m and m, f"other origin blocked by CORS: {m!r}")
    pg = b.new_page(); pg.route("https://jqrgen.github.io/" + REPO + "/**", serve)
    pg.goto(f"https://jqrgen.github.io/{REPO}/{PAGE}?confirmed=1"); m = pg.locator("main .nlmsg").first.inner_text(); pg.close()
    ok(bool(m), f"?confirmed=1 shows a message: {m!r}")
    b.close(); print(f"---- browser newsletter {REPO}: {4 - fails}/4"); sys.exit(1 if fails else 0)
