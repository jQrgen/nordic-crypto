#!/usr/bin/env bash
# Nightly fetch for Crypto Nordic (routine). Fetches new stories/events into the editor queue and builds a LOCAL preview.
# Publishes nothing. Log: logs/nightly-YYYYMMDD.txt. Exit code != 0 if the fetch or the privacy gate fails.
# Editor workflow after this run: English summary first, then summary_i18n (nn, nb, sv, da, fi, is) + summary_i18n_source in
# queue/approved.json; new org rows/people/logos/photos/profiles are "review: pending" until listed in org.approve (see README).
set -euo pipefail
cd "$(dirname "$0")/.."
log="logs/nightly-$(date +%Y%m%d).txt"; mkdir -p logs
{
  echo "== nightly fetch $(date '+%Y-%m-%d %H:%M %Z')"
  ./fetch.sh --days 3
  .venv/bin/python tools/crosssite_handoff.py || echo "warning: crosssite_handoff failed"   # Norway news shared with Kryptonytt (suggestions only, never publishes)
  tipserver/run.sh ensure || echo "warning: tip server not healthy"   # no systemd/cron on the box: (re)start the tip server if needed
  .venv/bin/python tipworker/pull.py || echo "warning: tip worker pull failed"   # pending tips from Cloudflare D1 (needs CLOUDFLARE_API_TOKEN; skips otherwise) -> queue as pending, marked imported in D1
  .venv/bin/python tools/reader_tips.py || echo "warning: reader_tips failed"   # pending tips from tipserver/tips.db (+ GitHub tip issues as fallback) -> queue as pending; never publishes
  ./build.sh --preview          # local review build in site/ (never published)
  .venv/bin/python -c "import json;q=json.load(open('queue/review.json'));print('awaiting editor:',len(q.get('items_needing_summary',[])),'stories,',len(q.get('events_pending',[])),'events')" || true
} >"$log" 2>&1
tail -5 "$log"
