"""Renders Substack branding images from the sites' existing brand (wordmark colours + favicon mark) – PNGs + SVG source."""
from playwright.sync_api import sync_playwright
NC_MARK = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect width='16' height='16' fill='#0f5ea8'/><rect x='4' width='3' height='16' fill='white'/><rect y='6.5' width='16' height='3' fill='white'/></svg>"
KN_MARK = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect width='16' height='16' fill='#b45309'/><text x='8' y='12.5' font-size='12' text-anchor='middle' fill='white' font-family='DejaVu Sans, sans-serif' font-weight='bold'>K</text></svg>"
FONT = "font-family:system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif"   # same stack as the sites (no quotes: used inside style='…')
def word(nc): return ("Nordic <span style='color:#0f5ea8'>Crypto</span>" if nc else "Krypto<span style='color:#b45309'>nytt</span> Norge")
def tag(nc): return ("Crypto news from the Nordics" if nc else "Norske nyheiter om bitcoin, blokkjede og krypto")
JOBS = []
for nc, d in ((True, "/workspace/nordic-crypto/newsletter/assets/"), (False, "/workspace/kryptonytt/newsletter/assets/")):
    mark = NC_MARK if nc else KN_MARK
    open(d + "logo.svg", "w").write(mark.replace("viewBox", "width='512' height='512' viewBox") + "\n")
    JOBS += [(d + "logo-512.png", 512, 512, f"<div style='width:512px;height:512px'>{mark.replace('viewBox', 'width=\"512\" height=\"512\" viewBox')}</div>"),
             (d + "wordmark-1200x300.png", 1200, 300, f"<div style='width:1200px;height:300px;display:flex;align-items:center;justify-content:center;background:#fff;{FONT};font-weight:800;font-size:110px;letter-spacing:-2px;color:#111'>{word(nc)}</div>"),
             (d + "email-banner-1100x220.png", 1100, 220, f"<div style='width:1100px;height:220px;display:flex;align-items:center;gap:36px;padding:0 56px;box-sizing:border-box;background:#fff;border-bottom:8px solid {'#0f5ea8' if nc else '#b45309'};{FONT}'><div style='width:128px;height:128px;flex:none'>{mark.replace('viewBox', 'width=\"128\" height=\"128\" viewBox')}</div><div><div style='font-weight:800;font-size:72px;letter-spacing:-1px;color:#111'>{word(nc)}</div><div style='font-size:30px;color:#4B5563'>{tag(nc)}</div></div></div>"),
             (d + "cover-1200x630.png", 1200, 630, f"<div style='width:1200px;height:630px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:28px;background:{'#f5f7fa' if nc else '#f6f6f4'};{FONT}'><div style='width:180px;height:180px'>{mark.replace('viewBox', 'width=\"180\" height=\"180\" viewBox')}</div><div style='font-weight:800;font-size:92px;letter-spacing:-2px;color:#111'>{word(nc)}</div><div style='font-size:36px;color:#4B5563'>{tag(nc)}</div></div>")]
with sync_playwright() as p:
    b = p.chromium.launch()
    for path, w, h, html in JOBS:
        pg = b.new_page(viewport={"width": w, "height": h}); pg.set_content(f"<html><body style='margin:0'>{html}</body></html>"); pg.wait_for_timeout(150)
        pg.screenshot(path=path, clip={"x": 0, "y": 0, "width": w, "height": h}); pg.close(); print(path)
    b.close()
