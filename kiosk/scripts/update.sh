#!/usr/bin/env bash
# Pull a new kiosk release if VERSION on UPDATE_BASE differs from local.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/config.env"
UPDATE_BASE="https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/kiosk"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

LOCAL_VER="$(tr -d '[:space:]' < "$ROOT/VERSION" 2>/dev/null || echo 0)"
REMOTE_VER="$(curl -fsSL --max-time 30 "$UPDATE_BASE/VERSION" | tr -d '[:space:]' || true)"

if [[ -z "$REMOTE_VER" ]]; then
  echo "update: could not read remote VERSION (kiosk may not be published yet)"
  exit 0
fi

if [[ "$REMOTE_VER" == "$LOCAL_VER" ]]; then
  echo "update: already on $LOCAL_VER"
  exit 0
fi

echo "update: $LOCAL_VER -> $REMOTE_VER"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Manifest lists relative paths under kiosk/
MANIFEST_URL="$UPDATE_BASE/MANIFEST.txt"
if curl -fsSL --max-time 30 "$MANIFEST_URL" -o "$TMP/MANIFEST.txt"; then
  while IFS= read -r path || [[ -n "$path" ]]; do
    [[ -z "$path" || "$path" =~ ^# ]] && continue
    mkdir -p "$TMP/pkg/$(dirname "$path")"
    curl -fsSL --max-time 60 "$UPDATE_BASE/$path" -o "$TMP/pkg/$path"
  done < "$TMP/MANIFEST.txt"
else
  echo "update: no MANIFEST.txt; abort"
  exit 1
fi

# Preserve local config.env
if [[ -f "$ROOT/config.env" ]]; then
  cp "$ROOT/config.env" "$TMP/config.env.bak"
fi

rsync -a --delete \
  --exclude 'config.env' \
  --exclude 'web/config.js' \
  --exclude '.git' \
  "$TMP/pkg/" "$ROOT/"

if [[ -f "$TMP/config.env.bak" ]]; then
  cp "$TMP/config.env.bak" "$ROOT/config.env"
fi

"$ROOT/scripts/write-config-js.sh" "$ROOT/config.env"
echo "$REMOTE_VER" > "$ROOT/VERSION"
echo "update: done $REMOTE_VER — restart kiosk to pick up UI changes"
# Soft-reload chromium if running under systemd
systemctl --user try-restart nordic-crypto-kiosk.service 2>/dev/null || \
  sudo systemctl try-restart nordic-crypto-kiosk.service 2>/dev/null || true
