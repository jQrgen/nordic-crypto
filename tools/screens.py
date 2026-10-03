#!/usr/bin/env python3
"""Screenshots of site/ served locally, for QA. .venv/bin/python tools/screens.py [base-url]
Also reports JavaScript errors and broken local links/assets per page."""
import sys, subprocess, time, os, socket
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base = sys.argv[1] if len(sys.argv) > 1 else None
srv = None
if not base:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", os.path.join(ROOT, "site")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1); base = f"http://127.0.0.1:{port}/"
shots = [("", 1280, 1000, "news-desktop.png", False), ("calendar/", 1280, 1400, "calendar-desktop.png", False), ("org-chart/", 1280, 1600, "org-chart-desktop.png", False),
         ("academia/", 1280, 1700, "academia.png", False), ("sources/", 1280, 1000, "sources.png", False), ("about/", 1280, 1000, "about.png", False),
         ("stories/iceland-mica-casp-status/", 1280, 1100, "story-iceland.png", False), ("changelog/", 1280, 900, "changelog.png", False),
         ("calendar/", 390, 844, "calendar-mobile.png", True), ("", 390, 844, "news-mobile.png", False), ("org-chart/", 390, 844, "org-chart-mobile.png", False), ("academia/", 390, 844, "academia-mobile.png", False),
         ("screen/", 1080, 1920, "screen-portrait-1080x1920.png", False), ("screen/", 1920, 1080, "screen-landscape-1920x1080.png", False)]
os.makedirs(os.path.join(ROOT, "shots"), exist_ok=True)
bad = 0
with sync_playwright() as p:
    b = p.chromium.launch()
    for path, w, h, out, full in shots:
        pg = b.new_page(viewport={"width": w, "height": h}); errs = []; fails = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("response", lambda r: fails.append(f"{r.status} {r.url}") if r.status >= 400 and r.url.startswith(base) else None)
        pg.goto(base + path); pg.wait_for_timeout(2500)
        ow = pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        pg.screenshot(path=os.path.join(ROOT, "shots", out), full_page=full); pg.close()
        print(out, "JS errors:", errs or "none", "| 4xx:", fails or "none", "| horizontal overflow:", ow); bad += bool(errs or fails)
    b.close()
if srv: srv.terminate()
sys.exit(1 if bad else 0)
