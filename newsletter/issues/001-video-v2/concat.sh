#!/bin/bash
# Concat silent segment mp4s and mux the wav mix to H.264 + AAC.
# usage: concat.sh TIMELINE_JSON SEGDIR MIX_WAV OUT_MP4
set -euo pipefail
cd "$(dirname "$0")"
TL=${1:?timeline json}
SEGDIR=${2:?segment dir}
MIX=${3:?mix wav}
OUT=${4:?out mp4}
mkdir -p "$(dirname "$OUT")"
LIST="$SEGDIR/list.txt"
python3 - "$TL" "$SEGDIR" "$LIST" <<'PY'
import json, sys
tl, segdir, listp = sys.argv[1:]
segs = json.load(open(tl))['segs']
with open(listp, 'w') as f:
    for s in segs:
        f.write(f"file 'v_{s['name']}.mp4'\n")
print(len(segs), 'segments')
PY
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$LIST" -c copy "$SEGDIR/video_only.mp4"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SEGDIR/video_only.mp4")
# Pad or trim audio to the picture so the sign-off is not cut.
ffmpeg -hide_banner -loglevel error -y -i "$SEGDIR/video_only.mp4" -i "$MIX" \
  -filter_complex "[1:a]aresample=48000,aformat=channel_layouts=stereo,apad=pad_dur=2,atrim=0:${DUR},asetpts=PTS-STARTPTS[a]" \
  -map 0:v:0 -map "[a]" -c:v copy -c:a aac -b:a 192k -movflags +faststart "$OUT"
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,sample_rate -of default=nw=1 "$OUT"
echo "wrote $OUT"
