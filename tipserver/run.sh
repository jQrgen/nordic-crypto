#!/usr/bin/env bash
# Nordic Crypto tip server control: run.sh start|stop|restart|status|ensure
#   start/ensure : start the supervisor (tipserver/supervise.sh) detached with setsid+nohup if it is not already running.
#   The box has no systemd/cron, so 'ensure' is also called from routines/nightly-fetch.sh to bring it back after a box restart.
# Logs: tipserver/server.log (method, path, status only – never IPs or request bodies). Listens on 127.0.0.1:${TIP_PORT:-8787}.
set -euo pipefail
cd "$(dirname "$0")"
PIDF=supervise.pid; PORT=${TIP_PORT:-8787}
running() { [[ -f $PIDF ]] && kill -0 "$(cat $PIDF)" 2>/dev/null; }
health() { curl -fsS --max-time 3 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; }
case "${1:-status}" in
  start|ensure)
    if running; then echo "tip server supervisor already running (pid $(cat $PIDF))"; else
      setsid nohup bash supervise.sh >>server.log 2>&1 < /dev/null & echo $! > $PIDF
      for _ in $(seq 1 20); do health && break; sleep 0.25; done
      echo "tip server supervisor started (pid $(cat $PIDF))"; fi
    health && echo "health: ok (http://127.0.0.1:$PORT/api/health)" || { echo "health: FAILED – see tipserver/server.log"; exit 1; } ;;
  stop) if running; then kill "$(cat $PIDF)"; rm -f $PIDF; echo stopped; else echo "not running"; fi ;;
  restart) "$0" stop || true; sleep 1; "$0" start ;;
  status) running && echo "supervisor running (pid $(cat $PIDF))" || echo "supervisor not running"; health && echo "health: ok" || echo "health: down" ;;
  *) echo "usage: $0 start|stop|restart|status|ensure"; exit 2 ;;
esac
