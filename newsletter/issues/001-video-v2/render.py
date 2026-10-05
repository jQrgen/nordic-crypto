"""Newsreel renderer for Nordic Crypto #1 (v2). PIL frames -> ffmpeg (-threads 1). One segment per process.
usage: render.py SEG            -> $SEGDIR/v_SEG.mp4
       render.py SEG --still T  -> still frame at local time T
       render.py thumb          -> thumbnail.png
Env: TIMELINE (json path), SEGDIR (segment mp4 directory). Voice JSON stays in build/."""
import os, sys, json, math, random, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.'); import content as C
W, H = 1920, 1080
ROOT = 'build/'
SEGDIR = os.environ.get('SEGDIR', ROOT)
os.makedirs(SEGDIR, exist_ok=True)
G = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts') + os.sep
FONTS = {'cb': G + 'BarlowCondensed-Black.ttf', 'cx': G + 'BarlowCondensed-ExtraBold.ttf',
         'cs': G + 'BarlowCondensed-SemiBold.ttf', 'cm': G + 'BarlowCondensed-Medium.ttf',
         'b': G + 'Barlow-Bold.ttf', 'r': G + 'Barlow-Regular.ttf', 'm': G + 'Barlow-Medium.ttf', 'k': G + 'Barlow-Black.ttf'}
_fc = {}
def F(k, s):
    if (k, s) not in _fc: _fc[(k, s)] = ImageFont.truetype(FONTS[k], s)
    return _fc[(k, s)]
NAVY = (6, 20, 43); NAVY2 = (2, 8, 20); BLUE = (15, 94, 168); BRIGHT = (29, 140, 255); RED = (214, 40, 40); WHITE = (255, 255, 255)
GOLD = (242, 183, 5); INK = (12, 18, 30); GREY = (170, 182, 200)
def clamp(x, a=0., b=1.): return max(a, min(b, x))
def eo(x): x = clamp(x); return 1 - (1 - x) ** 3
def eio(x): x = clamp(x); return 3 * x * x - 2 * x * x * x
def eback(x, s=1.6): x = clamp(x); x -= 1; return x * x * ((s + 1) * x + s) + 1
def tw(d, txt, f): b = d.textbbox((0, 0), txt, font=f); return b[2] - b[0]
DUMMY = ImageDraw.Draw(Image.new('L', (1, 1)))
def fit(txt, k, start, maxw, mn=20):
    s = start
    while s > mn and tw(DUMMY, txt, F(k, s)) > maxw: s -= 2
    return F(k, s)
def wrap(txt, f, maxw):
    out, cur = [], ''
    for w in txt.split():
        t = (cur + ' ' + w).strip()
        if cur and tw(DUMMY, t, f) > maxw: out.append(cur); cur = w
        else: cur = t
    return out + [cur]
def spaced(d, xy, txt, f, fill, sp=2):
    x, y = xy
    for ch in txt: d.text((x, y), ch, font=f, fill=fill); x += tw(d, ch, f) + sp if ch != ' ' else tw(d, 'n', f) * .6 + sp
    return x
def spaced_w(txt, f, sp=2): return sum((tw(DUMMY, c, f) + sp) if c != ' ' else tw(DUMMY, 'n', f) * .6 + sp for c in txt)
def mark(d, x, y, s):  # brand mark: blue square with Nordic cross
    d.rectangle((x, y, x + s, y + s), fill=BLUE); d.rectangle((x + s * .25, y, x + s * .44, y + s), fill=WHITE)
    d.rectangle((x, y + s * .405, x + s, y + s * .595), fill=WHITE)
def grad(w, h, top, bot):
    g = Image.linear_gradient('L').resize((w, h)); return Image.composite(Image.new('RGB', (w, h), bot), Image.new('RGB', (w, h), top), g)
def star(d, cx, cy, r, fill):
    pts = [(cx + (r if i % 2 == 0 else r * .4) * math.sin(i * math.pi / 5), cy - (r if i % 2 == 0 else r * .4) * math.cos(i * math.pi / 5)) for i in range(10)]
    d.polygon(pts, fill=fill)

TL = json.load(open(os.environ.get('TIMELINE', ROOT + 'timeline.json'))); FPS = TL['fps']; SEGS = {s['name']: s for s in TL['segs']}
def sentences(name):
    try: return json.load(open(ROOT + name + '.json'))
    except FileNotFoundError: return []
def cue_at(sents, voff, needle):
    n = needle.lower()
    for a, _z, txt in sents:
        if n in txt.lower(): return voff + a
    return None

# ---------- persistent overlays ----------
def make_bug():
    im = Image.new('RGBA', (500, 112), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 500, 66), fill=(4, 12, 28, 215)); mark(d, 12, 11, 44)
    d.text((70, 6), 'NORDIC', font=F('cb', 44), fill=WHITE); x = 70 + tw(d, 'NORDIC ', F('cb', 44))
    d.text((x, 6), 'CRYPTO', font=F('cb', 44), fill=BRIGHT)
    return im
def draw_clock(base, T):
    d = ImageDraw.Draw(base, 'RGBA'); x0, y0 = 1500, 40
    d.rectangle((x0, y0, 1860, y0 + 66), fill=(4, 12, 28, 215))
    pulse = 0.5 + 0.5 * math.cos(T * 2 * math.pi * 0.8); r = 9
    d.ellipse((x0 + 18 - r, y0 + 33 - r, x0 + 18 + r, y0 + 33 + r), fill=(int(150 + 105 * pulse), 30, 30, 255))
    d.text((x0 + 38, y0 + 10), 'OSLO', font=F('cx', 40), fill=GREY)
    sec = int(T); hh, mm, ss = 19, sec // 60, sec % 60
    d.text((x0 + 130, y0 + 8), f'{hh:02d}:{mm:02d}:{ss:02d}', font=F('cx', 44), fill=WHITE)
    d.text((x0 + 300, y0 + 18), 'CET' if False else 'CEST', font=F('cs', 26), fill=GREY)
    d.rectangle((x0, y0 + 70, 1860, y0 + 104), fill=(15, 94, 168, 235))
    spaced(d, (x0 + 14, y0 + 73), 'ISSUE #1 · 27 SEP – 2 OCT 2026', F('cs', 23), WHITE, 1.5)
TICK_Y, TICK_H, TICK_SPEED = 1012, 68, 140
def make_ticker():
    f = F('cs', 36); parts = []
    for it in C.TICKER: parts.append(it)
    widths = [tw(DUMMY, p, f) for p in parts]; gap = 90; L = sum(widths) + gap * len(parts)
    strip = Image.new('RGB', (int(L) + W, TICK_H), (240, 242, 246)); d = ImageDraw.Draw(strip)
    x = 0
    for rep in range(2):
        for p, w in zip(parts, widths):
            if x > L + W: break
            d.text((x, 12), p, font=f, fill=INK); x += w + gap / 2
            cx, cy = x - 4, TICK_H / 2; d.polygon([(cx, cy - 11), (cx + 11, cy), (cx, cy + 11), (cx - 11, cy)], fill=RED); x += gap / 2
    lab = Image.new('RGB', (290, TICK_H), RED); dl = ImageDraw.Draw(lab)
    dl.text((22, 8), 'HEADLINES', font=F('cb', 44), fill=WHITE); dl.polygon([(262, 0), (290, 0), (290, TICK_H), (262 + 0, TICK_H)], fill=(160, 20, 20))
    return strip, int(L), lab
def draw_ticker(base, T, strip, L, lab, yoff=0):
    off = int(T * TICK_SPEED) % L
    base.paste(strip.crop((off, 0, off + W - 290, TICK_H)), (290, TICK_Y + yoff)); base.paste(lab, (0, TICK_Y + yoff))
    ImageDraw.Draw(base).rectangle((0, TICK_Y + yoff - 5, W, TICK_Y + yoff - 1), fill=BLUE)
def draw_band(base, p):  # wipe band; p 0..1 across a cut (covers screen at p=.5)
    if p <= 0 or p >= 1: return
    d = ImageDraw.Draw(base); BW = 2500; sl = 260; x = -BW - sl + p * (W + BW + 2 * sl)
    d.polygon([(x + sl, 0), (x + BW + sl, 0), (x + BW, H), (x, H)], fill=NAVY)
    d.polygon([(x + BW - 30 + sl, 0), (x + BW + sl + 40, 0), (x + BW + 40, H), (x + BW - 30, H)], fill=RED)
    d.polygon([(x + BW + sl + 40, 0), (x + BW + sl + 70, 0), (x + BW + 70, H), (x + BW + 40, H)], fill=WHITE)
    d.polygon([(x + sl - 60, 0), (x + sl, 0), (x, H), (x - 60, H)], fill=BLUE)
    if 0.3 < p < 0.7:  # brand mark rides the band
        s = 160; mark(d, int(x + BW / 2 + sl / 2 - s / 2), H // 2 - s // 2, s)
WIPE = 0.36  # seconds each side of a cut

# ---------- backgrounds ----------
BW_, BH_ = 2112, 1188
def kb(img, u, dirx=1, diry=0):  # Ken Burns: zoom from 1.0 to 1.1, gentle pan
    u = eio(u); bw = BW_ / (1 + 0.1 * u); bh = bw * 9 / 16
    cx = BW_ / 2 + dirx * (BW_ - bw) / 2 * (u * 2 - 1) * 0.8; cy = BH_ / 2 + diry * (BH_ - bh) / 2 * (u * 2 - 1) * 0.8
    return img.resize((W, H), Image.BILINEAR, box=(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2))
def base_bg(tint=None):
    im = grad(BW_, BH_, (9, 30, 66) if not tint else tint, NAVY2); d = ImageDraw.Draw(im)
    for x in range(0, BW_, 96): d.line((x, 0, x, BH_), fill=(18, 42, 80), width=1)
    for y in range(0, BH_, 96): d.line((0, y, BW_, y), fill=(18, 42, 80), width=1)
    return im
def glow_layer(draw_fn, blur=14):
    lay = Image.new('RGBA', (BW_, BH_), (0, 0, 0, 0)); draw_fn(ImageDraw.Draw(lay))
    g = lay.filter(ImageFilter.GaussianBlur(blur)); out = Image.alpha_composite(g, lay); del g; return out
def art_bg(st):
    random.seed(st['big']); tint = (60, 14, 22) if st['art'] == 'scan' else None
    im = base_bg(tint).convert('RGBA'); cx, cy = 1530, 540
    def motif(d):
        a = st['art']
        if a == 'stars':
            d.ellipse((cx - 330, cy - 330, cx + 330, cy + 330), outline=(29, 140, 255, 90), width=3)
            for i in range(12): ang = i * math.pi / 6; star(d, cx + 260 * math.sin(ang), cy - 260 * math.cos(ang), 34, GOLD + (255,))
            d.ellipse((cx - 120, cy - 120, cx + 120, cy + 120), outline=(255, 255, 255, 120), width=2)
        elif a == 'globe':
            r = 320; d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BRIGHT + (220,), width=4)
            for k in range(1, 6):
                rx = r * math.cos(k * math.pi / 12); d.ellipse((cx - rx, cy - r, cx + rx, cy + r), outline=BRIGHT + (110,), width=2)
            for k in range(-4, 5):
                yy = cy + r * math.sin(k * math.pi / 10); hw = r * math.cos(k * math.pi / 10); d.line((cx - hw, yy, cx + hw, yy), fill=BRIGHT + (110,), width=2)
            for _ in range(7):
                a2 = random.uniform(0, 2 * math.pi); rr = random.uniform(0, r * .85); x, y = cx + rr * math.cos(a2), cy + rr * math.sin(a2)
                d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=RED + (255,)); d.ellipse((x - 22, y - 22, x + 22, y + 22), outline=RED + (160,), width=2)
        elif a == 'bars':
            for i in range(6):
                x = cx - 330 + i * 125; hgt = 3 + (i * 7 + 3) % 9
                for j in range(hgt):
                    y = cy + 300 - j * 38
                    d.ellipse((x - 50, y - 16, x + 50, y + 16), fill=(150, 110, 0, 255), outline=GOLD + (255,), width=3)
                    d.ellipse((x - 50, y - 22, x + 50, y + 10), fill=GOLD + (255,), outline=(255, 220, 110, 255), width=2)
        elif a == 'nodes':
            pts = [(cx + random.uniform(-380, 380), cy + random.uniform(-330, 330)) for _ in range(20)]
            for i, p in enumerate(pts):
                for q in pts[i + 1:]:
                    if math.dist(p, q) < 260: d.line((*p, *q), fill=BRIGHT + (140,), width=3)
            for i, (x, y) in enumerate(pts):
                r = 12 if i % 4 else 22; d.ellipse((x - r, y - r, x + r, y + r), fill=(WHITE if i % 3 else GOLD) + (255,))
        elif a == 'scan':
            for r in (110, 210, 310): d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 90, 90, 150), width=3)
            d.line((cx - 380, cy, cx + 380, cy), fill=(255, 90, 90, 160), width=2); d.line((cx, cy - 380, cx, cy + 380), fill=(255, 90, 90, 160), width=2)
            d.pieslice((cx - 310, cy - 310, cx + 310, cy + 310), -70, -20, fill=(255, 60, 60, 70))
            for _ in range(5):
                a2 = random.uniform(0, 2 * math.pi); rr = random.uniform(60, 290); x, y = cx + rr * math.cos(a2), cy + rr * math.sin(a2)
                d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=(255, 210, 210, 255))
    im = Image.alpha_composite(im, glow_layer(motif)); d = ImageDraw.Draw(im)
    # headline typography (left), keep out of lower-third area (screen y<760 -> art y<~800)
    kf = F('cx', 46); kw = spaced_w(st['kicker'], kf, 3)
    d.rectangle((200, 300, 200 + kw + 40, 366), fill=RED); spaced(d, (220, 304), st['kicker'], kf, WHITE, 3)
    bf = fit(st['big'], 'cb', 250, 980, 90); d.text((196, 360), st['big'], font=bf, fill=WHITE)
    d.rectangle((200, 640, 420, 652), fill=BRIGHT)
    return im.convert('RGB')
def bokeh_bg(seed=3, tint=(9, 30, 66)):
    random.seed(seed); im = grad(BW_, BH_, tint, NAVY2).convert('RGBA')
    lay = Image.new('RGBA', (BW_ // 4, BH_ // 4), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for _ in range(40):
        x, y, r = random.uniform(0, BW_ / 4), random.uniform(0, BH_ / 4), random.uniform(8, 40)
        c = random.choice([BRIGHT, BLUE, (90, 160, 255), RED if random.random() < .15 else BLUE])
        d.ellipse((x - r, y - r, x + r, y + r), fill=c + (random.randint(40, 110),))
    lay = lay.filter(ImageFilter.GaussianBlur(6)).resize((BW_, BH_), Image.BILINEAR)
    return Image.alpha_composite(im, lay).convert('RGB')

# ---------- lower third ----------
def make_lt(st):
    f = fit(st['head'], 'cs', 62, 1640, 46); lines = [st['head']] if tw(DUMMY, st['head'], f) <= 1640 else wrap(st['head'], F('cs', 50), 1640)
    if len(lines) > 1: f = F('cs', 50)
    hh = 34 + len(lines) * (f.size + 6)
    head = Image.new('RGB', (1740, hh), WHITE); d = ImageDraw.Draw(head)
    for i, ln in enumerate(lines): d.text((40, 12 + i * (f.size + 6)), ln, font=f, fill=INK)
    d.rectangle((0, 0, 12, hh), fill=RED)
    tf = F('cb', 40); tag = Image.new('RGB', (int(spaced_w(st['section'], tf, 3)) + 44, 56), RED); spaced(ImageDraw.Draw(tag), (22, 4), st['section'], tf, WHITE, 3)
    sf = F('cs', 30); src = Image.new('RGB', (int(tw(DUMMY, 'SOURCE  ' + st['src'], sf)) + 60, 46), BLUE); ds = ImageDraw.Draw(src)
    ds.text((22, 6), 'SOURCE', font=F('cx', 30), fill=(190, 220, 255)); ds.text((22 + tw(ds, 'SOURCE  ', F('cx', 30)), 6), st['src'], font=sf, fill=WHITE)
    return tag, head, src
def draw_lt(base, lt, t, dur):
    tag, head, src = lt; x0 = 90; ybot = 994; ys = ybot - src.height; yh = ys - head.height; yt = yh - tag.height
    out = clamp((t - (dur - 0.5)) / 0.35)  # slide out before the wipe
    a = eo((t - 0.35) / 0.4) * (1 - eio(out))
    if a > 0: base.paste(tag, (int(x0 - (1 - a) * (tag.width + 120)), yt))
    b = eo((t - 0.55) / 0.5) * (1 - eio(out))
    if b > 0:
        wv = int(head.width * b)
        if wv > 0: base.paste(head.crop((0, 0, wv, head.height)), (x0, yh))
    c = eo((t - 0.95) / 0.4) * (1 - eio(out))
    if c > 0: base.paste(src.crop((0, 0, src.width, int(src.height * c)) if c < 1 else (0, 0, src.width, src.height)), (x0, ys))

# ---------- segment renderers ----------
def seg_bumper(s):
    logo_big = Image.new('RGBA', (1400, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(logo_big)
    def frame(t, T):
        im = Image.new('RGB', (W, H), NAVY2); d = ImageDraw.Draw(im); cx, cy = W / 2, H / 2 - 40
        rot = t * 0.35; flash = clamp(1 - abs(t - 3.0) / 0.25)
        for i in range(24):  # rotating sunburst
            a0 = rot + i * 2 * math.pi / 24; a1 = a0 + math.pi / 24
            c = (10 + int(20 * flash), 34 + int(30 * flash), 74 + int(40 * flash)) if i % 2 == 0 else NAVY2
            d.polygon([(cx, cy), (cx + 2400 * math.cos(a0), cy + 2400 * math.sin(a0)), (cx + 2400 * math.cos(a1), cy + 2400 * math.sin(a1))], fill=c)
        for k in range(5):  # expanding rings
            r = ((t * 420 + k * 260) % 1300); w_ = max(1, int(6 * (1 - r / 1300)))
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(29, 140, 255), width=w_)
        # globe grid behind logo
        r = 250 * eo((t - 0.2) / 0.8)
        if r > 2:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(60, 150, 255), width=3)
            for k in range(1, 5):
                ph = (t * 0.8 + k / 5) % 1; rx = r * math.cos(ph * math.pi); rx = abs(rx)
                d.ellipse((cx - rx, cy - r, cx + rx, cy + r), outline=(40, 110, 200), width=2)
            for k in (-2, -1, 0, 1, 2):
                yy = cy + r * k / 3; hw = math.sqrt(max(0, r * r - (r * k / 3) ** 2)); d.line((cx - hw, yy, cx + hw, yy), fill=(40, 110, 200), width=2)
        sz = 200 * eback((t - 1.0) / 0.5)
        if sz > 4: mark(d, cx - sz / 2, cy - sz / 2, sz)
        f = F('cb', 190)
        if t > 1.9:
            u = eo((t - 1.9) / 0.5); w1 = tw(d, 'NORDIC', f); w2 = tw(d, 'CRYPTO', f); y = cy + 150
            d.text((cx - 20 - w1 - (1 - u) * 1200, y), 'NORDIC', font=f, fill=WHITE); d.text((cx + 20 + (1 - u) * 1200, y), 'CRYPTO', font=f, fill=BRIGHT)
        if t > 3.0:
            u = eo((t - 3.0) / 0.4); sf = F('cx', 50); txt = 'CRYPTO NEWS FROM THE NORDICS'; ww = spaced_w(txt, sf, 6)
            d.rectangle((cx - ww / 2 - 30, cy + 385, cx - ww / 2 - 30 + (ww + 60) * u, cy + 450), fill=RED)
            if u > .6: spaced(d, (cx - ww / 2, cy + 388), txt, sf, WHITE, 6)
        if flash > 0:  # white flash on the final chord
            im = Image.blend(im, Image.new('RGB', (W, H), WHITE), 0.55 * flash)
        if t < 0.3: im = Image.blend(Image.new('RGB', (W, H), (0, 0, 0)), im, t / 0.3)
        return im
    return frame, dict(bugs=False)
def seg_title(s):
    bg = bokeh_bg(11); sents = sentences(s['name'])
    stripes = Image.new('L', (W * 2, H), 0); ds = ImageDraw.Draw(stripes)
    for i in range(0, W * 2, 240): ds.polygon([(i, 0), (i + 90, 0), (i + 90 - 400, H), (i - 400, H)], fill=26)
    def frame(t, T):
        im = kb(bg, t / (s['dur'])); off = int(t * 60) % 240
        im.paste((60, 140, 255), (0, 0), stripes.crop((off, 0, off + W, H)))
        d = ImageDraw.Draw(im); cx = W / 2
        u = eback((t - 0.1) / 0.6); sz = 150 * u
        if sz > 3: mark(d, cx - sz / 2, 250 - sz / 2 + 75, sz)
        f = F('cb', 180); u2 = eo((t - 0.4) / 0.6); w1 = tw(d, 'NORDIC ', f); w2 = tw(d, 'CRYPTO', f); x = cx - (w1 + w2) / 2
        d.text((x - (1 - u2) * 300, 400), 'NORDIC', font=f, fill=WHITE); d.text((x + w1 + (1 - u2) * 300, 400), 'CRYPTO', font=f, fill=BRIGHT)
        u3 = eo((t - 0.9) / 0.5)
        if u3 > 0:
            tf = F('cb', 60); txt = 'ISSUE #1'; ww = spaced_w(txt, tf, 4) + 60
            d.rectangle((cx - ww / 2, 660, cx - ww / 2 + ww * u3, 735), fill=RED)
            if u3 > .7: spaced(d, (cx - ww / 2 + 30, 663), txt, tf, WHITE, 4)
        u4 = eo((t - 1.3) / 0.5)
        if u4 > 0:
            df = F('cx', 58); txt = C.DATES; ww = tw(d, txt, df); d.text((cx - ww / 2, 760 + (1 - u4) * 40), txt, font=df, fill=WHITE if u4 > .99 else (int(255 * u4),) * 3)
        u5 = eo((t - 1.7) / 0.45)
        if u5 > 0:
            nf = F('cs', 40); txt = 'CRYPTO, BITCOIN AND BLOCKCHAIN NEWS FROM THE NORDICS'; ww = tw(d, txt, nf) + 50
            d.rectangle((cx - ww / 2, 860, cx + ww / 2, 860 + 58 * u5), fill=(4, 12, 28))
            if u5 > .8: d.text((cx - ww / 2 + 25, 868), txt, font=nf, fill=GOLD)
        return im
    return frame, {}
def seg_tonight(s):
    bg = bokeh_bg(5); sents = sentences(s['name']); vo = s['voff']
    heads = ["Binance under scrutiny over Europe's new crypto rules", "Sweden's financial watchdog issues a crypto sanctions warning", "The meetups coming up across the region"]
    tags = ['TOP STORY', 'REGULATION', 'ON THE CALENDAR']
    st = [vo + x[0] for x in sents] + [99] * 6
    countries = ['NORWAY', 'SWEDEN', 'DENMARK', 'FINLAND', 'ICELAND']
    def frame(t, T):
        im = kb(bg, t / s['dur'], -1); d = ImageDraw.Draw(im)
        phase2 = t >= st[3] - 0.2
        if not phase2:
            u = eo(t / 0.5); tf = F('cb', 96); d.rectangle((140 - (1 - u) * 700, 190, 140 - (1 - u) * 700 + 430, 310), fill=RED)
            spaced(d, (170 - (1 - u) * 700, 196), 'TONIGHT', tf, WHITE, 6)
            for i in range(3):
                a = eo((t - st[i] - 0.05) / 0.45)
                if a <= 0: continue
                y = 370 + i * 175; x = 140 + (1 - a) * 1900
                d.rectangle((x, y, x + 1640, y + 140), fill=(4, 12, 28)); d.rectangle((x, y, x + 14, y + 140), fill=BRIGHT)
                d.text((x + 44, y + 14), tags[i], font=F('cx', 34), fill=GOLD)
                d.text((x + 44, y + 52), heads[i], font=fit(heads[i], 'cs', 62, 1560, 40), fill=WHITE)
        else:
            t2 = t - (st[3] - 0.2)
            d.text((140, 200), 'NEWS FROM FIVE COUNTRIES', font=F('cb', 90), fill=WHITE)
            d.text((140, 310), 'Crypto, bitcoin and blockchain news, with a link to every original source', font=F('m', 40), fill=GREY)
            for i, c in enumerate(countries):
                a = eback((t2 - 0.6 - i * 0.55) / 0.4)
                if a <= 0: continue
                x = 140 + i * 330; y = 470; hgt = 230 * a
                d.rectangle((x, y + 230 - hgt, x + 300, y + 230), fill=BLUE)
                if a > .7:
                    mark(d, x + 110, y + 30, 80); cw = tw(d, c, F('cb', 54)); d.text((x + 150 - cw / 2, y + 140), c, font=F('cb', 54), fill=WHITE)
        return im
    return frame, {}
def seg_section(s):
    def frame(t, T):
        im = Image.new('RGB', (W, H), NAVY2); d = ImageDraw.Draw(im)
        for i in range(14):  # speed streaks
            y = (i * 83 + 40) % H; x = ((t * 3200 + i * 517) % (W + 1200)) - 600; d.line((W - x, y, W - x + 400 + i * 20, y), fill=(29, 90, 170), width=3 + i % 3)
        u = eo((t - 0.05) / 0.45); sl = 220
        x1 = W - u * (W + 200)
        d.polygon([(x1 + sl, 300), (W + 400, 300), (W + 400 - sl, 780), (x1, 780)], fill=RED)
        d.polygon([(x1 + sl - 50, 300), (x1 + sl, 300), (x1, 780), (x1 - 50, 780)], fill=WHITE)
        tf = fit(s['label'], 'cb', 230, 1600, 120); lw = spaced_w(s['label'], tf, 8); v = eo((t - 0.25) / 0.5)
        x = W / 2 - lw / 2 + (1 - v) * 1400 - (t - 0.75) * 30 * (t > 0.75)
        if v > 0: spaced(d, (x, 380), s['label'], tf, WHITE, 8)
        a = eo((t - 0.6) / 0.4)
        if a > 0:
            sf = F('cs', 52); sw = tw(d, s['sub'], sf); d.rectangle((W / 2 - sw / 2 - 30, 800, W / 2 - sw / 2 - 30 + (sw + 60) * a, 872), fill=BLUE)
            if a > .8: d.text((W / 2 - sw / 2, 804), s['sub'], font=sf, fill=WHITE)
        return im
    return frame, {}
def seg_story(s):
    st = C.STORIES[s['name']]; bg = art_bg(st); lt = make_lt(st); dirx = 1 if int(s['name'][1]) % 2 else -1
    def frame(t, T):
        im = kb(bg, t / s['dur'], dirx, 0.5); draw_lt(im, lt, t, s['dur']); return im
    return frame, {}
def seg_sponsor(s):
    bg = bokeh_bg(21, (40, 32, 6))
    def frame(t, T):
        im = kb(bg, t / s['dur']); d = ImageDraw.Draw(im); cx = W / 2
        u = eo(t / 0.5); tf = F('cx', 48); txt = 'A NEWS SOURCE WE FOLLOW'; ww = spaced_w(txt, tf, 6)
        spaced(d, (cx - ww / 2, 250 - (1 - u) * 120), txt, tf, GOLD if u > .99 else tuple(int(c * u) for c in GOLD), 8)
        a = eback((t - 0.4) / 0.6); bw, bh = 980 * a, 300 * a
        if a > 0.02:
            d.rectangle((cx - bw / 2, 360 + 150 - bh / 2, cx + bw / 2, 360 + 150 + bh / 2), fill=WHITE)
            d.rectangle((cx - bw / 2, 360 + 150 + bh / 2 - 16 * a, cx + bw / 2, 360 + 150 + bh / 2), fill=GOLD)
            if a > .9:
                kf = F('k', 200); kw = tw(d, 'Kaupr', kf); d.text((cx - kw / 2, 375), 'Kaupr', font=kf, fill=INK)
        b = eo((t - 1.1) / 0.5)
        if b > 0:
            uf = F('cx', 64); uw = tw(d, 'kaupr.io', uf); d.text((cx - uw / 2, 700 + (1 - b) * 40), 'kaupr.io', font=uf, fill=WHITE)
        return im
    return frame, {}
def seg_calendar(s):
    bg = bokeh_bg(8); sents = sentences(s['name']); st = [s['voff'] + x[0] for x in sents]
    def frame(t, T):
        im = kb(bg, t / s['dur'], 1); d = ImageDraw.Draw(im)
        u = eo(t / 0.5); d.rectangle((120 - (1 - u) * 900, 160, 120 - (1 - u) * 900 + 640, 250), fill=RED)
        spaced(d, (145 - (1 - u) * 900, 163), 'ON THE CALENDAR', F('cb', 74), WHITE, 4)
        for i, (dt, city, title, venue) in enumerate(C.EVENTS):
            a = eo((t - st[i] + 0.1) / 0.45) if i < len(st) else 0
            if a <= 0: continue
            y = 280 + i * 124; x = 120 + (1 - a) * 1900; hi = (i == 3)
            d.rectangle((x, y, x + 1680, y + 108), fill=(250, 250, 252) if not hi else (255, 246, 214)); d.rectangle((x, y, x + 210, y + 108), fill=BLUE if not hi else RED)
            dw = tw(d, dt, F('cb', 64)); d.text((x + 105 - dw / 2, y + 16), dt, font=F('cb', 64), fill=WHITE)
            d.text((x + 240, y + 8), title, font=F('cx', 52), fill=INK); d.text((x + 240, y + 64), f'{city}  ·  {venue}', font=F('m', 34), fill=(60, 70, 90))
        disc_t = cue_at(sents, s['voff'], 'disclosure')
        if disc_t is None and len(st) > 4: disc_t = st[4]
        if disc_t is not None:
            a = eo((t - disc_t) / 0.5)
            if a > 0:
                y = 790 + (1 - a) * 300; d.rectangle((120, y, 1800, y + 100), fill=(4, 12, 28)); d.rectangle((120, y, 134, y + 100), fill=GOLD)
                f = F('m', 30); lines = wrap(C.NEXA_DISCLOSURE, f, 1610)
                for k, ln in enumerate(lines[:2]): d.text((160, y + 8 + k * 40), ln, font=f, fill=WHITE)
                d.text((160, y + 8), 'Disclosure (28 Oct):', font=f, fill=GOLD)
        more_t = cue_at(sents, s['voff'], 'more events')
        if more_t is None and len(st) > 6: more_t = st[6]
        if more_t is not None and t >= more_t:
            a = eo((t - more_t) / 0.4); txt = 'More events, including Stockholm and Helsinki in November: ' + C.SITE + '/calendar'
            ff = F('cs', 36); ww = tw(d, txt, ff); d.rectangle((120, 908, 120 + (ww + 50) * a, 966), fill=BLUE)
            if a > .9: d.text((145, 914), txt, font=ff, fill=WHITE)
        return im
    return frame, {}
def seg_end(s):
    bg = bokeh_bg(13); sents = sentences(s['name']); st = [s['voff'] + x[0] for x in sents] + [99] * 6
    def frame(t, T):
        im = kb(bg, t / s['dur'], -1); d = ImageDraw.Draw(im); cx = W / 2
        u = eback((t - 0.1) / 0.6); sz = 110 * u
        if sz > 3: mark(d, cx - sz / 2, 130 + 55 - sz / 2, sz)
        a = eo((t - 0.3) / 0.5); txt = "THAT'S NORDIC CRYPTO FOR THIS WEEK"; tf = fit(txt, 'cb', 110, 1760, 56); ww = tw(d, txt, tf)
        d.text((cx - ww / 2, 265 + (1 - a) * 60), txt, font=tf, fill=WHITE if a > .99 else (int(255 * a),) * 3)
        b = eo((t - st[1]) / 0.5)
        if b > 0:
            l1 = "All the stories, the events calendar and a who's who of Nordic crypto"; f1 = F('m', 40); w1 = tw(d, l1, f1); d.text((cx - w1 / 2, 420), l1, font=f1, fill=GREY)
            f2 = F('cx', 66); w2 = tw(d, C.SITE, f2); d.rectangle((cx - w2 / 2 - 30, 480, cx - w2 / 2 - 30 + (w2 + 60) * b, 570), fill=BLUE)
            if b > .9: d.text((cx - w2 / 2, 486), C.SITE, font=f2, fill=WHITE)
        c = eo((t - st[2]) / 0.5)
        if c > 0:
            l3 = 'Spotted a mistake or a story we missed? Use the tip form: ' + C.SITE + '/tip'; f3 = F('m', 34); w3 = tw(d, l3, f3)
            d.text((cx - w3 / 2, 595 + (1 - c) * 30), l3, font=f3, fill=WHITE)
        team_t = cue_at(sents, s['voff'], 'nordic crypto team')
        if team_t is None: team_t = st[5] if len(sents) > 5 else st[min(4, len(st) - 1)]
        e = eo((t - team_t) / 0.35)
        if e > 0:
            f4 = F('cx', 58); l4 = C.SIGNOFF_CARD; w4 = tw(d, l4, f4); d.text((cx - w4 / 2, 660 + (1 - e) * 30), l4, font=f4, fill=GOLD)
        g = eo((t - 0.8) / 0.5)
        if g > 0:
            f5 = F('r', 28); lines = wrap(C.END_DISCLOSURE, f5, 1560)
            for k, ln in enumerate(lines): lw = tw(d, ln, f5); d.text((cx - lw / 2, 850 + k * 38), ln, font=f5, fill=(200, 210, 225))
        fade = clamp((t - (s['dur'] - 1.2)) / 1.2)
        if fade > 0: im = Image.blend(im, Image.new('RGB', (W, H), (0, 0, 0)), fade)
        return im
    return frame, dict(ticker_out=True, last=True)
KINDS = dict(bumper=seg_bumper, title=seg_title, tonight=seg_tonight, section=seg_section, story=seg_story, sponsor=seg_sponsor, calendar=seg_calendar, end=seg_end)

def compose(s, frame, opts, i, bug, tick):
    t = i / FPS; T = (s['start_f'] + i) / FPS; dur = s['frames'] / FPS
    im = frame(t, T)
    first = s['start_f'] == 0; last = opts.get('last')
    if not first and t < WIPE: draw_band(im, 0.5 + 0.5 * t / WIPE)
    if not last and t > dur - WIPE: draw_band(im, 0.5 * (t - (dur - WIPE)) / WIPE)
    if opts.get('bugs', True):
        fade = clamp((dur - t - 1.2) / 1.2) if last else 1
        if fade > 0:
            yo = int(eio(clamp(t / 0.6)) * 120) if opts.get('ticker_out') else 0
            if yo < 100: draw_ticker(im, T, *tick, yoff=yo)
            im.paste(bug, (60, 40), bug); draw_clock(im, T)
    return im

def main():
    name = sys.argv[1]
    if name == 'thumb': return thumb()
    s = SEGS[name]; frame, opts = KINDS[s['kind']](s); bug = make_bug(); tick = make_ticker()
    if '--still' in sys.argv:
        t = float(sys.argv[sys.argv.index('--still') + 1]); out = sys.argv[sys.argv.index('--still') + 2] if len(sys.argv) > sys.argv.index('--still') + 2 else SEGDIR + f'still_{name}.png'
        compose(s, frame, opts, min(s['frames'] - 1, int(t * FPS)), bug, tick).save(out); print(out); return
    out = os.path.join(SEGDIR, f'v_{name}.mp4')
    logp = os.path.join(SEGDIR, f'ffmpeg_{name}.log')
    # stdin pipe: read stderr from a file so a full pipe cannot deadlock, and surface ffmpeg's
    # real error instead of a bare BrokenPipeError when the encoder exits early.
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{W}x{H}', '-r', str(FPS), '-i', 'pipe:0',
           '-threads', '1', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
           '-x264-params', 'threads=1:sliced-threads=0:lookahead-threads=1:rc-lookahead=8',
           '-pix_fmt', 'yuv420p', '-g', '50', out]
    logf = open(logp, 'w')
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=logf, bufsize=1024 * 1024)
    broken = False
    try:
        for i in range(s['frames']):
            buf = compose(s, frame, opts, i, bug, tick).tobytes()
            try:
                p.stdin.write(buf)
            except BrokenPipeError:
                broken = True
                break
            if (i + 1) % 75 == 0:
                if p.poll() is not None:
                    broken = True
                    break
                print(f'  {name} {i + 1}/{s["frames"]}', flush=True)
    finally:
        try:
            p.stdin.close()
        except Exception:
            pass
        rc = p.wait()
        logf.close()
    if rc != 0 or broken:
        err = open(logp).read()[-2000:]
        raise SystemExit(f'ffmpeg failed on {name} rc={rc}\n{err}')
    print('done', name, s['frames'], 'frames', flush=True)

def thumb():
    st = dict(C.STORIES['s1']); st['big'] = 'BINANCE'; st['kicker'] = 'TOP STORY · ISSUE #1'
    im = art_bg(st).resize((W, H), Image.LANCZOS, box=(96, 54, 96 + 1920, 54 + 1080)); d = ImageDraw.Draw(im)
    # headline bar
    d.rectangle((90, 700, 1830, 900), fill=WHITE); d.rectangle((90, 700, 104, 900), fill=RED)
    hl = "Binance under scrutiny and Sweden's crypto sanctions warning"; f = fit(hl, 'cx', 96, 1660, 50); lines = wrap(hl, F('cx', 80), 1660)
    for k, ln in enumerate(lines[:2]): d.text((130, 712 + k * 90), ln, font=F('cx', 80), fill=INK)
    d.rectangle((90, 900, 900, 960), fill=BLUE); d.text((115, 906), C.DATES.upper(), font=F('cx', 44), fill=WHITE)
    bug = make_bug(); im.paste(bug, (60, 40), bug)
    tick = make_ticker(); draw_ticker(im, 3.0, *tick)
    im.resize((1280, 720), Image.LANCZOS).save('thumbnail.png'); print('thumbnail.png')

if __name__ == '__main__': main()
