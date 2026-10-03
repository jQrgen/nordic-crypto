#!/usr/bin/env bash
# Keeps the tip server running: restarts it whenever it exits (crash or kill), with a short back-off.
# Started detached by tipserver/run.sh start; stop with tipserver/run.sh stop.
cd "$(dirname "$0")"
trap 'kill "$child" 2>/dev/null; exit 0' TERM INT
delay=1
while true; do
  started=$(date +%s)
  python3 server.py & child=$!; wait "$child"; rc=$?
  echo "$(date -u +%FT%TZ) server exited rc=$rc, restarting in ${delay}s" >&2
  sleep "$delay"
  if (( $(date +%s) - started > 60 )); then delay=1; else delay=$(( delay < 30 ? delay * 2 : 30 )); fi
done
