"""Per-section visual themes. Each part of the site gets its own look, figures and animations on top of the
Våpen tokens (assets/css/tokens.css): page() calls themes.for_nav(nav) and gets the CSS, the decoration layer and
the script for that section. Files: assets/themes/_base.css + <name>.css, assets/themes/_base.js + <name>.js.

All figures are our own drawings (inline SVG built below). Decoration sits in one aria-hidden, pointer-events:none
layer behind the content, so text, links and focus order are unchanged. Readers with prefers-reduced-motion get
the still versions: CSS animations stop and the scripts skip their loops.

Section (the `nav` key of page()) -> theme:"""
import os

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "themes")

BY_NAV = {
    "": "aurora", "stories": "aurora",            # front page and story pages: the serious one, with a moving aurora
    "calendar": "matrix",                         # calendar, event pages, previous events: green code rain
    "markets": "pixel",                           # 8-bit monster-battle handheld
    "org-chart": "pirate",                        # who's who: wanted posters on a sea chart
    "api": "cbase",                               # crashed space station hackerspace
    "newsletter": "broadsheet",                   # hot-off-the-press newspaper
    "talks": "vhs",                               # synthwave VHS tape
    "academia": "chalk",                          # lecture-hall chalkboard
    "about": "saga",                              # northern lights and a longship
    "tip": "noir",                                # rainy detective office
    "sources": "teletext",                        # Nordic tekst-TV
}

# Browser UI colour per theme (meta theme-color); default stays the North Sea band.
THEME_COLOR = {"matrix": "#000000", "pixel": "#E83838", "pirate": "#1D2F4A", "cbase": "#05070D", "broadsheet": "#1A1712",
               "vhs": "#12071F", "chalk": "#1E3127", "saga": "#0B1320", "noir": "#0E0E0F", "teletext": "#000000"}


def _read(fn):
    p = os.path.join(DIR, fn)
    if not os.path.exists(p): return ""
    with open(p, encoding="utf-8") as fh: return fh.read()


# ---------- small SVG helpers ----------

def _sprite(rows, palette, px=4, cls=""):
    """Pixel sprite from a list of strings; each char is a palette key, '.' is transparent."""
    w, h = max(len(r) for r in rows), len(rows)
    rects = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            c = row[x]
            if c == ".": x += 1; continue
            run = 1
            while x + run < len(row) and row[x + run] == c: run += 1
            rects.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{palette[c]}"/>')
            x += run
    return (f'<svg class="{cls}" viewBox="0 0 {w} {h}" width="{w * px}" height="{h * px}" shape-rendering="crispEdges">'
            + "".join(rects) + "</svg>")


# Original pixel creatures for the markets page.
COINLET = [  # a round gold coin creature
    "....kkkkkk....",
    "..kkyyyyyykk..",
    ".kyyyyyyyyyyk.",
    ".kyywwyyywwyk.",
    "kyyywkyyywkyyk",
    "kyyywkyyywkyyk",
    "kyyyyyyyyyyyyk",
    "kyyyyoyyoyyyyk",
    "kyyyyyooyyyyyk",
    ".kyyyyyyyyyyk.",
    ".kyyyyyyyyyyk.",
    "..kkyyyyyykk..",
    "...kk....kk...",
    "..kkk....kkk..",
]
BYTEBAT = [  # a small cyan bat made of bits
    "k............k",
    "kk..........kk",
    "kck..kkkk..kck",
    "kcckkcccckkcck",
    "kcccccwcwccccck"[:14],
    ".kccccckcckcck"[:14],
    "..kccccccccck.",
    "...kccoocck...",
    "....kccccck...",
    ".....kk.kk....",
]
LEDGEROO = [  # a green block-chain lizard
    "......kkkk....",
    ".....kggggk...",
    "....kgwkggk...",
    "....kggggggk..",
    ".kk.kgggrrrk..",
    "kggkkggggk....",
    "kgggggggggk...",
    ".kgdgdgdggk...",
    "..kggggggggk..",
    "...kgggkgggk..",
    "...kgk..kgk...",
    "..kkk..kkk....",
]
PIX = {"k": "#181818", "y": "#F8C030", "w": "#FFFFFF", "o": "#C05010", "c": "#38C8E8", "g": "#48B848", "d": "#2E7D32", "r": "#E83838"}


def _deco_matrix():
    return ('<canvas class="mx-rain"></canvas><div class="mx-scan"></div>'
            '<div class="mx-term"><div class="mx-bar"><i></i><i></i><i></i></div><pre class="mx-log"></pre></div>')


def _deco_pixel():
    s = lambda rows, cls: _sprite(rows, PIX, 4, cls)
    return ('<div class="px-flash"></div>'
            '<div class="px-arena"><div class="px-plat px-plat1"></div><div class="px-plat px-plat2"></div>'
            + s(COINLET, "px-mon px-coin") + s(BYTEBAT, "px-mon px-bat") + s(LEDGEROO, "px-mon px-roo") +
            '</div><div class="px-box"><span class="px-type"></span><b class="px-next">▼</b></div>'
            '<div class="px-clouds"><i></i><i></i><i></i></div>')


_SHIP = ('<svg class="pr-ship" viewBox="0 0 160 130" width="160" height="130">'
         '<path d="M18 92 L142 92 L126 116 L36 116 Z" fill="#5B3A1E" stroke="#2B1D0E" stroke-width="3"/>'
         '<path d="M30 98 H130" stroke="#C8902A" stroke-width="3"/>'
         '<circle cx="54" cy="105" r="3.5" fill="#2B1D0E"/><circle cx="80" cy="105" r="3.5" fill="#2B1D0E"/><circle cx="106" cy="105" r="3.5" fill="#2B1D0E"/>'
         '<rect x="77" y="14" width="5" height="80" fill="#3B2612"/><rect x="47" y="34" width="4" height="60" fill="#3B2612"/>'
         '<path class="pr-sail" d="M84 20 Q120 40 84 82 Z" fill="#F3E6C8" stroke="#2B1D0E" stroke-width="2.5"/>'
         '<path class="pr-sail" d="M53 40 Q80 55 53 86 Z" fill="#F3E6C8" stroke="#2B1D0E" stroke-width="2.5"/>'
         '<g class="pr-flag"><path d="M82 14 L112 18 L104 24 L112 30 L82 30 Z" fill="#8B1E1E" stroke="#2B1D0E" stroke-width="2"/>'
         '<circle cx="93" cy="22" r="4.5" fill="#C8902A"/><path d="M90 22 h6 M93 19 v6" stroke="#2B1D0E" stroke-width="1.5"/></g></svg>')

_COMPASS = ('<svg class="pr-compass" viewBox="-50 -50 100 100" width="130" height="130">'
            '<circle r="46" fill="none" stroke="#6B4F2A" stroke-width="2"/><circle r="38" fill="none" stroke="#6B4F2A" stroke-dasharray="2 4"/>'
            '<g class="pr-needle"><path d="M0 -40 L7 0 L0 40 L-7 0 Z" fill="#8B1E1E"/><path d="M0 -40 L7 0 L0 0 Z" fill="#C8902A"/>'
            '<path d="M-40 0 L0 6 L40 0 L0 -6 Z" fill="#6B4F2A" opacity=".6"/></g>'
            '<text y="-30" text-anchor="middle" font-size="11" font-weight="700" fill="#2B1D0E">N</text><circle r="4" fill="#2B1D0E"/></svg>')


def _deco_pirate():
    gulls = "".join(f'<svg class="pr-gull pr-gull{i}" viewBox="0 0 30 12" width="30" height="12"><path d="M1 10 Q8 0 15 8 Q22 0 29 10" fill="none" stroke="#2B1D0E" stroke-width="2.2" stroke-linecap="round"/></svg>' for i in (1, 2, 3))
    return ('<svg class="pr-map" viewBox="0 0 1000 1000" preserveAspectRatio="none"><path class="pr-trail" d="M60 940 C 240 760, 120 600, 380 560 S 620 380, 560 260 S 820 160, 900 90" fill="none" stroke="#8B1E1E" stroke-width="5" stroke-dasharray="14 14"/>'
            '<g class="pr-x" transform="translate(900 90)"><path d="M-22 -22 L22 22 M22 -22 L-22 22" stroke="#8B1E1E" stroke-width="9" stroke-linecap="round"/></g></svg>'
            + _COMPASS + gulls +
            '<div class="pr-sea"><svg class="pr-wave pr-wave1" viewBox="0 0 1200 60" preserveAspectRatio="none"><path d="M0 30 Q75 0 150 30 T300 30 T450 30 T600 30 T750 30 T900 30 T1050 30 T1200 30 V60 H0 Z"/></svg>'
            + _SHIP +
            '<svg class="pr-wave pr-wave2" viewBox="0 0 1200 60" preserveAspectRatio="none"><path d="M0 30 Q75 55 150 30 T300 30 T450 30 T600 30 T750 30 T900 30 T1050 30 T1200 30 V60 H0 Z"/></svg></div>')


_STATION = ('<svg class="cb-station" viewBox="-160 -160 320 320" width="420" height="420">'
            '<g class="cb-tilt">'
            '<g class="cb-ring cb-ring1"><ellipse rx="140" ry="44" fill="none" stroke="#FF7A1A" stroke-width="3" stroke-dasharray="18 10"/></g>'
            '<g class="cb-ring cb-ring2"><ellipse rx="112" ry="112" fill="none" stroke="#2FD4FF" stroke-width="2" stroke-dasharray="4 8" opacity=".7"/></g>'
            '<circle r="62" fill="url(#cbg)" stroke="#9FB6E0" stroke-width="2.5"/>'
            '<path d="M-62 0 A62 20 0 0 0 62 0" fill="none" stroke="#9FB6E0" stroke-width="2"/><path d="M-50 -34 A62 18 0 0 0 50 -34" fill="none" stroke="#9FB6E0" stroke-width="1.5" opacity=".6"/>'
            '<path d="M-50 34 A62 18 0 0 0 50 34" fill="none" stroke="#9FB6E0" stroke-width="1.5" opacity=".6"/>'
            '<g class="cb-win"><circle cx="-24" cy="-14" r="5"/><circle cx="0" cy="-16" r="5"/><circle cx="24" cy="-14" r="5"/><circle cx="-14" cy="14" r="4"/><circle cx="14" cy="14" r="4"/></g>'
            '<path d="M0 -62 V-118" stroke="#9FB6E0" stroke-width="3"/><circle class="cb-led" cy="-122" r="6"/>'
            '<path d="M44 -44 L84 -92" stroke="#9FB6E0" stroke-width="2.5"/><rect x="74" y="-112" width="34" height="18" fill="#203458" stroke="#2FD4FF" transform="rotate(-50 91 -103)"/>'
            '<path d="M-44 44 L-92 70" stroke="#9FB6E0" stroke-width="2.5"/><circle class="cb-led cb-led2" cx="-96" cy="72" r="5"/>'
            '<g class="cb-sat"><circle cx="0" cy="-150" r="5" fill="#FFD9B0"/></g>'
            '</g><defs><radialGradient id="cbg" cx=".35" cy=".3"><stop offset="0" stop-color="#3B5A8F"/><stop offset="1" stop-color="#0D1730"/></radialGradient></defs></svg>')


def _deco_cbase():
    leds = "".join(f'<i style="--d:{i * .37 % 2:.2f}s"></i>' for i in range(14))
    return ('<canvas class="cb-stars"></canvas><div class="cb-planet"></div>' + _STATION +
            f'<div class="cb-hud"><span class="cb-leds">{leds}</span><span class="cb-clock"></span></div>'
            '<div class="cb-corner cb-tl"></div><div class="cb-corner cb-tr"></div><div class="cb-corner cb-bl"></div><div class="cb-corner cb-br"></div>')


def _deco_broadsheet():
    sheets = "".join(f'<svg class="bs-sheet bs-sheet{i}" viewBox="0 0 60 80" width="60" height="80"><rect x="1" y="1" width="58" height="78" fill="#FBF6EA" stroke="#1A1712"/>'
                     '<rect x="6" y="6" width="48" height="8" fill="#1A1712"/><path d="M6 20h22M6 25h22M6 30h22M6 35h22M32 20h22M32 25h22M32 30h22M32 35h22M6 44h48M6 49h48M6 54h48M6 59h30" stroke="#1A1712" stroke-width="1.2" opacity=".55"/>'
                     '<rect x="34" y="58" width="20" height="16" fill="#8A1C1C" opacity=".25"/></svg>' for i in range(1, 6))
    return ('<div class="bs-halftone"></div>' + sheets +
            '<svg class="bs-press" viewBox="0 0 200 120" width="200" height="120"><rect x="10" y="70" width="180" height="40" rx="6" fill="#2A251D"/>'
            '<g class="bs-roll"><circle cx="60" cy="56" r="26" fill="#3A3428" stroke="#1A1712" stroke-width="3"/><path d="M60 30 V82 M34 56 H86" stroke="#8A1C1C" stroke-width="3"/></g>'
            '<g class="bs-roll"><circle cx="140" cy="56" r="26" fill="#3A3428" stroke="#1A1712" stroke-width="3"/><path d="M140 30 V82 M114 56 H166" stroke="#8A1C1C" stroke-width="3"/></g>'
            '<rect class="bs-paper" x="40" y="74" width="120" height="6" fill="#FBF6EA"/></svg>'
            '<div class="bs-stamp">★ EXTRA ★</div>')


def _deco_vhs():
    return ('<div class="vh-sky"></div><div class="vh-sun"></div><div class="vh-mtn"></div><div class="vh-grid"></div>'
            '<div class="vh-osd"><b class="vh-play">▶ PLAY</b><span class="vh-ctr">SP 0:00:00</span></div>'
            '<div class="vh-track"></div><div class="vh-noise"></div>'
            '<svg class="vh-tape" viewBox="0 0 120 70" width="120" height="70"><rect x="2" y="2" width="116" height="66" rx="6" fill="#1B0B2B" stroke="#FF3EA5" stroke-width="2"/>'
            '<rect x="16" y="14" width="88" height="22" rx="3" fill="#22E6FF" opacity=".25"/><g class="vh-reel"><circle cx="38" cy="25" r="9" fill="none" stroke="#FFE9FB" stroke-width="2"/><path d="M38 16 V34 M29 25 H47" stroke="#FFE9FB" stroke-width="2"/></g>'
            '<g class="vh-reel"><circle cx="82" cy="25" r="9" fill="none" stroke="#FFE9FB" stroke-width="2"/><path d="M82 16 V34 M73 25 H91" stroke="#FFE9FB" stroke-width="2"/></g>'
            '<rect x="20" y="46" width="80" height="12" fill="#FF3EA5" opacity=".7"/></svg>')


def _deco_chalk():
    s = 'fill="none" stroke="#F1F1E8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"'
    y = 'fill="none" stroke="#F7E27A" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"'
    return ('<div class="ck-smudge"></div>'
            # Merkle tree doodle
            f'<svg class="ck-doodle ck-d1" viewBox="0 0 220 160" width="220" height="160"><path class="ck-draw" {s} d="M110 20 L60 70 M110 20 L160 70 M60 70 L35 120 M60 70 L85 120 M160 70 L135 120 M160 70 L185 120"/>'
            f'<circle class="ck-draw" {y} cx="110" cy="20" r="12"/><circle class="ck-draw" {s} cx="60" cy="70" r="10"/><circle class="ck-draw" {s} cx="160" cy="70" r="10"/>'
            f'<rect class="ck-draw" {s} x="25" y="120" width="20" height="20"/><rect class="ck-draw" {s} x="75" y="120" width="20" height="20"/><rect class="ck-draw" {s} x="125" y="120" width="20" height="20"/><rect class="ck-draw" {s} x="175" y="120" width="20" height="20"/></svg>'
            # sine / price curve with axes
            f'<svg class="ck-doodle ck-d2" viewBox="0 0 240 140" width="240" height="140"><path class="ck-draw" {s} d="M20 10 V120 H230"/><path class="ck-draw" {y} d="M22 100 C 50 20, 80 130, 110 70 S 170 10, 200 50 S 220 30, 228 24"/></svg>'
            # hash formula
            f'<svg class="ck-doodle ck-d3" viewBox="0 0 260 80" width="260" height="80"><text class="ck-text" x="8" y="50" font-size="34">H(x) = y</text><path class="ck-draw" {y} d="M8 64 Q130 74 250 60"/></svg>'
            # sigma
            f'<svg class="ck-doodle ck-d4" viewBox="0 0 160 100" width="160" height="100"><text class="ck-text" x="6" y="64" font-size="44">Σ tx</text></svg>'
            f'<svg class="ck-doodle ck-d5" viewBox="0 0 140 140" width="140" height="140"><circle class="ck-draw" {s} cx="70" cy="70" r="52"/><path class="ck-draw" {y} d="M70 18 V122 M18 70 H122 M33 33 L107 107"/></svg>'
            '<div class="ck-ledge"><span class="ck-eraser"></span><span class="ck-stick"></span><span class="ck-stick ck-stick2"></span></div>'
            '<canvas class="ck-dust"></canvas>')


_LONGSHIP = ('<svg class="sg-ship" viewBox="0 0 220 120" width="220" height="120">'
             '<path d="M10 80 Q30 104 110 104 Q190 104 210 80 Q200 92 110 92 Q20 92 10 80 Z" fill="#5A3B1F" stroke="#1A120A" stroke-width="2"/>'
             '<path d="M10 80 Q2 60 16 50 Q14 64 22 72" fill="none" stroke="#5A3B1F" stroke-width="5" stroke-linecap="round"/>'
             '<path d="M210 80 Q218 60 204 50 Q206 64 198 72" fill="none" stroke="#5A3B1F" stroke-width="5" stroke-linecap="round"/>'
             '<rect x="107" y="18" width="5" height="76" fill="#3A2614"/>'
             '<path class="sg-sail" d="M64 26 H156 V76 Q110 84 64 76 Z" fill="#B32D2D" stroke="#1A120A" stroke-width="2"/>'
             '<path d="M64 38 H156 M64 50 H156 M64 62 H156" stroke="#F0E6CF" stroke-width="5" opacity=".85"/>'
             + "".join(f'<circle cx="{40 + i * 22}" cy="88" r="7" fill="#D9A034" stroke="#1A120A" stroke-width="2"/>' for i in range(7)) + '</svg>')


def _deco_saga():
    stars = "".join(f'<i style="left:{(i * 37) % 100}%;top:{(i * 53) % 60}%;--d:{(i * 0.41) % 3:.2f}s"></i>' for i in range(46))
    runes = "".join(f'<span style="--i:{i}">{r}</span>' for i, r in enumerate("ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ"))
    return (f'<div class="sg-stars">{stars}</div><div class="sg-aurora"><i></i><i></i><i></i></div>'
            f'<div class="sg-runes">{runes}</div>'
            '<div class="sg-sea"><div class="sg-shipwrap">' + _LONGSHIP + '</div><div class="sg-water"></div></div>')


_DETECTIVE = ('<svg class="nr-det" viewBox="0 0 160 260" width="160" height="260">'
              '<path d="M38 64 Q80 44 122 64 L128 72 Q80 64 32 72 Z" fill="#050505"/>'
              '<path d="M52 64 Q56 30 80 28 Q104 30 108 64 Z" fill="#050505"/>'
              '<path d="M58 72 Q60 104 80 108 Q100 104 102 72 Z" fill="#0A0A0A"/>'
              '<path d="M44 112 Q80 100 116 112 L134 250 H26 Z" fill="#070707"/>'
              '<path d="M80 108 L66 170 L80 250 L94 170 Z" fill="#141414"/>'
              '<path d="M116 120 Q142 150 128 178 L116 176" fill="#070707"/>'
              '<rect x="118" y="168" width="22" height="20" rx="3" fill="#1A1A1A" stroke="#333"/>'
              '<g class="nr-steam"><path d="M124 162 q-6 -10 0 -18 q6 -8 0 -18" fill="none" stroke="#BBB" stroke-width="2" opacity=".5"/>'
              '<path d="M134 162 q-6 -10 0 -18 q6 -8 0 -18" fill="none" stroke="#BBB" stroke-width="2" opacity=".4"/></g></svg>')


def _deco_noir():
    return ('<div class="nr-blinds"></div><div class="nr-rain"></div><div class="nr-rain nr-rain2"></div>'
            '<div class="nr-spot"></div><div class="nr-flash"></div>' + _DETECTIVE +
            '<svg class="nr-glass" viewBox="0 0 80 80" width="80" height="80"><circle cx="32" cy="32" r="22" fill="rgb(242 193 78 / .08)" stroke="#E8E6E1" stroke-width="4"/>'
            '<path d="M48 48 L74 74" stroke="#E8E6E1" stroke-width="8" stroke-linecap="round"/></svg>'
            '<div class="nr-fan"><i></i><i></i><i></i><i></i></div>')


def _deco_teletext():
    blocks = "".join(f'<i style="--c:{c};--d:{i * .25:.2f}s"></i>' for i, c in enumerate(["#FF0000", "#00FF00", "#FFFF00", "#0000FF", "#FF00FF", "#00FFFF", "#FFFFFF"] * 2))
    return (f'<div class="tt-head"><span class="tt-pg">P100</span><span class="tt-name">NORDIC CRYPTO</span><span class="tt-sub">1/4</span><span class="tt-clock">00:00:00</span></div>'
            f'<div class="tt-bars">{blocks}</div><div class="tt-mosaic"></div><div class="tt-scan"></div>'
            '<div class="tt-keys"><b style="--c:#FF0000">◼</b><b style="--c:#00FF00">◼</b><b style="--c:#FFFF00">◼</b><b style="--c:#00FFFF">◼</b></div>')


def _deco_aurora():
    return '<div class="au-glow"><i></i><i></i></div>'


DECO = {"matrix": _deco_matrix, "pixel": _deco_pixel, "pirate": _deco_pirate, "cbase": _deco_cbase, "broadsheet": _deco_broadsheet,
        "vhs": _deco_vhs, "chalk": _deco_chalk, "saga": _deco_saga, "noir": _deco_noir, "teletext": _deco_teletext, "aurora": _deco_aurora}


def for_nav(nav):
    """dict(name, body_class, css, deco, script, theme_color) for a page() nav key; None keeps the plain site look."""
    name = BY_NAV.get(nav)
    if not name: return None
    js = _read("_base.js") + _read(name + ".js")
    return {
        "name": name,
        "body_class": f"themed th-{name}",
        "css": _read("_base.css") + _read(name + ".css"),
        "deco": f'<div class="th-deco" aria-hidden="true">{DECO[name]()}</div>',
        "script": f"<script>{js}</script>" if js.strip() else "",
        "theme_color": THEME_COLOR.get(name),
    }
