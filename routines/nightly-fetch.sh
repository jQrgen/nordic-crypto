#!/usr/bin/env bash
# Nightly fetch for Nordic Crypto (routine). Fetches new stories/events into the editor queue and builds a LOCAL preview.
# Publishes nothing. Log: logs/nightly-YYYYMMDD.txt. Exit code != 0 if the fetch or the privacy gate fails.
set -euo pipefail
cd "$(dirname "$0")/.."
log="logs/nightly-$(date +%Y%m%d).txt"; mkdir -p logs
{
  echo "== nightly fetch $(date '+%Y-%m-%d %H:%M %Z')"
  ./fetch.sh --days 3
  ./build.sh --preview          # local review build in site/ (never published)
  .venv/bin/python -c "import json;q=json.load(open('queue/review.json'));print('awaiting editor:',len(q.get('items_needing_summary',[])),'stories,',len(q.get('events_pending',[])),'events')" || true
} >"$log" 2>&1
tail -5 "$log"
