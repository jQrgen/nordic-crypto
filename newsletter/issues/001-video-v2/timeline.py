"""Decode voice to wav, compute segment timeline -> build/timeline.json, subs.srt, script.txt"""
import argparse, json, os, subprocess, wave, sys
sys.path.insert(0, '.'); import content as C
B = 'build/'; SR = 48000
# Short lead/tail so the anchor doesn't leave dead air between sentences' pictures.
LEAD, TAIL = 0.12, 0.18
TITLE_PAD, END_PAD = 0.28, 1.05
FF = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '1']
ap = argparse.ArgumentParser()
ap.add_argument('--timeline', default=B + 'timeline.json')
ap.add_argument('--subs', default='subs.srt')
ap.add_argument('--script', default='script.txt')
ap.add_argument('--bumper', type=float, default=None)
ap.add_argument('--section', type=float, default=None)
args = ap.parse_args()
BUMPER_LEN = dict(C.BUMPER_LEN)
if args.bumper is not None: BUMPER_LEN['bumper'] = args.bumper
if args.section is not None: BUMPER_LEN['section'] = args.section
os.makedirs(B, exist_ok=True)
segs = []; t = 0.0; cues = []
def wrap(s, n=60):
    out, cur = [], ''
    for w in s.split():
        if cur and len(cur) + len(w) + 1 > n: out.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    return out + ([cur] if cur else [])
for name, kind, extra in C.TIMELINE:
    if name in C.VO:
        subprocess.run(FF + ['-i', B + name + '.mp3', '-ar', str(SR), '-ac', '1', B + name + '.wav'], check=True)
        with wave.open(B + name + '.wav') as w: vd = w.getnframes() / SR
        dur = LEAD + vd + TAIL + (END_PAD if kind == 'end' else 0) + (TITLE_PAD if kind == 'title' else 0)
        voff = LEAD + (TITLE_PAD if kind == 'title' else 0)
        for a, z, txt in json.load(open(B + name + '.json')):
            lines = wrap(txt); ch = [' '.join(lines[i:i+2]) and '\n'.join(lines[i:i+2]) for i in range(0, len(lines), 2)]
            tot = sum(len(c) for c in ch); s = a
            for c in ch:
                d = (z - a) * len(c) / tot; cues.append((t + voff + s, t + voff + s + d, c)); s += d
    else:
        dur = BUMPER_LEN[kind]; voff = None; vd = 0
    segs.append(dict(name=name, kind=kind, start=round(t, 4), dur=round(dur, 4), voff=voff, vdur=vd, **extra)); t += dur
# snap to frame grid (25 fps): each segment an integer number of frames
FPS = 25; acc = 0
for s in segs:
    n = round(s['dur'] * FPS); s['frames'] = n; s['start_f'] = acc; acc += n
json.dump(dict(fps=FPS, total_frames=acc, segs=segs), open(args.timeline, 'w'), indent=1)
def ts(x):
    h, r = divmod(max(0, x), 3600); m, s = divmod(r, 60)
    return f"{int(h):02}:{int(m):02}:{int(s):02},{int(round((s % 1) * 1000)) % 1000:03}"
with open(args.subs, 'w') as f:
    for i, (a, z, c) in enumerate(cues, 1):
        z = min(z, cues[i][0]) if i < len(cues) else z
        f.write(f"{i}\n{ts(a)} --> {ts(z)}\n{c}\n\n")
with open(args.script, 'w') as f:
    f.write(f"Nordic Crypto #1 narration. Voice: {C.VOICE} (edge-tts, rate {C.RATE}). "
            f"Sign-off: The Nordic Crypto team. Source: newsletter issue #1.\n\n")
    for s in segs:
        f.write(f"[{s['name']} @ {s['start']:.1f}s, {s['kind']}{' - ' + s['label'] if 'label' in s else ''}]\n{C.VO.get(s['name'], '(music/stinger only)')}\n\n")
print('total', acc / FPS, 's', len(cues), 'cues')
