"""Write an issue's video block into newsletter/published/issues.json from the rendered file.
usage: video_meta.py ISSUE_ID FIELD MP4 URL [POSTER]
  FIELD video (landscape) or video_vertical (Instagram Reels cut). Keeps the other keys of that block."""
import hashlib, json, os, subprocess, sys
iid, field, mp4, url = sys.argv[1:5]; poster = sys.argv[5] if len(sys.argv) > 5 else None
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'published', 'issues.json')
pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate,codec_name',
                                '-show_entries', 'format=duration', '-of', 'json', mp4], capture_output=True, check=True, text=True).stdout)
st = pr['streams'][0]; dur = float(pr['format']['duration']); n, d = st['r_frame_rate'].split('/')
if field == 'video_vertical':  # Instagram Reels: H.264, 9:16, 30 fps, at most 15 minutes
    assert st['codec_name'] == 'h264' and (st['width'], st['height']) == (1080, 1920) and round(int(n) / int(d)) == 30 and dur <= 900, st
h = hashlib.sha256()
with open(mp4, 'rb') as f:
    for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
doc = json.load(open(P, encoding='utf-8')); iss = next(i for i in doc['issues'] if i['id'] == iid)
v = iss.get(field) or {}
v.update(file=v.get('file') or ('video-vertical.mp4' if field == 'video_vertical' else 'video.mp4'), duration=round(dur),
         width=st['width'], height=st['height'], bytes=os.path.getsize(mp4), sha256=h.hexdigest(), url=url)
if field == 'video_vertical': v['fps'] = 30
if poster: v['poster'] = poster
iss[field] = v
with open(P, 'w', encoding='utf-8') as f: json.dump(doc, f, ensure_ascii=False, indent=1); f.write('\n')
print(field, json.dumps(v))
