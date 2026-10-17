"""Newsreel renderer for Nordic Crypto #2. PIL frames -> ffmpeg (-threads 1). One segment per process.
usage: render.py SEG            -> $SEGDIR/v_SEG.mp4
       render.py SEG --still T  -> still frame at local time T
       render.py thumb          -> thumbnail.png
Env: TIMELINE (json path), SEGDIR (segment mp4 directory). Voice JSON stays in build/."""
import os, re, sys, json, math, random, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.'); import content as C
W, H = 1920, 1080
ROOT = 'build/'
SEGDIR = os.environ.get('SEGDIR', ROOT)
os.makedirs(SEGDIR, exist_ok=True)
G = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts') + os.sep
# Brand fonts from nordiccrypto.no/media: Cormorant Garamond Bold (wordmark, display) and Schibsted Grotesk (text).
FONTS = {'cb': G + 'CormorantGaramond-Bold.ttf', 'cx': G + 'SchibstedGrotesk-Bold.ttf',
         'cs': G + 'SchibstedGrotesk-SemiBold.ttf', 'm': G + 'SchibstedGrotesk-Medium.ttf'}
_fc = {}
def F(k, s):
    if (k, s) not in _fc: _fc[(k, s)] = ImageFont.truetype(FONTS[k], s)
    return _fc[(k, s)]
# Media-kit colours: North Sea, Shield Gold, Sailcloth, Pine Tar, Sea Foam, dark gold; NIGHT is the site's dark ground.
SEA = (30, 58, 69); NIGHT = (13, 24, 29); GOLD = (217, 160, 52); SAIL = (240, 241, 236)
TAR = (29, 28, 26); FOAM = (191, 211, 211); GOLD_INK = (138, 90, 12); LINE = (36, 66, 76); MUTED = (85, 96, 95)
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
BRAND = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'assets', 'brand') + os.sep
def _arc(x1, y1, rx, ry, fa, fs, x2, y2):  # SVG endpoint arc without x-rotation
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    lam = dx * dx / (rx * rx) + dy * dy / (ry * ry)
    if lam > 1: rx *= math.sqrt(lam); ry *= math.sqrt(lam)
    den = rx * rx * dy * dy + ry * ry * dx * dx
    co = math.sqrt(max(0, (rx * rx * ry * ry - den) / den)) * (-1 if fa == fs else 1)
    cxp, cyp = co * rx * dy / ry, -co * ry * dx / rx
    a1 = math.atan2((dy - cyp) / ry, (dx - cxp) / rx); da = math.atan2((-dy - cyp) / ry, (-dx - cxp) / rx) - a1
    if fs and da < 0: da += 2 * math.pi
    if not fs and da > 0: da -= 2 * math.pi
    cx, cy = cxp + (x1 + x2) / 2, cyp + (y1 + y2) / 2
    return [(cx + rx * math.cos(a1 + da * k / 32), cy + ry * math.sin(a1 + da * k / 32)) for k in range(1, 33)]
def _subpaths(d):  # M L H V C A Z, absolute, as used in assets/brand/shield*.svg
    toks = re.findall(r'[A-Za-z]|-?[0-9.]+', d); subs, cur, x, y, sx, sy, i, cmd = [], [], 0., 0., 0., 0., 0, None
    def n(k):
        nonlocal i; i += k; return [float(v) for v in toks[i - k:i]]
    while i < len(toks):
        if toks[i].isalpha(): cmd = toks[i]; i += 1
        if cmd == 'M':
            if cur: subs.append(cur)
            x, y = n(2); sx, sy = x, y; cur = [(x, y)]; cmd = 'L'
        elif cmd == 'L': x, y = n(2); cur.append((x, y))
        elif cmd == 'H': x, = n(1); cur.append((x, y))
        elif cmd == 'V': y, = n(1); cur.append((x, y))
        elif cmd == 'C':
            x1, y1, x2, y2, x3, y3 = n(6)
            for k in range(1, 25):
                t = k / 24; u = 1 - t
                cur.append((u ** 3 * x + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3, u ** 3 * y + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3))
            x, y = x3, y3
        elif cmd == 'A':
            rx, ry, _rot, fa, fs, x2, y2 = n(7); cur += _arc(x, y, rx, ry, fa, fs, x2, y2); x, y = x2, y2
        elif cmd == 'Z':
            if cur: subs.append(cur)
            cur = []; x, y = sx, sy
    return subs + ([cur] if cur else [])
_SHIELD = {}
def shield(h):  # assets/brand/shield-band.svg (Sailcloth outline for dark grounds), h px tall
    if not _SHIELD:
        src = open(BRAND + 'shield-band.svg', encoding='utf-8').read()
        vx, vy, vw, vh = (float(v) for v in re.search(r'viewBox="([^"]+)"', src).group(1).split()); k = 1024 / vh
        im = Image.new('RGBA', (round(vw * k), 1024), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for attrs in re.findall(r'<path([^>]*)/>', src):
            a = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
            for pts in _subpaths(a['d']):
                q = [((px - vx) * k, (py - vy) * k) for px, py in pts]
                if a.get('fill', 'none') != 'none': d.polygon(q, fill=a['fill'])
                if a.get('stroke', 'none') != 'none': d.line(q + q[:2], fill=a['stroke'], width=round(float(a['stroke-width']) * k), joint='curve')
        _SHIELD['m'] = im
    m = _SHIELD['m']; h = max(2, int(h)); return m.resize((max(1, round(m.width * h / m.height)), h), Image.LANCZOS)
def mark(im, x, y, s):  # shield s px tall, centred on an s x s box
    sh = shield(s); im.paste(sh, (int(x + s / 2 - sh.width / 2), int(y)), sh)
def wordmark(d, x, y, f):  # "Nordic" in Sailcloth, "Crypto" in Shield Gold, as on the band lockup
    d.text((x, y), 'Nordic', font=f, fill=SAIL); d.text((x + tw(d, 'Nordic ', f), y), 'Crypto', font=f, fill=GOLD)
# Nordic cross flags in their official units: (width, height, field, cross bands as (colour, x0, x1, y0, y1)).
FLAGS = {'NO': (22, 16, (186, 12, 47), [((255, 255, 255), 6, 10, 6, 10), ((0, 32, 91), 7, 9, 7, 9)]),
         'SE': (16, 10, (0, 106, 167), [((254, 204, 2), 5, 7, 4, 6)]),
         'DK': (37, 28, (200, 16, 46), [((255, 255, 255), 12, 16, 12, 16)]),
         'FI': (18, 11, (255, 255, 255), [((0, 47, 108), 5, 8, 4, 7)]),
         'IS': (25, 18, (2, 82, 156), [((255, 255, 255), 7, 11, 7, 11), ((220, 30, 53), 8, 10, 8, 10)])}
def flag_w(code, h): fw, fh = FLAGS[code][:2]; return fw * h / fh
def flag(d, code, x, y, h):
    fw, fh, field, bands = FLAGS[code]; k = h / fh; w = fw * k
    d.rectangle((x, y, x + w - 1, y + h - 1), fill=field)
    for c, x0, x1, y0, y1 in bands:
        d.rectangle((x + x0 * k, y, x + x1 * k - 1, y + h - 1), fill=c); d.rectangle((x, y + y0 * k, x + w - 1, y + y1 * k - 1), fill=c)
COUNTRIES = [('NO', 'NORWAY'), ('SE', 'SWEDEN'), ('DK', 'DENMARK'), ('FI', 'FINLAND'), ('IS', 'ICELAND')]
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
    f = F('cb', 46); w = 70 + tw(DUMMY, 'Nordic Crypto', f) + 24
    im = Image.new('RGBA', (w, 112), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w, 66), fill=SEA + (230,)); mark(im, 12, 9, 48)
    wordmark(d, 70, 2, f)
    return im
def draw_clock(base, T):
    d = ImageDraw.Draw(base, 'RGBA'); x0, y0 = 1500, 40
    d.rectangle((x0, y0, 1860, y0 + 66), fill=SEA + (230,))
    pulse = 0.5 + 0.5 * math.cos(T * 2 * math.pi * 0.8); r = 9
    d.ellipse((x0 + 18 - r, y0 + 33 - r, x0 + 18 + r, y0 + 33 + r), fill=tuple(int(c * (0.55 + 0.45 * pulse)) for c in GOLD) + (255,))
    d.text((x0 + 36, y0 + 14), 'OSLO', font=F('cx', 32), fill=FOAM); x = x0 + 50 + tw(d, 'OSLO', F('cx', 32))
    sec = int(T); hh, mm, ss = 19, sec // 60, sec % 60
    d.text((x, y0 + 10), f'{hh:02d}:{mm:02d}:{ss:02d}', font=F('cx', 38), fill=SAIL); x += 12 + tw(d, '00:00:00', F('cx', 38))
    d.text((x, y0 + 22), 'CEST', font=F('cs', 22), fill=FOAM)
    d.rectangle((x0, y0 + 70, 1860, y0 + 104), fill=NIGHT + (235,))
    spaced(d, (x0 + 14, y0 + 74), C.BUG_LINE, F('cs', 20), GOLD, 1)
TICK_Y, TICK_H, TICK_SPEED = 1012, 68, 140
def make_ticker():
    f = F('cs', 32); parts = []
    for it in C.TICKER: parts.append(it)
    widths = [tw(DUMMY, p, f) for p in parts]; gap = 90; L = sum(widths) + gap * len(parts)
    strip = Image.new('RGB', (int(L) + W, TICK_H), SAIL); d = ImageDraw.Draw(strip)
    x = 0
    for rep in range(2):
        for p, w in zip(parts, widths):
            if x > L + W: break
            d.text((x, 12), p, font=f, fill=TAR); x += w + gap / 2
            cx, cy = x - 4, TICK_H / 2; d.polygon([(cx, cy - 11), (cx + 11, cy), (cx, cy + 11), (cx - 11, cy)], fill=GOLD); x += gap / 2
    lab = Image.new('RGB', (290, TICK_H), SEA); dl = ImageDraw.Draw(lab)
    spaced(dl, (22, 16), 'HEADLINES', F('cx', 30), SAIL, 2); dl.polygon([(262, 0), (290, 0), (290, TICK_H), (262 + 0, TICK_H)], fill=GOLD)
    return strip, int(L), lab
def draw_ticker(base, T, strip, L, lab, yoff=0):
    off = int(T * TICK_SPEED) % L
    base.paste(strip.crop((off, 0, off + W - 290, TICK_H)), (290, TICK_Y + yoff)); base.paste(lab, (0, TICK_Y + yoff))
    ImageDraw.Draw(base).rectangle((0, TICK_Y + yoff - 5, W, TICK_Y + yoff - 1), fill=GOLD)
def draw_band(base, p):  # wipe band; p 0..1 across a cut (covers screen at p=.5)
    if p <= 0 or p >= 1: return
    d = ImageDraw.Draw(base); BW = 2500; sl = 260; x = -BW - sl + p * (W + BW + 2 * sl)
    d.polygon([(x + sl, 0), (x + BW + sl, 0), (x + BW, H), (x, H)], fill=SEA)
    d.polygon([(x + BW - 30 + sl, 0), (x + BW + sl + 40, 0), (x + BW + 40, H), (x + BW - 30, H)], fill=GOLD)
    d.polygon([(x + BW + sl + 40, 0), (x + BW + sl + 70, 0), (x + BW + 70, H), (x + BW + 40, H)], fill=SAIL)
    d.polygon([(x + sl - 60, 0), (x + sl, 0), (x, H), (x - 60, H)], fill=FOAM)
    if 0.3 < p < 0.7:  # brand mark rides the band
        s = 180; mark(base, int(x + BW / 2 + sl / 2 - s / 2), H // 2 - s // 2, s)
WIPE = 0.36  # seconds each side of a cut

# ---------- backgrounds ----------
BW_, BH_ = 2112, 1188
def kb(img, u, dirx=1, diry=0):  # Ken Burns: zoom from 1.0 to 1.1, gentle pan
    u = eio(u); bw = BW_ / (1 + 0.1 * u); bh = bw * 9 / 16
    cx = BW_ / 2 + dirx * (BW_ - bw) / 2 * (u * 2 - 1) * 0.8; cy = BH_ / 2 + diry * (BH_ - bh) / 2 * (u * 2 - 1) * 0.8
    return img.resize((W, H), Image.BILINEAR, box=(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2))
def base_bg(tint=None):
    im = grad(BW_, BH_, SEA if not tint else tint, NIGHT); d = ImageDraw.Draw(im)
    for x in range(0, BW_, 96): d.line((x, 0, x, BH_), fill=LINE, width=1)
    for y in range(0, BH_, 96): d.line((0, y, BW_, y), fill=LINE, width=1)
    return im
def glow_layer(draw_fn, blur=14):
    lay = Image.new('RGBA', (BW_, BH_), (0, 0, 0, 0)); draw_fn(ImageDraw.Draw(lay))
    g = lay.filter(ImageFilter.GaussianBlur(blur)); out = Image.alpha_composite(g, lay); del g; return out
def art_bg(st):
    random.seed(st['big']); tint = (52, 44, 30) if st['art'] == 'scan' else None
    im = base_bg(tint).convert('RGBA'); cx, cy = 1530, 540
    def motif(d):
        a = st['art']
        if a == 'stars':
            d.ellipse((cx - 330, cy - 330, cx + 330, cy + 330), outline=FOAM + (90,), width=3)
            for i in range(12): ang = i * math.pi / 6; star(d, cx + 260 * math.sin(ang), cy - 260 * math.cos(ang), 34, GOLD + (255,))
            d.ellipse((cx - 120, cy - 120, cx + 120, cy + 120), outline=SAIL + (120,), width=2)
        elif a == 'globe':
            r = 320; d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=FOAM + (220,), width=4)
            for k in range(1, 6):
                rx = r * math.cos(k * math.pi / 12); d.ellipse((cx - rx, cy - r, cx + rx, cy + r), outline=FOAM + (110,), width=2)
            for k in range(-4, 5):
                yy = cy + r * math.sin(k * math.pi / 10); hw = r * math.cos(k * math.pi / 10); d.line((cx - hw, yy, cx + hw, yy), fill=FOAM + (110,), width=2)
            for _ in range(7):
                a2 = random.uniform(0, 2 * math.pi); rr = random.uniform(0, r * .85); x, y = cx + rr * math.cos(a2), cy + rr * math.sin(a2)
                d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=GOLD + (255,)); d.ellipse((x - 22, y - 22, x + 22, y + 22), outline=GOLD + (160,), width=2)
        elif a == 'bars':
            for i in range(6):
                x = cx - 330 + i * 125; hgt = 3 + (i * 7 + 3) % 9
                for j in range(hgt):
                    y = cy + 300 - j * 38
                    d.ellipse((x - 50, y - 16, x + 50, y + 16), fill=GOLD_INK + (255,), outline=GOLD + (255,), width=3)
                    d.ellipse((x - 50, y - 22, x + 50, y + 10), fill=GOLD + (255,), outline=(236, 196, 110, 255), width=2)
        elif a == 'nodes':
            pts = [(cx + random.uniform(-380, 380), cy + random.uniform(-330, 330)) for _ in range(20)]
            for i, p in enumerate(pts):
                for q in pts[i + 1:]:
                    if math.dist(p, q) < 260: d.line((*p, *q), fill=FOAM + (140,), width=3)
            for i, (x, y) in enumerate(pts):
                r = 12 if i % 4 else 22; d.ellipse((x - r, y - r, x + r, y + r), fill=(SAIL if i % 3 else GOLD) + (255,))
        elif a == 'scan':
            for r in (110, 210, 310): d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=GOLD + (150,), width=3)
            d.line((cx - 380, cy, cx + 380, cy), fill=GOLD + (160,), width=2); d.line((cx, cy - 380, cx, cy + 380), fill=GOLD + (160,), width=2)
            d.pieslice((cx - 310, cy - 310, cx + 310, cy + 310), -70, -20, fill=GOLD + (70,))
            for _ in range(5):
                a2 = random.uniform(0, 2 * math.pi); rr = random.uniform(60, 290); x, y = cx + rr * math.cos(a2), cy + rr * math.sin(a2)
                d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=SAIL + (255,))
    im = Image.alpha_composite(im, glow_layer(motif)); d = ImageDraw.Draw(im)
    # headline typography (left), keep out of lower-third area (screen y<760 -> art y<~800)
    kf = F('cx', 40); kw = spaced_w(st['kicker'], kf, 3)
    d.rectangle((200, 300, 200 + kw + 40, 366), fill=GOLD); spaced(d, (220, 310), st['kicker'], kf, TAR, 3)
    bf = fit(st['big'], 'cb', 290, 980, 90); d.text((196, 330), st['big'], font=bf, fill=SAIL)
    d.rectangle((200, 640, 420, 652), fill=GOLD)
    return im.convert('RGB')
def bokeh_bg(seed=3, tint=SEA):
    random.seed(seed); im = grad(BW_, BH_, tint, NIGHT).convert('RGBA')
    lay = Image.new('RGBA', (BW_ // 4, BH_ // 4), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for _ in range(40):
        x, y, r = random.uniform(0, BW_ / 4), random.uniform(0, BH_ / 4), random.uniform(8, 40)
        c = random.choice([FOAM, SEA, (70, 110, 120), GOLD if random.random() < .15 else SEA])
        d.ellipse((x - r, y - r, x + r, y + r), fill=c + (random.randint(40, 110),))
    lay = lay.filter(ImageFilter.GaussianBlur(6)).resize((BW_, BH_), Image.BILINEAR)
    return Image.alpha_composite(im, lay).convert('RGB')

# ---------- lower third ----------
def make_lt(st):
    f = fit(st['head'], 'cs', 54, 1640, 42); lines = [st['head']] if tw(DUMMY, st['head'], f) <= 1640 else wrap(st['head'], F('cs', 44), 1640)
    if len(lines) > 1: f = F('cs', 44)
    hh = 34 + len(lines) * (f.size + 6)
    head = Image.new('RGB', (1740, hh), SAIL); d = ImageDraw.Draw(head)
    for i, ln in enumerate(lines): d.text((40, 10 + i * (f.size + 6)), ln, font=f, fill=TAR)
    d.rectangle((0, 0, 12, hh), fill=GOLD)
    tf = F('cx', 32); tag = Image.new('RGB', (int(spaced_w(st['section'], tf, 3)) + 44, 56), GOLD); spaced(ImageDraw.Draw(tag), (22, 9), st['section'], tf, TAR, 3)
    sf = F('cs', 26); src = Image.new('RGB', (int(tw(DUMMY, 'SOURCE  ' + st['src'], sf)) + 60, 46), SEA); ds = ImageDraw.Draw(src)
    ds.text((22, 8), 'SOURCE', font=F('cx', 26), fill=GOLD); ds.text((22 + tw(ds, 'SOURCE  ', F('cx', 26)), 8), st['src'], font=sf, fill=SAIL)
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
        im = Image.new('RGB', (W, H), NIGHT); d = ImageDraw.Draw(im); cx, cy = W / 2, H / 2 - 40
        rot = t * 0.35; flash = clamp(1 - abs(t - 3.0) / 0.25)
        for i in range(24):  # rotating sunburst
            a0 = rot + i * 2 * math.pi / 24; a1 = a0 + math.pi / 24
            c = (21 + int(20 * flash), 44 + int(30 * flash), 53 + int(30 * flash)) if i % 2 == 0 else NIGHT
            d.polygon([(cx, cy), (cx + 2400 * math.cos(a0), cy + 2400 * math.sin(a0)), (cx + 2400 * math.cos(a1), cy + 2400 * math.sin(a1))], fill=c)
        for k in range(5):  # expanding rings
            r = ((t * 420 + k * 260) % 1300); w_ = max(1, int(6 * (1 - r / 1300)))
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(110, 150, 152), width=w_)
        # globe grid behind logo
        r = 250 * eo((t - 0.2) / 0.8)
        if r > 2:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=FOAM, width=3)
            for k in range(1, 5):
                ph = (t * 0.8 + k / 5) % 1; rx = r * math.cos(ph * math.pi); rx = abs(rx)
                d.ellipse((cx - rx, cy - r, cx + rx, cy + r), outline=(70, 110, 118), width=2)
            for k in (-2, -1, 0, 1, 2):
                yy = cy + r * k / 3; hw = math.sqrt(max(0, r * r - (r * k / 3) ** 2)); d.line((cx - hw, yy, cx + hw, yy), fill=(70, 110, 118), width=2)
        sz = 260 * eback((t - 1.0) / 0.5)
        if sz > 4: mark(im, cx - sz / 2, cy - 40 - sz / 2, sz)
        f = F('cb', 200)
        if t > 1.9:
            u = eo((t - 1.9) / 0.5); w1 = tw(d, 'Nordic', f); y = cy + 110
            d.text((cx - 24 - w1 - (1 - u) * 1200, y), 'Nordic', font=f, fill=SAIL); d.text((cx + 24 + (1 - u) * 1200, y), 'Crypto', font=f, fill=GOLD)
        if t > 3.0:
            u = eo((t - 3.0) / 0.4); sf = F('cx', 40); txt = 'CRYPTO NEWS FROM THE NORDICS'; ww = spaced_w(txt, sf, 6)
            d.rectangle((cx - ww / 2 - 30, cy + 385, cx - ww / 2 - 30 + (ww + 60) * u, cy + 450), fill=GOLD)
            if u > .6: spaced(d, (cx - ww / 2, cy + 395), txt, sf, TAR, 6)
        if flash > 0:  # Sailcloth flash on the final chord
            im = Image.blend(im, Image.new('RGB', (W, H), SAIL), 0.55 * flash)
        if t < 0.3: im = Image.blend(Image.new('RGB', (W, H), (0, 0, 0)), im, t / 0.3)
        return im
    return frame, dict(bugs=False)
def seg_title(s):
    bg = bokeh_bg(11); sents = sentences(s['name'])
    stripes = Image.new('L', (W * 2, H), 0); ds = ImageDraw.Draw(stripes)
    for i in range(0, W * 2, 240): ds.polygon([(i, 0), (i + 90, 0), (i + 90 - 400, H), (i - 400, H)], fill=26)
    def frame(t, T):
        im = kb(bg, t / (s['dur'])); off = int(t * 60) % 240
        im.paste(FOAM, (0, 0), stripes.crop((off, 0, off + W, H)))
        d = ImageDraw.Draw(im); cx = W / 2
        u = eback((t - 0.1) / 0.6); sz = 190 * u
        if sz > 3: mark(im, cx - sz / 2, 230 - sz / 2 + 75, sz)
        f = F('cb', 190); u2 = eo((t - 0.4) / 0.6); w1 = tw(d, 'Nordic ', f); w2 = tw(d, 'Crypto', f); x = cx - (w1 + w2) / 2
        d.text((x - (1 - u2) * 300, 380), 'Nordic', font=f, fill=SAIL); d.text((x + w1 + (1 - u2) * 300, 380), 'Crypto', font=f, fill=GOLD)
        u3 = eo((t - 0.9) / 0.5)
        if u3 > 0:
            tf = F('cx', 46); txt = C.ISSUE_RIBBON; ww = spaced_w(txt, tf, 4) + 60
            d.rectangle((cx - ww / 2, 660, cx - ww / 2 + ww * u3, 735), fill=GOLD)
            if u3 > .7: spaced(d, (cx - ww / 2 + 30, 670), txt, tf, TAR, 4)
        u4 = eo((t - 1.3) / 0.5)
        if u4 > 0:
            df = F('cb', 66); txt = C.DATES; ww = tw(d, txt, df); d.text((cx - ww / 2, 752 + (1 - u4) * 40), txt, font=df, fill=SAIL if u4 > .99 else tuple(int(c * u4) for c in SAIL))
        u5 = eo((t - 1.7) / 0.45)
        if u5 > 0:
            nf = F('cs', 34); txt = 'CRYPTO, BITCOIN AND BLOCKCHAIN NEWS FROM THE NORDICS'; ww = tw(d, txt, nf) + 50
            d.rectangle((cx - ww / 2, 860, cx + ww / 2, 860 + 58 * u5), fill=NIGHT)
            if u5 > .8: d.text((cx - ww / 2 + 25, 868), txt, font=nf, fill=GOLD)
        return im
    return frame, {}
def seg_tonight(s):
    bg = bokeh_bg(5); sents = sentences(s['name']); vo = s['voff']
    tags, heads, needles = zip(*C.TONIGHT)
    starts = []
    for i, needle in enumerate(needles):
        hit = cue_at(sents, vo, needle)
        if hit is None and i < len(sents): hit = vo + sents[i][0]
        starts.append(0.2 + i * 1.6 if hit is None else hit)
    def frame(t, T):
        im = kb(bg, t / s['dur'], -1); d = ImageDraw.Draw(im)
        u = eo(t / 0.45); tf = F('cx', 80); bw = spaced_w('TONIGHT', tf, 6) + 60
        d.rectangle((140 - (1 - u) * 700, 160, 140 - (1 - u) * 700 + bw, 280), fill=GOLD)
        spaced(d, (168 - (1 - u) * 700, 175), 'TONIGHT', tf, TAR, 6)
        for i in range(3):
            a = eo((t - starts[i]) / 0.42)
            if a <= 0: continue
            y = 330 + i * 210; x = 140 + (1 - a) * 1900
            d.rectangle((x, y, x + 1640, y + 180), fill=NIGHT); d.rectangle((x, y, x + 14, y + 180), fill=GOLD)
            d.text((x + 44, y + 24), tags[i], font=F('cx', 32), fill=GOLD)
            hf = fit(heads[i], 'cb', 62, 1540, 34)
            d.text((x + 44, y + 70), heads[i], font=hf, fill=SAIL)
        return im
    return frame, {}
def seg_countries(s):
    bg = bokeh_bg(7)
    def frame(t, T):
        im = kb(bg, t / s['dur'], 1); d = ImageDraw.Draw(im)
        a = eo(t / 0.5); d.text((140 - (1 - a) * 900, 180), 'News from five countries', font=F('cb', 104), fill=SAIL)
        if a > .5: d.text((144, 320), 'Crypto, bitcoin and blockchain news, with a link to every original source', font=F('m', 36), fill=FOAM)
        for i, (cc, c) in enumerate(COUNTRIES):
            u = eback((t - 0.6 - i * 0.4) / 0.4)
            if u <= 0: continue
            x = 140 + i * 336; y = 450; hgt = 300 * min(u, 1)
            d.rectangle((x, y + 300 - hgt, x + 300, y + 300), fill=SEA); d.rectangle((x, y + 300 - hgt, x + 300, y + 300 - hgt + 8), fill=GOLD)
            if u > .7:
                fh = 110; flag(d, cc, x + 150 - flag_w(cc, fh) / 2, y + 60, fh)
                cw = spaced_w(c, F('cx', 34), 3); spaced(d, (x + 150 - cw / 2, y + 210), c, F('cx', 34), SAIL, 3)
        return im
    return frame, {}
def seg_section(s):
    def frame(t, T):
        im = Image.new('RGB', (W, H), NIGHT); d = ImageDraw.Draw(im)
        for i in range(14):  # speed streaks
            y = (i * 83 + 40) % H; x = ((t * 3200 + i * 517) % (W + 1200)) - 600; d.line((W - x, y, W - x + 400 + i * 20, y), fill=LINE, width=3 + i % 3)
        u = eo((t - 0.05) / 0.45); sl = 220
        x1 = W - u * (W + 200)
        d.polygon([(x1 + sl, 300), (W + 400, 300), (W + 400 - sl, 780), (x1, 780)], fill=SEA)
        d.polygon([(x1 + sl - 50, 300), (x1 + sl, 300), (x1, 780), (x1 - 50, 780)], fill=GOLD)
        tf = fit(s['label'], 'cb', 230, 1600, 120); lw = spaced_w(s['label'], tf, 8); v = eo((t - 0.25) / 0.5)
        x = W / 2 - lw / 2 + (1 - v) * 1400 - (t - 0.75) * 30 * (t > 0.75)
        if v > 0: spaced(d, (x, 360), s['label'], tf, SAIL, 8)
        a = eo((t - 0.6) / 0.4)
        if a > 0:
            sf = F('cs', 44); sw = tw(d, s['sub'], sf); d.rectangle((W / 2 - sw / 2 - 30, 800, W / 2 - sw / 2 - 30 + (sw + 60) * a, 872), fill=GOLD)
            if a > .8: d.text((W / 2 - sw / 2, 810), s['sub'], font=sf, fill=TAR)
        return im
    return frame, {}
def seg_story(s):
    st = C.STORIES[s['name']]; bg = art_bg(st); lt = make_lt(st); dirx = 1 if int(s['name'][1]) % 2 else -1
    def frame(t, T):
        im = kb(bg, t / s['dur'], dirx, 0.5); draw_lt(im, lt, t, s['dur']); return im
    return frame, {}
def seg_calendar(s):
    bg = bokeh_bg(8); sents = sentences(s['name']); st = [s['voff'] + x[0] for x in sents]
    def frame(t, T):
        im = kb(bg, t / s['dur'], 1); d = ImageDraw.Draw(im)
        u = eo(t / 0.5); lf = F('cx', 56); bw = spaced_w('ON THE CALENDAR', lf, 4) + 50
        d.rectangle((120 - (1 - u) * 900, 160, 120 - (1 - u) * 900 + bw, 250), fill=GOLD)
        spaced(d, (145 - (1 - u) * 900, 172), 'ON THE CALENDAR', lf, TAR, 4)
        for i, (dt, city, title, venue) in enumerate(C.EVENTS):
            a = eo((t - st[i] + 0.1) / 0.45) if i < len(st) else 0
            if a <= 0: continue
            y = 280 + i * 124; x = 120 + (1 - a) * 1900; hi = (i == 3)
            d.rectangle((x, y, x + 1680, y + 108), fill=SAIL if not hi else (251, 241, 220)); d.rectangle((x, y, x + 210, y + 108), fill=SEA if not hi else GOLD)
            dw = tw(d, dt, F('cb', 64)); d.text((x + 105 - dw / 2, y + 12), dt, font=F('cb', 64), fill=TAR if hi else SAIL)
            d.text((x + 240, y + 8), title, font=F('cx', 46), fill=TAR); d.text((x + 240, y + 64), f'{city}  ·  {venue}', font=F('m', 30), fill=MUTED)
        disc_t = cue_at(sents, s['voff'], 'disclosure')
        if disc_t is None and len(st) > 4: disc_t = st[4]
        if disc_t is not None:
            a = eo((t - disc_t) / 0.5)
            if a > 0:
                y = 790 + (1 - a) * 300; d.rectangle((120, y, 1800, y + 100), fill=NIGHT); d.rectangle((120, y, 134, y + 100), fill=GOLD)
                f = F('m', 28); lines = wrap(C.NEXA_DISCLOSURE, f, 1610)
                for k, ln in enumerate(lines[:2]): d.text((160, y + 8 + k * 40), ln, font=f, fill=SAIL)
                d.text((160, y + 8), 'Disclosure (28 Oct):', font=f, fill=GOLD)
        more_t = cue_at(sents, s['voff'], 'more events')
        if more_t is None and len(st) > 6: more_t = st[6]
        if more_t is not None and t >= more_t:
            a = eo((t - more_t) / 0.4); txt = 'More events, including Stockholm and Helsinki in November: ' + C.SITE + '/calendar'
            ff = F('cs', 32); ww = tw(d, txt, ff); d.rectangle((120, 908, 120 + (ww + 50) * a, 966), fill=SEA)
            if a > .9: d.text((145, 916), txt, font=ff, fill=SAIL)
        return im
    return frame, {}
def seg_end(s):
    bg = bokeh_bg(13); sents = sentences(s['name'])
    site_t = cue_at(sents, s['voff'], 'every story')
    advice_t = cue_at(sents, s['voff'], 'investment advice')
    team_t = cue_at(sents, s['voff'], 'nordic crypto team')
    if site_t is None and len(sents) > 1: site_t = s['voff'] + sents[1][0]
    if advice_t is None and len(sents) > 2: advice_t = s['voff'] + sents[2][0]
    if team_t is None and sents: team_t = s['voff'] + sents[-1][0]
    def frame(t, T):
        im = kb(bg, t / s['dur'], -1); d = ImageDraw.Draw(im); cx = W / 2
        u = eback((t - 0.1) / 0.55); sz = 130 * u
        if sz > 3: mark(im, cx - sz / 2, 90 + 65 - sz / 2, sz)
        a = eo((t - 0.25) / 0.5); txt = C.END_HEAD; tf = fit(txt, 'cb', 92, 1760, 48); ww = tw(d, txt, tf)
        d.text((cx - ww / 2, 236 + (1 - a) * 50), txt, font=tf, fill=SAIL if a > .99 else tuple(int(c * a) for c in SAIL))
        if site_t is not None:
            b = eo((t - site_t) / 0.45)
            if b > 0:
                l1 = "Every story, with a link to the original source"; f1 = F('m', 38); w1 = tw(d, l1, f1)
                d.text((cx - w1 / 2, 390), l1, font=f1, fill=FOAM)
                f2 = F('cx', 60); w2 = tw(d, C.SITE, f2)
                d.rectangle((cx - w2 / 2 - 36, 455, cx - w2 / 2 - 36 + (w2 + 72) * b, 548), fill=GOLD)
                if b > .85: d.text((cx - w2 / 2, 467), C.SITE, font=f2, fill=TAR)
        if advice_t is not None:
            c = eo((t - advice_t) / 0.4)
            if c > 0:
                f3 = F('m', 32); w3 = tw(d, C.END_DISCLOSURE, f3)
                d.text((cx - w3 / 2, 600 + (1 - c) * 24), C.END_DISCLOSURE, font=f3, fill=FOAM)
        if team_t is not None:
            e = eo((t - team_t) / 0.4)
            if e > 0:
                f4 = F('cx', 56); w4 = spaced_w('GOOD NIGHT', f4, 4)
                spaced(d, (cx - w4 / 2, 690 + (1 - e) * 28), 'GOOD NIGHT', f4, SAIL, 4)
                f5 = F('cb', 64); w5 = tw(d, C.SIGNOFF_CARD, f5)
                d.text((cx - w5 / 2, 775 + (1 - e) * 28), C.SIGNOFF_CARD, font=f5, fill=GOLD)
        fade = clamp((t - (s['dur'] - 1.2)) / 1.2)
        if fade > 0: im = Image.blend(im, Image.new('RGB', (W, H), (0, 0, 0)), fade)
        return im
    return frame, dict(ticker_out=True, last=True)
KINDS = dict(bumper=seg_bumper, title=seg_title, tonight=seg_tonight, countries=seg_countries, section=seg_section, story=seg_story, calendar=seg_calendar, end=seg_end)

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
    st = dict(C.STORIES['s1']); st['big'] = 'HALT'; st['kicker'] = 'NORWAY · ISSUE #2'
    im = art_bg(st).resize((W, H), Image.LANCZOS, box=(96, 54, 96 + 1920, 54 + 1080)); d = ImageDraw.Draw(im)
    d.rectangle((90, 680, 1830, 900), fill=SAIL); d.rectangle((90, 680, 104, 900), fill=GOLD)
    lines = wrap(C.THUMB_HEAD, F('cb', 80), 1640)
    for k, ln in enumerate(lines[:2]): d.text((130, 694 + k * 90), ln, font=F('cb', 80), fill=TAR)
    d.rectangle((90, 900, 1040, 960), fill=SEA); d.text((115, 909), C.DATES.upper(), font=F('cx', 38), fill=SAIL)
    bug = make_bug(); im.paste(bug, (60, 40), bug)
    tick = make_ticker(); draw_ticker(im, 3.0, *tick)
    im.resize((1280, 720), Image.LANCZOS).save('thumbnail.png'); print('thumbnail.png')

if __name__ == '__main__': main()
