#!/usr/bin/env bash
# Nightly fetch for Nordic Crypto (routine). Fetches new stories/events into the editor queue and builds a LOCAL preview.
# Publishes nothing. Log: logs/nightly-YYYYMMDD.txt, and the same lines on stdout so a runner never sees a silent hang.
# Exit code != 0 if the fetch fails, if 80% or more of the sources error, if the preview build fails,
# if this run exceeds NIGHTLY_TIMEOUT_SECS (default 3 h), or if another run still holds a fresh lock.
# Editor workflow after this run: English summary first, then summary_i18n (nn, nb, sv, da, fi, is) + summary_i18n_source in
# queue/approved.json; new org rows/people/logos/photos/profiles are "review: pending" until listed in org.approve (see README).
#
# Lock: logs/nightly-fetch.lock (override with NIGHTLY_LOCK). The lock is flock, so it dies with the process;
# a leftover file from a dead run does not block the next one. The file records "pid start-epoch". If that pid is
# still alive and older than NIGHTLY_STALE_SECS (default 3 h, same as the timeout), it is stopped and the lock is taken.
# On the box the file is /workspace/nordic-crypto/logs/nightly-fetch.lock.
set -u
cd "$(dirname "$0")/.."

export PYTHONUNBUFFERED=1
export GIT_TERMINAL_PROMPT=0
# gh and wrangler must fail instead of waiting on a password. The nightly job has no keyboard.
if [[ "${NIGHTLY_INNER:-}" != 1 ]]; then
  exec </dev/null
fi

LOCK="${NIGHTLY_LOCK:-logs/nightly-fetch.lock}"
STALE="${NIGHTLY_STALE_SECS:-10800}"
TIMEOUT="${NIGHTLY_TIMEOUT_SECS:-10800}"
log="${NIGHTLY_LOG:-logs/nightly-$(date +%Y%m%d).txt}"
mkdir -p logs "$(dirname "$log")" "$(dirname "$LOCK")"

say() {
  printf '%s\n' "$*" >>"$log"
  printf '%s\n' "$*"
}

alive() { [[ "${1:-}" =~ ^[0-9]+$ ]] && [[ "$1" -gt 1 ]] && kill -0 "$1" 2>/dev/null; }

kill_tree() {
  local p="$1" sig="$2" c
  alive "$p" || return 0
  for c in $(ps -o pid= --ppid "$p" 2>/dev/null); do
    kill_tree "$c" "$sig"
  done
  kill -"$sig" "$p" 2>/dev/null || true
}

take_lock() {
  exec 9>>"$LOCK"
  if flock -n 9; then
    printf '%s %s\n' "$$" "$(date +%s)" >"$LOCK"
    return 0
  fi
  local pid="" start="" now age=0
  read -r pid start < "$LOCK" || true
  now=$(date +%s)
  if [[ "${start:-}" =~ ^[0-9]+$ ]]; then age=$((now - start)); fi
  if alive "${pid:-}" && [[ "$pid" != "$$" ]] && [[ "$age" -ge "$STALE" ]]; then
    say "nightly fetch: stale lock, pid $pid has held $LOCK for ${age}s — stopping it"
    kill_tree "$pid" TERM
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do
      alive "$pid" || break
      sleep 0.5
    done
    alive "$pid" && kill_tree "$pid" KILL
    sleep 0.2
    if flock -w 5 9; then
      printf '%s %s\n' "$$" "$(date +%s)" >"$LOCK"
      return 0
    fi
  fi
  if alive "${pid:-}" && [[ "$pid" != "$$" ]]; then
    say "nightly fetch: another run is active (pid $pid, ${age}s, lock $LOCK). Not waiting."
    say "If that process is stuck, stop it. A dead process does not keep this lock; the file does not need to be deleted."
    exit 1
  fi
  # Record missing or the pid is already dead, but flock is still held (the holder is exiting,
  # or it has not written its pid yet). Wait a moment, then give up. Do not wait for the outer killer.
  if flock -w 2 9; then
    printf '%s %s\n' "$$" "$(date +%s)" >"$LOCK"
    return 0
  fi
  say "nightly fetch: lock $LOCK is busy (recorded pid ${pid:-unknown} is not running). Not waiting."
  exit 1
}

# Stream a command to the log and to stdout. Line-buffered, so a kill still leaves the last line.
run_out() {
  stdbuf -oL -eL "$@" 2>&1 | stdbuf -oL tee -a "$log"
}

if [[ "${NIGHTLY_INNER:-}" != 1 ]]; then
  take_lock
  say "== nightly fetch $(date '+%Y-%m-%d %H:%M %Z') pid $$ timeout ${TIMEOUT}s"
  export NIGHTLY_INNER=1 NIGHTLY_LOG="$log" NIGHTLY_LOCK="$LOCK"
  set +e
  timeout -k 20 "${TIMEOUT}" bash "$0"
  rc=$?
  set -e
  if [[ "$rc" -eq 124 || "$rc" -eq 137 ]]; then
    say "nightly fetch timed out after ${TIMEOUT}s and was stopped"
    exit 124
  fi
  exit "$rc"
fi

set -euo pipefail
rc=0
if [[ -n "${NIGHTLY_HOOK:-}" ]]; then
  say "-- hook"
  run_out bash -c "$NIGHTLY_HOOK" || rc=$?
  if [[ "$rc" -ne 0 ]]; then say "nightly fetch failed"; fi
  exit "$rc"
fi

say "-- fetch (./fetch.sh --days 3)"
run_out ./fetch.sh --days 3 || rc=1
say "-- fetch health"
health="$(.venv/bin/python tools/fetch_health.py 2>&1)" || rc=1
printf '%s\n' "$health" >>"$log"
printf '%s\n' "$health"
say "-- crosssite handoff"
run_out .venv/bin/python tools/crosssite_handoff.py || say "warning: crosssite_handoff failed"   # Norway news shared with Kryptonytt (suggestions only, never publishes)
say "-- tip server"
run_out tipserver/run.sh ensure || say "warning: tip server not healthy"   # no systemd/cron on the box: (re)start the tip server if needed
say "-- tip worker pull"
run_out .venv/bin/python tipworker/pull.py || say "warning: tip worker pull failed"   # pending tips from Cloudflare D1 (needs CLOUDFLARE_API_TOKEN; skips otherwise) -> queue as pending, marked imported in D1
say "-- reader tips"
run_out .venv/bin/python tools/reader_tips.py || say "warning: reader_tips failed"   # pending tips from tipserver/tips.db (+ GitHub tip issues as fallback) -> queue as pending; never publishes
say "-- preview build"
run_out ./build.sh --preview || rc=1          # local review build in site/ (never published)
say "-- queue"
run_out .venv/bin/python -c "import json;q=json.load(open('queue/review.json'));print('awaiting editor:',len(q.get('items_needing_summary',[])),'stories,',len(q.get('events_pending',[])),'events')" || true
printf '%s\n' "$health" >>"$log"
printf '%s\n' "$health"
if [[ "$rc" -ne 0 ]]; then say "nightly fetch failed"; fi
exit "$rc"
