#!/usr/bin/env python3
"""Redraw the original story illustrations (the files named original-*.webp).

Flat geometry only: no letters, no logos, no people, no copy of a news photo
or of a trademark. Wikimedia Commons files and official press photos are not
redrawn here; they are committed beside these files and recorded in
data/illustrations.json. Do not point this script at a newspaper.

  python3 tools/make_illustrations.py
"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "img", "illustrations")
W, H = 960, 540


def base(bg):
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 14, H), fill="#0f5ea8")
    return im, d


def save(im, name):
    path = os.path.join(OUT, name)
    im.save(path, "WEBP", quality=80, method=6)
    print(name, os.path.getsize(path))


def main():
    os.makedirs(OUT, exist_ok=True)
    im, d = base("#f6f1e7")
    d.ellipse((78, 90, 430, 442), fill="#e2b340")
    d.ellipse((148, 160, 360, 372), fill="#f6f1e7")
    d.rectangle((70, 250, 438, 282), fill="#c4922a")
    save(im, "original-bitcoin.webp")

    im, d = base("#f3f6fb")
    for x, hgt, col in ((90, 280, "#0f5ea8"), (190, 340, "#123a66"), (290, 220, "#7aa0c4")):
        d.rectangle((x, H - 70 - hgt, x + 64, H - 70), fill=col)
    d.rectangle((70, H - 70, 520, H - 54), fill="#111111")
    save(im, "original-regulation.webp")

    im, d = base("#eef2f6")
    d.polygon([(80, 210), (250, 80), (420, 210)], fill="#123a66")
    d.rectangle((100, 210, 168, 450), fill="#0f5ea8")
    d.rectangle((332, 210, 400, 450), fill="#0f5ea8")
    d.rectangle((80, 450, 420, 478), fill="#111111")
    save(im, "original-court.webp")

    im, d = base("#f7f7f5")
    for x, hgt, col in ((80, 300, "#111"), (160, 180, "#0f5ea8"), (240, 360, "#111"), (320, 140, "#7aa0c4"), (400, 260, "#0f5ea8"), (480, 210, "#111")):
        d.rectangle((x, H - 64 - hgt, x + 56, H - 64), fill=col)
    d.rectangle((64, H - 64, 620, H - 52), fill="#d1d5db")
    save(im, "original-exchange.webp")

    im, d = base("#f4f1ea")

    def cube(x, y, s, top, left, right):
        d.polygon([(x, y), (x + s, y - s // 2), (x + 2 * s, y), (x + s, y + s // 2)], fill=top)
        d.polygon([(x, y), (x + s, y + s // 2), (x + s, y + s // 2 + s), (x, y + s)], fill=left)
        d.polygon([(x + s, y + s // 2), (x + 2 * s, y), (x + 2 * s, y + s), (x + s, y + s // 2 + s)], fill=right)

    cube(90, 180, 70, "#d9dde3", "#8b939e", "#5c656f")
    cube(250, 210, 70, "#e2b340", "#a8842a", "#7a6120")
    cube(150, 300, 80, "#c5ccd4", "#6d7580", "#4a515a")
    save(im, "original-mining.webp")

    im, d = base("#f4f7fb")
    xs = [80, 280, 480, 680]
    for i, x in enumerate(xs):
        d.rounded_rectangle((x, 170, x + 150, 370), radius=18, fill="#0f5ea8" if i % 2 == 0 else "#123a66")
        if i < len(xs) - 1:
            d.rectangle((x + 150, 250, xs[i + 1], 290), fill="#111111")
    save(im, "original-crypto.webp")


if __name__ == "__main__":
    main()
