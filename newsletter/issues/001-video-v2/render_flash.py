"""Sensational cut of Nordic Crypto #1.

Same spoken facts and sign-off as the newsreel. Pictures are a
faster, louder house style: hyperspace streaks, light flashes, kinetic wipes
and original space-kitten cameos. No copyrighted theme music or footage.

Usage (after build/timeline_flash.json exists):
    python3 render_flash.py SEG
    python3 render_flash.py SEG --still T out.png
"""
import math
import os
import random

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('TIMELINE', 'build/timeline_flash.json')
os.environ.setdefault('SEGDIR', 'build/flash/')
os.makedirs(os.environ['SEGDIR'], exist_ok=True)

import render as R


def draw_kitten(d, x, y, s, phase=0.0):
    """Original space kitten: ears, visor, a small engine glow. Not a licensed character."""
    x, y, s = int(x), int(y), max(8, int(s))
    bob = int(math.sin(phase * 6.0) * s * 0.06)
    y += bob
    # engine glow (a soft jet, not a blast)
    d.ellipse((x - int(s * 1.55), y - int(s * 0.15), x - int(s * 0.15), y + int(s * 0.45)), fill=(70, 150, 255))
    d.ellipse((x - int(s * 1.15), y - int(s * 0.02), x - int(s * 0.35), y + int(s * 0.28)), fill=(190, 230, 255))
    # ears stick out of the helmet
    eh = int(s * 0.62)
    d.polygon([(x - int(s * 0.58), y - int(s * 0.15)),
               (x - int(s * 0.30), y - int(s * 0.95) - eh),
               (x - int(s * 0.02), y - int(s * 0.28))], fill=(255, 214, 186))
    d.polygon([(x + int(s * 0.58), y - int(s * 0.15)),
               (x + int(s * 0.30), y - int(s * 0.95) - eh),
               (x + int(s * 0.02), y - int(s * 0.28))], fill=(255, 214, 186))
    d.polygon([(x - int(s * 0.48), y - int(s * 0.22)),
               (x - int(s * 0.30), y - int(s * 0.85) - int(eh * 0.55)),
               (x - int(s * 0.12), y - int(s * 0.28))], fill=(255, 170, 176))
    d.polygon([(x + int(s * 0.48), y - int(s * 0.22)),
               (x + int(s * 0.30), y - int(s * 0.85) - int(eh * 0.55)),
               (x + int(s * 0.12), y - int(s * 0.28))], fill=(255, 170, 176))
    # helmet
    d.ellipse((x - s, y - int(s * 0.92), x + s, y + int(s * 1.05)), fill=(226, 236, 246), outline=(30, 60, 100), width=max(2, s // 16))
    # face
    d.ellipse((x - int(s * 0.64), y - int(s * 0.40), x + int(s * 0.64), y + int(s * 0.62)), fill=(255, 226, 204))
    # visor glass
    d.pieslice((x - int(s * 0.78), y - int(s * 0.58), x + int(s * 0.78), y + int(s * 0.55)), 200, 340, fill=(150, 205, 255))
    blink = 0.35 if (int(phase * 1.7) % 7 == 0) else 1.0
    ey = y - int(s * 0.02)
    for sx in (-1, 1):
        ex = x + sx * int(s * 0.26)
        d.ellipse((ex - int(s * 0.13), ey - int(s * 0.15 * blink), ex + int(s * 0.13), ey + int(s * 0.15)), fill=(24, 32, 48))
        if blink > 0.7:
            d.ellipse((ex - int(s * 0.05), ey - int(s * 0.08), ex + int(s * 0.01), ey - int(s * 0.01)), fill=R.WHITE)
    d.polygon([(x, y + int(s * 0.16)), (x - int(s * 0.07), y + int(s * 0.26)), (x + int(s * 0.07), y + int(s * 0.26))], fill=(230, 130, 140))
    d.arc((x - int(s * 0.18), y + int(s * 0.22), x + int(s * 0.18), y + int(s * 0.42)), 15, 165, fill=(90, 50, 55), width=max(2, s // 22))
    d.arc((x - int(s * 0.72), y - int(s * 0.72), x + int(s * 0.15), y + int(s * 0.2)), 210, 300, fill=R.WHITE, width=max(2, s // 14))


def hyperspace(d, t, power=1.0, n=130):
    cx, cy = R.W / 2, R.H / 2 - 10
    for i in range(n):
        ang = (i * 2.399963) % (2 * math.pi)
        cyc = (t * power * 0.62 + i * 0.0137) % 1.0
        z = max(0.05, 1.0 - cyc)
        rad = (1.0 - z) ** 1.35 * 1080
        stretch = 8 + (1.0 - z) * 80 * power
        co, si = math.cos(ang), math.sin(ang)
        x = cx + co * rad
        y = cy + si * rad * 0.58
        x2 = cx + co * (rad + stretch)
        y2 = cy + si * (rad + stretch) * 0.58
        bri = int(110 + 145 * (1.0 - z))
        d.line((x, y, x2, y2), fill=(bri, bri, min(255, bri + 28)), width=1 if z > 0.4 else 2)


def light_hit(im, t, hits, width=0.10, amt=0.20):
    flash = 0.0
    for h in hits:
        flash = max(flash, R.clamp(1 - abs(t - h) / width))
    if flash <= 0:
        return im
    return R.Image.blend(im, R.Image.new('RGB', (R.W, R.H), (210, 230, 255)), amt * flash)


def seg_bumper(s):
    def frame(t, T):
        im = R.Image.new('RGB', (R.W, R.H), (1, 3, 10))
        d = R.ImageDraw.Draw(im)
        # slow starfield under the jump
        for i in range(70):
            x = (i * 137 + int(t * (18 + i % 5))) % R.W
            y = (i * 89) % R.H
            r = 2 if i % 9 == 0 else 1
            col = R.GOLD if i % 8 == 0 else R.WHITE
            d.ellipse((x, y, x + r, y + r), fill=col)
        power = 0.35 + 1.8 * R.eo(t / 2.4)
        hyperspace(d, t, power, 150)
        cx = R.W / 2
        # Plate so the title stays readable over the streaks. Beam sits under the words, not through them.
        title_y = 360
        if t > 2.15:
            u = R.eo((t - 2.15) / 0.28)
            d.rectangle((cx - int(860 * u), 320, cx + int(860 * u), 720), fill=(2, 6, 16))
            d.rectangle((cx - int(860 * u), 530, cx + int(860 * u), 542), fill=R.GOLD)
        if t > 2.3:
            f = R.F('cb', 150)
            u = R.eback((t - 2.3) / 0.5)
            w1 = R.tw(d, 'NORDIC', f)
            w2 = R.tw(d, 'CRYPTO', f)
            gap = 36
            x0 = (R.W - (w1 + gap + w2)) / 2
            d.text((x0 - (1 - u) * 1000, title_y), 'NORDIC', font=f, fill=R.WHITE)
            d.text((x0 + w1 + gap + (1 - u) * 1000, title_y), 'CRYPTO', font=f, fill=R.BRIGHT)
        if t > 3.05:
            u = R.eo((t - 3.05) / 0.3)
            tf = R.F('cb', 52)
            txt = 'ISSUE  #1'
            ww = R.spaced_w(txt, tf, 5) + 48
            d.rectangle((cx - ww / 2, 560, cx - ww / 2 + ww * u, 628), fill=R.RED)
            if u > 0.65:
                R.spaced(d, (cx - ww / 2 + 24, 566), txt, tf, R.WHITE, 5)
        if t > 3.45:
            u = R.eo((t - 3.45) / 0.35)
            sf = R.F('cx', 40)
            txt = 'BREAKING  ·  NEWS FROM THE NORDICS'
            ww = R.tw(d, txt, sf)
            col = R.GOLD if u > 0.95 else tuple(int(c * u) for c in R.GOLD)
            d.text((cx - ww / 2, 648), txt, font=sf, fill=col)
        # Kittens stay in the top and bottom bands so they don't cover the title.
        if 0.85 < t < 4.15:
            p = (t - 0.85) / 3.3
            draw_kitten(d, -140 + p * (R.W + 220), 150 + math.sin(t * 3) * 16, 56, t)
            draw_kitten(d, R.W + 100 - p * (R.W + 200), 900 + math.cos(t * 2.5) * 12, 52, t + 0.6)
        elif t >= 4.15:
            draw_kitten(d, 210 + math.sin(t) * 8, 860, 72, t)
            draw_kitten(d, R.W - 210 + math.cos(t) * 8, 860, 66, t + 1.1)
        im = light_hit(im, t, (1.65, 2.72, 5.55), 0.09, 0.16)
        if t < 0.25:
            im = R.Image.blend(R.Image.new('RGB', (R.W, R.H), (0, 0, 0)), im, t / 0.25)
        return im
    return frame, dict(bugs=False)


def seg_section(s):
    def frame(t, T):
        im = R.Image.new('RGB', (R.W, R.H), R.NAVY2)
        d = R.ImageDraw.Draw(im)
        hyperspace(d, t * 1.6, 2.4, 110)
        for i in range(10):
            y = (i * 97 + 30) % R.H
            x = ((t * 3800 + i * 430) % (R.W + 1400)) - 700
            d.line((R.W - x, y, R.W - x + 280, y), fill=(40, 120, 210), width=2)
        u = R.eo((t - 0.02) / 0.32)
        sl = 220
        x1 = R.W - u * (R.W + 200)
        d.polygon([(x1 + sl, 300), (R.W + 400, 300), (R.W + 400 - sl, 780), (x1, 780)], fill=R.RED)
        d.polygon([(x1 + sl - 50, 300), (x1 + sl, 300), (x1, 780), (x1 - 50, 780)], fill=R.WHITE)
        tf = R.fit(s['label'], 'cb', 210, 1500, 100)
        lw = R.spaced_w(s['label'], tf, 8)
        v = R.eo((t - 0.12) / 0.36)
        x = R.W / 2 - lw / 2 + (1 - v) * 1500
        if v > 0:
            R.spaced(d, (x, 390), s['label'], tf, R.WHITE, 8)
        a = R.eo((t - 0.38) / 0.3)
        if a > 0:
            sf = R.F('cs', 48)
            sw = R.tw(d, s['sub'], sf)
            d.rectangle((R.W / 2 - sw / 2 - 30, 800, R.W / 2 - sw / 2 - 30 + (sw + 60) * a, 868), fill=R.BLUE)
            if a > 0.75:
                d.text((R.W / 2 - sw / 2, 806), s['sub'], font=sf, fill=R.WHITE)
        p = t / max(0.4, s['dur'])
        draw_kitten(d, -100 + p * (R.W + 220), 168, 40, t)
        return light_hit(im, t, (0.18,), 0.08, 0.12)
    return frame, {}


_story = R.seg_story
def seg_story(s):
    fr, opts = _story(s)
    fly = s['name'] in ('s5', 's8')
    def frame(t, T):
        im = fr(t, T)
        d = R.ImageDraw.Draw(im)
        u = (t * 0.55) % 1.0
        x = int(140 + u * 980)
        d.line((x, 280, x, 700), fill=(170, 210, 255), width=2)
        if fly:
            p = t / max(s['dur'], 0.1)
            draw_kitten(d, -130 + p * (R.W + 260), 148 + math.sin(t * 4) * 10, 40, t)
        return im
    return frame, opts


_sponsor = R.seg_sponsor
def seg_sponsor(s):
    fr, opts = _sponsor(s)
    def frame(t, T):
        im = fr(t, T)
        d = R.ImageDraw.Draw(im)
        p = R.clamp(t / max(s['dur'], 0.1))
        draw_kitten(d, -120 + p * (R.W * 0.55), 150, 48, t)
        draw_kitten(d, R.W + 80 - p * (R.W * 0.5), 150, 44, t + 0.8)
        return light_hit(im, t, (0.35,), 0.1, 0.1)
    return frame, opts


_title = R.seg_title
def seg_title(s):
    fr, opts = _title(s)
    def frame(t, T):
        im = fr(t, T)
        d = R.ImageDraw.Draw(im)
        # Stars only in the top margin so they don't cross the title.
        for i in range(28):
            x = (i * 73 + int(t * 80)) % R.W
            y = 28 + (i % 4) * 16
            d.ellipse((x, y, x + 2, y + 2), fill=R.GOLD if i % 5 == 0 else R.WHITE)
        return im
    return frame, opts


_bokeh = R.bokeh_bg
def bokeh_bg(seed=3, tint=(9, 30, 66)):
    im = _bokeh(seed, tint)
    d = R.ImageDraw.Draw(im)
    rng = random.Random(seed + 17)
    for i in range(120):
        x = rng.randint(0, R.BW_ - 2)
        y = rng.randint(0, R.BH_ - 2)
        r = 2 if i % 7 == 0 else 1
        col = (255, 214, 90) if i % 6 == 0 else (235, 242, 255)
        d.ellipse((x, y, x + r, y + r), fill=col)
    return im


_art = R.art_bg
def art_bg(st):
    im = _art(st)
    d = R.ImageDraw.Draw(im)
    rng = random.Random(hash(st['big']) & 0xffffffff)
    for i in range(60):
        x = rng.randint(1080, R.BW_ - 4)
        y = rng.randint(30, 980)
        r = 2 if i % 5 == 0 else 1
        d.ellipse((x, y, x + r, y + r), fill=(255, 255, 255) if i % 4 else R.GOLD)
    return im


def _flash_band(base, p):
    # Sharper wipe than the newsreel: extra gold edge on the same navy band.
    R._news_band(base, p)
    if p <= 0 or p >= 1:
        return
    d = R.ImageDraw.Draw(base)
    BW = 2500
    sl = 260
    x = -BW - sl + p * (R.W + BW + 2 * sl)
    d.polygon([(x + BW + sl + 70, 0), (x + BW + sl + 92, 0), (x + BW + 92, R.H), (x + BW + 70, R.H)], fill=R.GOLD)


def apply():
    R.WIPE = 0.22
    R.TICK_SPEED = 220
    R._news_band = R.draw_band
    R.draw_band = _flash_band
    R.bokeh_bg = bokeh_bg
    R.art_bg = art_bg
    R.KINDS['bumper'] = seg_bumper
    R.KINDS['section'] = seg_section
    R.KINDS['story'] = seg_story
    R.KINDS['sponsor'] = seg_sponsor
    R.KINDS['title'] = seg_title


apply()

if __name__ == '__main__':
    R.main()
