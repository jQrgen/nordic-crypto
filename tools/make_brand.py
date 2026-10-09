#!/usr/bin/env python3
"""Media kit for /media/: the key shield from the front page (tools/make_mark.py) as downloadable files.

Builds on make_mark.py (shield.svg, shield-band.svg, favicon.svg, mark-*.png) and adds:
  assets/brand/shield-mono.svg            one colour (Pine Tar), the key knocked out of the dark half
  assets/brand/lockup.svg                 shield + "Nordic Crypto" for light grounds
  assets/brand/lockup-band.svg            the same on the North Sea band (as in the site header)
  assets/media/shield-4096.png            the shield, 4096 px tall, transparent
  assets/media/shield-mono-2048.png       one colour, 2048 px tall
  assets/media/lockup-light.png, lockup-dark.png   2400 px wide
Nothing else on the site changes: themed pages, favicon, app icons and the social image keep their files.

The wordmark is Cormorant Garamond Bold turned into outlines (fontTools), so the SVGs need no font.
PNGs are rendered with Playwright Chromium. Usage: python3 tools/make_mark.py && python3 tools/make_brand.py"""
import os, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_mark as mm

ROOT = mm.ROOT
SEA, GOLD, SAIL, TAR, FOAM, GOLD_INK = mm.SEA, mm.GOLD, mm.SAIL, "#1D1C1A", "#BFD3D3", "#8A5A0C"
FONT = os.path.join(ROOT, "assets", "fonts", "CormorantGaramond-Bold-latin.woff2")


def text_path(text, size):
    """Outlines for `text` at font size `size`; returns (path_d, width, ascent). Baseline at y=0, y grows down."""
    f = TTFont(FONT)
    cmap, gs, hmtx = f.getBestCmap(), f.getGlyphSet(), f["hmtx"]
    upm = f["head"].unitsPerEm
    k = size / upm
    d, x = [], 0.0
    kern = {}
    for ch in text:
        g = cmap[ord(ch)]
        pen = SVGPathPen(gs)
        gs[g].draw(pen)
        cmd = pen.getCommands()
        if cmd:
            d.append(f'<path transform="translate({x:.2f} 0) scale({k:.5f} {-k:.5f})" d="{cmd}"/>')
        x += hmtx[g][0] * k
    asc = f["hhea"].ascent * k
    return "".join(d), x, asc


def word(size, nordic, crypto):
    """'Nordic Crypto' as two coloured groups; returns (svg, width). Baseline at y=0."""
    a, wa, asc = text_path("Nordic", size)
    sp = text_path(" ", size)[1]
    b, wb, _ = text_path("Crypto", size)
    svg = f'<g fill="{nordic}">{a}</g><g fill="{crypto}" transform="translate({wa + sp:.2f} 0)">{b}</g>'
    return svg, wa + sp + wb


def lockup(nordic, crypto, line, ground=None):
    """Shield beside the wordmark, start-aligned, like the site header. 64-unit-high shield, text cap height ~ 0.55 of it."""
    sx, sy, sw, sh = 6.4, 2.4, 51.2, 60.2               # make_mark CROP
    scale = 100 / sh                                     # shield 100 units tall
    gap, size = 26, 78
    txt, tw = word(size, nordic, crypto)
    shield_w = sw * scale
    w = shield_w + gap + tw + 4
    h = 100
    base = 72                                            # baseline so the x-height sits on the shield's middle
    pad = 18 if ground else 0                            # a filled ground gets a margin so nothing touches its edge
    art = (f'<g transform="scale({scale:.5f}) translate({-sx} {-sy})">{mm.shield(line)}</g>'
           f'<g transform="translate({shield_w + gap:.2f} {base})">{txt}</g>')
    if ground:
        w, h = w + 2 * pad, h + 2 * pad
        art = f'<rect width="{w:.1f}" height="{h}" fill="{ground}"/><g transform="translate({pad} {pad})">{art}</g>'
    return mm.doc(f"0 0 {w:.1f} {h}", art), w, h


def shield_mono():
    """One colour: dark half and outline in Pine Tar, the key cut out of the dark half and drawn in the light half."""
    body = (f'<defs><mask id="k"><rect x="0" y="0" width="64" height="64" fill="#fff"/><path fill="#000" d="{mm.KEY_DEXTER}"/></mask></defs>'
            f'<path fill="{TAR}" mask="url(#k)" d="{mm.FIELD_DEXTER}"/><path fill="{TAR}" d="{mm.KEY_SINISTER}"/>'
            f'<path fill="none" stroke="{TAR}" stroke-width="2.4" stroke-linejoin="round" d="{mm.OUTLINE}"/>')
    return mm.doc(mm.CROP, body, "Nordic Crypto (one colour)")


def write(rel, text):
    p = os.path.join(ROOT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh: fh.write(text)


def render_all(jobs):
    """jobs: [(svg_text, out_rel, width, height)]. Chromium renders each SVG at exactly width x height, transparent."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        for svg, out, w, h in jobs:
            pg.set_viewport_size({"width": int(w), "height": int(h)})
            svg_sized = svg.replace("<svg ", f'<svg width="{int(w)}" height="{int(h)}" ', 1)
            pg.set_content(f'<html><body style="margin:0;background:transparent">{svg_sized.split("?>", 1)[1]}</body></html>')
            path = os.path.join(ROOT, out); os.makedirs(os.path.dirname(path), exist_ok=True)
            pg.screenshot(path=path, omit_background=True, clip={"x": 0, "y": 0, "width": int(w), "height": int(h)})
        b.close()


def main():
    write("assets/brand/shield-mono.svg", shield_mono())
    light, lw, lh = lockup(TAR, GOLD_INK, SEA)
    band, bw, bh = lockup(SAIL, GOLD, SAIL)
    write("assets/brand/lockup.svg", light)
    write("assets/brand/lockup-band.svg", band)
    shield_svg = open(os.path.join(ROOT, "assets/brand/shield.svg"), encoding="utf-8").read()
    band_bg, _, _ = lockup(SAIL, GOLD, SAIL, ground=SEA)
    render_all([
        (shield_svg, "assets/media/shield-4096.png", round(4096 * 51.2 / 60.2), 4096),
        (light, "assets/media/lockup-light.png", 2400, round(2400 * lh / lw)),
        (band_bg, "assets/media/lockup-dark.png", 2400, round(2400 * bh / bw)),
        (shield_mono(), "assets/media/shield-mono-2048.png", round(2048 * 51.2 / 60.2), 2048),
    ])
    print("media kit: shield-mono.svg, lockup.svg, lockup-band.svg, shield-4096.png, shield-mono-2048.png, lockup PNGs")


if __name__ == "__main__":
    main()
