#!/usr/bin/env bash
# One-liner install: curl -fsSL …/bootstrap.sh | bash
set -euo pipefail
BASE="${NCK_UPDATE_BASE:-https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/kiosk}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Nordic Crypto kiosk: downloading from $BASE"
curl -fsSL --max-time 60 "$BASE/MANIFEST.txt" -o "$TMP/MANIFEST.txt"
while IFS= read -r path || [[ -n "$path" ]]; do
  [[ -z "$path" || "$path" =~ ^# ]] && continue
  mkdir -p "$TMP/pkg/$(dirname "$path")"
  echo "  $path"
  curl -fsSL --max-time 60 "$BASE/$path" -o "$TMP/pkg/$path"
done < "$TMP/MANIFEST.txt"
chmod +x "$TMP/pkg/scripts/"*.sh
# install.sh expects to live inside the package tree
bash "$TMP/pkg/scripts/install.sh"
echo "Enabling kiosk on boot (fullscreen)…"
sudo systemctl enable --now nordic-crypto-kiosk.service
sudo systemctl enable --now nordic-crypto-kiosk-update.timer
echo "Done. Reboot to confirm autostart, or: sudo systemctl status nordic-crypto-kiosk"
