#!/usr/bin/env bash
# Morning publish for Nordic Crypto (routine). Public build with ONLY editor-approved content (queue/approved.json),
# privacy gate, push site/ to gh-pages and code to main, then check the live URL. Refuses preview builds (publish.sh).
# After a successful gh-pages push, publish.sh calls tools/push_notify.py (one browser notification for stories
# that were not already on gh-pages). That step does not import or unpublish anything. It skips if the push Worker
# is not configured. Then this script records every published story in the append-only archive (tools/article_archive.py record;
# archive/articles.db + archive/articles.json – rows are never deleted, stories that disappear are marked removed).
# Per-language summaries: only those the editor approved in queue/approved.json (summary_i18n, matching summary_i18n_source) are built.
# Log: logs/publish-YYYYMMDD.txt
set -euo pipefail
cd "$(dirname "$0")/.."
log="logs/publish-$(date +%Y%m%d).txt"; mkdir -p logs
# set -e does not apply on the left of ||, so each step is chained; a failure prints the log tail.
# The pull is refused on any branch but main, so it never fast-forwards a feature branch.
{
  echo "== morning publish $(date '+%Y-%m-%d %H:%M %Z')"
  if [ "$(git symbolic-ref --short -q HEAD || true)" != main ]; then echo "refusing: box is not on main"; false
  else git pull --ff-only origin main && ./publish.sh --yes; fi
} >"$log" 2>&1 || { tail -20 "$log"; exit 1; }
tail -4 "$log"
grep -q "HTTP 200" "$log" || { echo "live check failed – see $log"; exit 1; }
.venv/bin/python tools/article_archive.py record >>"$log" 2>&1 && tail -1 "$log"
git add archive/articles.json && { git diff --cached --quiet || { git commit -q -m "Archive export $(date +%F)" && git push -q origin main; }; } || echo "warning: archive export not pushed"
