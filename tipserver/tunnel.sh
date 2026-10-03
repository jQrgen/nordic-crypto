#!/usr/bin/env bash
# Keeps a Cloudflare QUICK tunnel (random https://*.trycloudflare.com, no login) in front of the tip server and restarts it
# when it exits or when the public /api/health check fails 3 times in a row (checked every 2 minutes).
# Each time it comes up, the URL is written to tipserver/tunnel-url.txt and tipserver/publish_endpoint.sh pushes ONLY
# tip-endpoint.json to gh-pages if it changed. Started by tipserver/run.sh (not used when config.json has public_endpoint).
cd "$(dirname "$0")"
log() { echo "$(date -u +%FT%TZ) $*" >&2; }
trap 'kill "$child" 2>/dev/null; exit 0' TERM INT
delay=2
while true; do
  started=$(date +%s); : > tunnel.cur.log
  cloudflared tunnel --no-autoupdate --loglevel info --url "http://127.0.0.1:${TIP_PORT:-8787}" >>tunnel.cur.log 2>&1 & child=$!
  url=""
  for _ in $(seq 1 60); do
    url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' tunnel.cur.log | head -1); [ -n "$url" ] && break
    kill -0 "$child" 2>/dev/null || break; sleep 1
  done
  ok=""
  if [ -n "$url" ]; then  # only publish a URL that really answers (the edge connection needs outbound port 7844)
    for _ in $(seq 1 18); do kill -0 "$child" 2>/dev/null || break; curl -fsS --max-time 10 "$url/api/health" 2>/dev/null | grep -q '"ok": true' && { ok=1; break; }; sleep 5; done
    [ -z "$ok" ] && { log "tunnel URL $url never answered (edge connection failed?) – not publishing it"; kill "$child" 2>/dev/null; url=""; }
  fi
  if [ -n "$url" ]; then
    echo "$url" > tunnel-url.txt; log "tunnel up: $url"
    ./publish_endpoint.sh >&2 || log "publishing tip-endpoint.json failed (will retry on next run.sh ensure)"
    fails=0; n=0
    while kill -0 "$child" 2>/dev/null; do
      sleep 10; n=$((n+1)); (( n % 12 )) && continue
      if curl -fsS --max-time 15 "$url/api/health" >/dev/null 2>&1; then fails=0
      else fails=$((fails+1)); log "public health check failed ($fails/3)"; (( fails >= 3 )) && { log "restarting tunnel"; kill "$child"; }; fi
    done
  else log "no working tunnel URL"; kill "$child" 2>/dev/null; fi
  wait "$child"; rc=$?
  cat tunnel.cur.log >> tunnel.log; tail -n 3000 tunnel.log > tunnel.log.tmp && mv tunnel.log.tmp tunnel.log
  log "cloudflared exited rc=$rc, restarting in ${delay}s"; sleep "$delay"
  if (( $(date +%s) - started > 300 )); then delay=2; else delay=$(( delay < 60 ? delay * 2 : 60 )); fi
done
