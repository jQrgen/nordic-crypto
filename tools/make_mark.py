#!/usr/bin/env python3
"""Draws the site mark and renders its favicon and app-icon set.

The mark is the Våpen shield from the logo sheet (option E) in the Langskip colours (option A):
per pale North Sea and gold, a key palewise counterchanged. On a dark ground the outline is Sailcloth; on a light ground it is North Sea.
The crest (assets/brand/crest.svg) and its files are not touched.

Writes:
  assets/brand/shield.svg         the shield for light grounds
  assets/brand/shield-band.svg    the shield for the North Sea band (header, footer)
  favicon.svg                     the shield on a rounded North Sea tile
  assets/brand/mark-{16,32,64,192,512}.png, mark-180.png (Apple touch icon, square), favicon.ico (16 and 32)
  apple-touch-icon.png (site root, which Safari and iOS fetch without a link) and the crest-era names that old links,
  bookmarks and the newsletter still use: assets/brand/icon.svg, icon-{16,32,192,512}.png, apple-touch-icon.png, favicon.ico
Needs rsvg-convert. Usage: python3 tools/make_mark.py"""
import os, shutil, struct, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEA, GOLD, SAIL = "#1E3A45", "#D9A034", "#F0F1EC"

# Shield and key on a 64 x 64 grid, as drawn on the logo sheet. The key's left half sits on the North Sea half and is gold;
# its right half (with the bit) sits on the gold half and is North Sea.
FIELD_DEXTER = "M8 4H32V61C18 56 8 46 8 30Z"
FIELD_SINISTER = "M32 4H56V30C56 46 46 56 32 61Z"
KEY_DEXTER = "M32 8.5A8.5 8.5 0 0 0 32 25.5L32 20.8A3.8 3.8 0 0 1 32 13.2ZM28.6 24H32V49H28.6Z"
KEY_SINISTER = "M32 8.5A8.5 8.5 0 0 1 32 25.5L32 20.8A3.8 3.8 0 0 0 32 13.2ZM32 24H35.4V49H32ZM35.4 36.5H45V41H40.5V44.5H45V49H35.4Z"
OUTLINE = "M8 4H56V30C56 46 46 56 32 61C18 56 8 46 8 30Z"
CROP = "6.4 2.4 51.2 60.2"   # the shield and its outline, nothing else


def shield(line):
    return (f'<path fill="{SEA}" d="{FIELD_DEXTER}"/><path fill="{GOLD}" d="{FIELD_SINISTER}"/>'
            f'<path fill="{GOLD}" d="{KEY_DEXTER}"/><path fill="{SEA}" d="{KEY_SINISTER}"/>'
            f'<path fill="none" stroke="{line}" stroke-width="2.4" stroke-linejoin="round" d="{OUTLINE}"/>')


def doc(viewbox, body, title="Nordic Crypto"):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" role="img">'
            f'<title>{title}</title>{body}</svg>\n')


def tile(rounded=True, scale=0.86):
    """The shield centred on a North Sea square. rounded=False for the Apple touch icon (iOS rounds it)."""
    rx = ' rx="14"' if rounded else ""
    k = scale
    # centre of the shield's box (32, 32.5) goes to the centre of the tile
    move = f"translate({32 - 32 * k:.3f} {32 - 32.5 * k:.3f}) scale({k})"
    return doc("0 0 64 64", f'<rect width="64" height="64"{rx} fill="{SEA}"/><g transform="{move}">{shield(SAIL)}</g>')


def ico(pngs):
    """ICO with PNG entries (Vista and later, every current browser)."""
    head = struct.pack("<HHH", 0, 1, len(pngs))
    entries, data, offset = b"", b"", 6 + 16 * len(pngs)
    for size, png in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset)
        data += png; offset += len(png)
    return head + entries + data


def write(rel, text):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as fh: fh.write(text)


def render(svg_text, size, out):
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
        fh.write(svg_text); src = fh.name
    try:
        subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), src, "-o", out], check=True)
    finally:
        os.unlink(src)


def main():
    write("assets/brand/shield.svg", doc(CROP, shield(SEA)))
    write("assets/brand/shield-band.svg", doc(CROP, shield(SAIL)))
    fav = tile()
    write("favicon.svg", fav)
    for size in (16, 32, 64, 192, 512):
        # 16 px: the shield fills more of the tile so the key still reads
        render(tile(scale=0.94) if size <= 32 else fav, size, os.path.join(ROOT, "assets", "brand", f"mark-{size}.png"))
    render(tile(rounded=False, scale=0.78), 180, os.path.join(ROOT, "assets", "brand", "mark-180.png"))
    pngs = [(s, open(os.path.join(ROOT, "assets", "brand", f"mark-{s}.png"), "rb").read()) for s in (16, 32)]
    with open(os.path.join(ROOT, "favicon.ico"), "wb") as fh: fh.write(ico(pngs))
    brand = os.path.join(ROOT, "assets", "brand")
    for old, new in [("assets/brand/icon.svg", "favicon.svg"), ("assets/brand/favicon.ico", "favicon.ico"),
                     ("assets/brand/apple-touch-icon.png", "assets/brand/mark-180.png"), ("apple-touch-icon.png", "assets/brand/mark-180.png")] + \
                    [(f"assets/brand/icon-{s}.png", f"assets/brand/mark-{s}.png") for s in (16, 32, 192, 512)]:
        shutil.copyfile(os.path.join(ROOT, new), os.path.join(ROOT, old))
    print("mark: shield.svg, shield-band.svg, favicon.svg, favicon.ico, mark-*.png, apple-touch-icon.png, crest-era icon names")


if __name__ == "__main__":
    main()
