#!/usr/bin/env bash
# Nordic Crypto tip server control: run.sh start|stop|restart|status|ensure
#   Starts two detached watchdogs (setsid + nohup): supervise.sh (tip server on 127.0.0.1:${TIP_PORT:-8787}) and, if
#   config.json has quick_tunnel: true (and no fixed public_endpoint), tunnel.sh (Cloudflare quick tunnel + publishes tip-endpoint.json when the URL changes).
#   The box has no systemd/cron: routines/nightly-fetch.sh calls 'run.sh ensure' to bring both back after a box restart.
#   ensure also re-pushes tip-endpoint.json if gh-pages has an outdated URL.
# Logs: server.log (method, path, status only – never IPs or bodies), tunnel.log / tunnel.cur.log (cloudflared).
set -euo pipefail
cd "$(dirname "$0")"
PORT=${TIP_PORT:-8787}
alive() { [[ -f $1 ]] && kill -0 "$(cat "$1")" 2>/dev/null; }
health() { curl -fsS --max-time 3 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; }
fixed() { python3 -c 'import json;print(json.load(open("config.json")).get("public_endpoint") or "")'; }
quick() { python3 -c 'import json;print("1" if json.load(open("config.json")).get("quick_tunnel") else "")'; }
pubhealth() { local u; u=$(python3 endpoint.py); [[ -n $u ]] && curl -fsS --max-time 15 "$u/api/health" >/dev/null 2>&1; }
start_one() { # pidfile script logfile
  if alive "$1"; then echo "$2 already running (pid $(cat "$1"))"; else setsid nohup bash "$2" >>"$3" 2>&1 < /dev/null & echo $! > "$1"; echo "$2 started (pid $(cat "$1"))"; fi; }
case "${1:-status}" in
  start|ensure)
    start_one supervise.pid supervise.sh server.log
    for _ in $(seq 1 20); do health && break; sleep 0.25; done
    health && echo "local health: ok (http://127.0.0.1:$PORT/api/health)" || { echo "local health: FAILED – see tipserver/server.log"; exit 1; }
    if [[ -z $(fixed) && -n $(quick) ]]; then
      command -v cloudflared >/dev/null || { echo "cloudflared not installed"; exit 1; }
      start_one tunnel.pid tunnel.sh tunnel.log
      for _ in $(seq 1 60); do [[ -s tunnel-url.txt ]] && grep -q "$(cat tunnel-url.txt)" tunnel.cur.log 2>/dev/null && break; sleep 1; done
    fi
    echo "public endpoint: $(python3 endpoint.py)"
    [[ ${1} == ensure && -n $(python3 endpoint.py) ]] && { (cd .. && tipserver/publish_endpoint.sh) || echo "warning: could not publish tip-endpoint.json"; }
    ;;
  stop) for p in tunnel.pid supervise.pid; do if alive $p; then kill "$(cat $p)"; echo "stopped ${p%.pid}"; fi; rm -f $p; done ;;
  restart) "$0" stop || true; sleep 1; "$0" start ;;
  status)
    alive supervise.pid && echo "server watchdog running (pid $(cat supervise.pid))" || echo "server watchdog NOT running"
    health && echo "local health: ok" || echo "local health: down"
    if [[ -n $(fixed) ]]; then echo "fixed endpoint: $(fixed)"; elif [[ -z $(quick) ]]; then echo "quick tunnel: disabled in config.json"; else
      alive tunnel.pid && echo "tunnel watchdog running (pid $(cat tunnel.pid))" || echo "tunnel watchdog NOT running"; fi
    echo "public endpoint: $(python3 endpoint.py)"; pubhealth && echo "public health: ok" || echo "public health: down"
    echo "published tip-endpoint.json: $(curl -fsS --max-time 10 "https://jqrgen.github.io/nordic-crypto/tip-endpoint.json?t=$(date +%s)" 2>/dev/null | tr -d '\n ' || echo none)" ;;
  *) echo "usage: $0 start|stop|restart|status|ensure"; exit 2 ;;
esac
