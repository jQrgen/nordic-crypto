#!/usr/bin/env bash
# Serve static files locally and open Chromium in kiosk mode (low-RAM flags).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/config.env"
CHROMIUM=chromium
DISPLAY="${DISPLAY:-:0}"
PORT=8765

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

"$ROOT/scripts/write-config-js.sh" "$ENV_FILE"

# Prefer python3 http.server (tiny) over heavier stacks.
cd "$ROOT/web"
python3 -m http.server "$PORT" --bind 127.0.0.1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
sleep 0.4

# Wait for X if needed
for i in $(seq 1 30); do
  if [[ -n "${DISPLAY:-}" ]] && xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

URL="http://127.0.0.1:${PORT}/"
# Chromium flags tuned for Pi: less GPU/cache, no extensions, single process avoided (unstable).
exec "$CHROMIUM" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --check-for-update-interval=31536000 \
  --disable-features=TranslateUI \
  --disable-translate \
  --disable-background-networking \
  --disable-sync \
  --disable-extensions \
  --disable-plugins \
  --disable-dev-shm-usage \
  --disk-cache-size=1 \
  --media-cache-size=1 \
  --js-flags="--max-old-space-size=96" \
  --window-size=1920,1080 \
  --app="$URL"
