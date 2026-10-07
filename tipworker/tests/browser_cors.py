#!/usr/bin/env python3
"""Real-browser CORS test of the /tip/ page against a local `wrangler dev` (Chrome via Playwright).
Build the site with TIP_ENDPOINT=http://127.0.0.1:8788 (to a scratch dir, never published). The page is served (Playwright
route) as the public origin /tip/ (allowed origin) and as https://evil.example/tip/
(other origin); the page's requests go over the network to the local worker, so Chrome itself enforces CORS
(preflight + Access-Control-Allow-Origin) on the worker's real headers.
Usage: python3 tipworker/tests/browser_cors.py <site_dir> [http://127.0.0.1:8788]"""
import mimetypes, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import site_url
from playwright.sync_api import sync_playwright
SITE = sys.argv[1]; W = (sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8788").rstrip("/")

def serve(route):
    path = route.request.url.split("://", 1)[1].split("/", 1)[1].split("?")[0]
    f = os.path.join(SITE, path + ("index.html" if path.endswith("/") or not path else ""))
    if not os.path.isfile(f): return route.fulfill(status=404, body="")
    route.fulfill(status=200, body=open(f, "rb").read(), content_type=mimetypes.guess_type(f)[0] or "text/html")

def run(origin, b):
    pg = b.new_page(); seen = []
    pg.on("request", lambda r: r.url.startswith(W) and seen.append((r.method, r.url[len(W):], r.headers.get("origin"))))
    pg.on("console", lambda m: m.type == "error" and seen.append(("console", m.text[:140])))
    pg.route(origin + "/**", serve)
    pg.goto(origin + "/tip/"); pg.wait_for_timeout(1500)
    pre = pg.inner_text("#tipmsg")
    pg.fill("#t-url", "https://e24.no/browser-test-" + origin.split("//")[1]); pg.select_option("#t-country", "NO"); pg.fill("#t-note", "browser test")
    pg.click("button[type=submit]"); pg.wait_for_function("document.getElementById('tipmsg').innerText.length>0 && !document.querySelector('#tipform button').disabled", timeout=20000)
    msg = pg.inner_text("#tipmsg"); pg.close(); return pre, msg, seen

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True, args=["--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults"]); fails = 0
    pre, msg, seen = run(site_url.ORIGIN, b)
    print("public origin: before submit:", repr(pre), "| after:", repr(msg)); print("   requests:", seen)
    if pre or "Thank you" not in msg: fails += 1; print("FAIL allowed origin")
    else: print("PASS allowed origin: health check OK, tip accepted")
    pre, msg, seen = run("https://evil.example", b)
    print("evil.example origin: before:", repr(pre[:60]), "| after:", repr(msg[:60])); print("   requests:", seen)
    if "Thank you" in msg or "offline" not in msg: fails += 1; print("FAIL other origin")
    else: print("PASS other origin: browser blocked (page shows offline + GitHub fallback)")
    b.close(); sys.exit(1 if fails else 0)
