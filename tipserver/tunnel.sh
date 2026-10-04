#!/usr/bin/env bash
# Keeps a Cloudflare QUICK tunnel (random https://*.trycloudflare.com, no login) in front of the tip server and restarts it
# when it exits or when the public /api/health check fails 3 times in a row (checked every 2 minutes).
# Preflight: every Cloudflare tunnel needs outbound port 7844 to Cloudflare's edge. If that port is blocked (the case on this
# box since 3 Oct 2026), cloudflared is not started; the check is repeated every 10 minutes and the tunnel comes up by itself
# once the port opens.
# State: tunnel-url.txt holds the CURRENT working URL only (removed whenever the tunnel is down, so no stale URL is ever used);
# tunnel.state holds one line: blocked-7844 | starting | up <url> | down.
# Each time a URL comes up, tipserver/publish_endpoint.sh updates site/tip-endpoint.json (local) and – ONLY if config.json
# has auto_publish_endpoint: true (jQrgen's approval) – pushes tip-endpoint.json to gh-pages.
# Started by tipserver/run.sh (not used when config.json has public_endpoint).
cd "$(dirname "$0")"
umask 077
log() { echo "$(date -u +%FT%TZ) $*" >&2; }
state() { echo "$*" > tunnel.state; }
edge_ok() { local h; for h in region1.v2.argotunnel.com region2.v2.argotunnel.com; do timeout 6 bash -c "echo > /dev/tcp/$h/7844" 2>/dev/null && return 0; done; return 1; }
down() { rm -f tunnel-url.txt; state "${1:-down}"; ./publish_endpoint.sh >/dev/null 2>&1 || true; }
trap 'kill "$child" 2>/dev/null; rm -f tunnel-url.txt; state down; exit 0' TERM INT
delay=2; child=""; was_blocked=""
while true; do
  if ! edge_ok; then
    [ -z "$was_blocked" ] && log "outbound port 7844 to Cloudflare's edge is blocked – quick tunnel cannot connect; re-checking every 10 min"
    was_blocked=1; down blocked-7844; sleep 600; continue
  fi
  [ -n "$was_blocked" ] && log "port 7844 reachable again – starting quick tunnel"; was_blocked=""
  started=$(date +%s); : > tunnel.cur.log; state starting; rm -f tunnel-url.txt
  cloudflared tunnel --no-autoupdate --loglevel info --url "http://127.0.0.1:${TIP_PORT:-8787}" >>tunnel.cur.log 2>&1 & child=$!
  url=""
  for _ in $(seq 1 60); do
    url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' tunnel.cur.log | grep -v '^https://api\.' | head -1); [ -n "$url" ] && break
    kill -0 "$child" 2>/dev/null || break; sleep 1
  done
  ok=""
  if [ -n "$url" ]; then  # only use a URL that really answers
    for _ in $(seq 1 18); do kill -0 "$child" 2>/dev/null || break; curl -fsS --max-time 10 "$url/api/health" 2>/dev/null | grep -q '"ok": true' && { ok=1; break; }; sleep 5; done
    [ -z "$ok" ] && { log "tunnel URL $url never answered (edge connection failed?) – not using it"; kill "$child" 2>/dev/null; url=""; }
  fi
  if [ -n "$url" ]; then
    echo "$url" > tunnel-url.txt; state "up $url"; log "tunnel up: $url"
    ./publish_endpoint.sh >&2 || log "updating tip-endpoint.json failed (will retry on next run.sh ensure)"
    fails=0; n=0
    while kill -0 "$child" 2>/dev/null; do
      sleep 10; n=$((n+1)); (( n % 12 )) && continue
      if curl -fsS --max-time 15 "$url/api/health" >/dev/null 2>&1; then fails=0
      else fails=$((fails+1)); log "public health check failed ($fails/3)"; (( fails >= 3 )) && { log "restarting tunnel"; kill "$child"; }; fi
    done
  else log "no working tunnel URL"; kill "$child" 2>/dev/null; fi
  wait "$child"; rc=$?; down
  cat tunnel.cur.log >> tunnel.log; tail -n 3000 tunnel.log > tunnel.log.tmp && mv tunnel.log.tmp tunnel.log
  log "cloudflared exited rc=$rc, restarting in ${delay}s"; sleep "$delay"
  if (( $(date +%s) - started > 300 )); then delay=2; else delay=$(( delay < 60 ? delay * 2 : 60 )); fi
done
