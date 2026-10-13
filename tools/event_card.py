"""1200x630 link-preview card for an event page: the event title on the brand background.
Pillow is optional; without it the caller falls back to the site-wide og-image."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_B = os.path.join(ROOT, "assets", "fonts", "CormorantGaramond-SemiBold.ttf")
FONT_R = os.path.join(ROOT, "assets", "fonts", "SchibstedGrotesk-Medium.ttf")


def _wrap(draw, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        nxt = (cur + " " + w).strip()
        if draw.textlength(nxt, font=font) <= width or not cur: cur = nxt
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def render(path, title, subtitle=""):
    """Write the card to path. Returns True when written, False when Pillow is missing."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    W, H, pad = 1200, 630, 80
    img = Image.new("RGB", (W, H), "#1E3A45"); d = ImageDraw.Draw(img)
    d.rectangle([0, H - 14, W, H], fill="#C8A24A")
    small = ImageFont.truetype(FONT_R, 30)
    d.text((pad, pad - 10), "NORDIC CRYPTO - CALENDAR", font=small, fill="#C8A24A")
    size = 84
    while True:
        big = ImageFont.truetype(FONT_B, size)
        lines = _wrap(d, title, big, W - 2 * pad)
        if len(lines) <= 4 or size <= 48: break
        size -= 6
    lines = lines[:4]
    y = 170
    for ln in lines:
        d.text((pad, y), ln, font=big, fill="#FFFFFF"); y += int(size * 1.12)
    subtitle = (subtitle or "").replace("·", "-").replace("–", "-")
    if subtitle and d.textlength(subtitle, font=small) > W - 2 * pad:
        while subtitle and d.textlength(subtitle + "...", font=small) > W - 2 * pad: subtitle = subtitle[:-1]
        subtitle = subtitle.rstrip() + "..."
    if subtitle:
        d.text((pad, H - pad - 40), subtitle, font=small, fill="#D9E3E6")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return True
