#!/usr/bin/env bash
# Morning publish for Nordic Crypto (routine). Public build with ONLY editor-approved content (queue/approved.json),
# privacy gate, push site/ to gh-pages and code to main, then check the live URL. Refuses preview builds (publish.sh).
# Log: logs/publish-YYYYMMDD.txt
set -euo pipefail
cd "$(dirname "$0")/.."
log="logs/publish-$(date +%Y%m%d).txt"; mkdir -p logs
{
  echo "== morning publish $(date '+%Y-%m-%d %H:%M %Z')"
  ./publish.sh --yes
} >"$log" 2>&1
tail -4 "$log"
grep -q "HTTP 200" "$log" || { echo "live check failed – see $log"; exit 1; }
# reader tips the editor has published or rejected: neutral comment + close (undecided tips stay open)
.venv/bin/python tools/reader_tips.py --close-decided >>"$log" 2>&1 || echo "warning: closing decided reader tips failed – see $log"
