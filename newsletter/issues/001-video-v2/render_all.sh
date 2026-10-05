#!/bin/bash
# Render every segment one at a time (never parallel). Wait if available RAM < 500 MB.
set -euo pipefail
cd "$(dirname "$0")"
export TIMELINE="${TIMELINE:-build/timeline.json}"
export SEGDIR="${SEGDIR:-build/}"
mkdir -p "$SEGDIR"
SEGS=$(python3 -c "import json,os; print(' '.join(s['name'] for s in json.load(open(os.environ['TIMELINE']))['segs']))")
RENDER="${RENDER:-render.py}"
for n in ${@:-$SEGS}; do
  while [ "$(free -m | awk '/Mem:/{print $7}')" -lt 500 ]; do echo "low memory, waiting..."; sleep 15; done
  s=$(date +%s)
  nice -n 19 python3 "$RENDER" "$n"
  echo "$n took $(( $(date +%s)-s ))s, avail $(free -m | awk '/Mem:/{print $7}')MB"
done
