#!/usr/bin/env bash
# Install Nordic Crypto news kiosk on Raspberry Pi OS (Bookworm/Bullseye).
set -euo pipefail
DEST="${DEST:-/opt/nordic-crypto-kiosk}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing to $DEST"
sudo mkdir -p "$DEST"
sudo rsync -a --delete \
  --exclude '.git' \
  --exclude 'config.env' \
  "$SRC/" "$DEST/"

if [[ ! -f "$DEST/config.env" ]]; then
  sudo cp "$DEST/config.example.env" "$DEST/config.env"
fi

sudo chmod +x "$DEST/scripts/"*.sh
"$DEST/scripts/write-config-js.sh" "$DEST/config.env"

# Packages (idempotent)
if command -v apt-get >/dev/null; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 curl rsync x11-utils \
    chromium || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq chromium-browser || true
fi

# Systemd (system-wide; runs as current user for display)
USER_NAME="${SUDO_USER:-$USER}"
UNIT_DIR=/etc/systemd/system
sudo tee "$UNIT_DIR/nordic-crypto-kiosk.service" >/dev/null <<UNIT
[Unit]
Description=Nordic Crypto news kiosk
After=graphical.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/$USER_NAME/.Xauthority
WorkingDirectory=$DEST
ExecStart=$DEST/scripts/start-kiosk.sh
Restart=on-failure
RestartSec=5
Nice=10

[Install]
WantedBy=graphical.target
UNIT

sudo tee "$UNIT_DIR/nordic-crypto-kiosk-update.service" >/dev/null <<UNIT
[Unit]
Description=Update Nordic Crypto kiosk app
After=network-online.target

[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$DEST
ExecStart=$DEST/scripts/update.sh
Nice=15
UNIT

sudo tee "$UNIT_DIR/nordic-crypto-kiosk-update.timer" >/dev/null <<UNIT
[Unit]
Description=Check for Nordic Crypto kiosk updates

[Timer]
OnBootSec=5min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now nordic-crypto-kiosk-update.timer
sudo systemctl enable nordic-crypto-kiosk.service
# Start now if graphical session is up; always enabled for next boot
sudo systemctl start nordic-crypto-kiosk.service || true
echo "Kiosk enabled for graphical.target (fullscreen on every boot). Ensure desktop autologin is on."

echo
echo "Installed. Start with:  sudo systemctl start nordic-crypto-kiosk"
echo "Config:                 $DEST/config.env"
echo "Logs:                   journalctl -u nordic-crypto-kiosk -f"
echo "Autoupdate checks every 6h against gh-pages/kiosk/VERSION"
