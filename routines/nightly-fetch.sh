#!/usr/bin/env bash
# Nightly fetch for Nordic Crypto (routine). Fetches new stories/events into the editor queue and builds a LOCAL preview.
# Publishes nothing. Log: logs/nightly-YYYYMMDD.txt.
# Exit code != 0 if the fetch fails, if 80% or more of the sources error, or if the preview build fails.
# Editor workflow after this run: English summary first, then summary_i18n (nn, nb, sv, da, fi, is) + summary_i18n_source in
# queue/approved.json; new org rows/people/logos/photos/profiles are "review: pending" until listed in org.approve (see README).
set -euo pipefail
cd "$(dirname "$0")/.."
log="logs/nightly-$(date +%Y%m%d).txt"; mkdir -p logs
rc=0
{
  echo "== nightly fetch $(date '+%Y-%m-%d %H:%M %Z')"
  ./fetch.sh --days 3 || rc=1
  health="$(.venv/bin/python tools/fetch_health.py 2>&1)" || rc=1
  printf '%s\n' "$health"
  .venv/bin/python tools/crosssite_handoff.py || echo "warning: crosssite_handoff failed"   # Norway news shared with Kryptonytt (suggestions only, never publishes)
  tipserver/run.sh ensure || echo "warning: tip server not healthy"   # no systemd/cron on the box: (re)start the tip server if needed
  .venv/bin/python tipworker/pull.py || echo "warning: tip worker pull failed"   # pending tips from Cloudflare D1 (needs CLOUDFLARE_API_TOKEN; skips otherwise) -> queue as pending, marked imported in D1
  .venv/bin/python tools/reader_tips.py || echo "warning: reader_tips failed"   # pending tips from tipserver/tips.db (+ GitHub tip issues as fallback) -> queue as pending; never publishes
  ./build.sh --preview || rc=1          # local review build in site/ (never published)
  .venv/bin/python -c "import json;q=json.load(open('queue/review.json'));print('awaiting editor:',len(q.get('items_needing_summary',[])),'stories,',len(q.get('events_pending',[])),'events')" || true
  printf '%s\n' "$health"
  if [ "$rc" -ne 0 ]; then echo "nightly fetch failed"; fi
} >"$log" 2>&1
tail -20 "$log"
exit "$rc"
