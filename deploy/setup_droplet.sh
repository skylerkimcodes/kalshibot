#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 24.04 DigitalOcean Droplet.
# Run as root: bash deploy/setup_droplet.sh
set -euo pipefail

APP_DIR=/opt/kalshibot
APP_USER=kalshibot

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/setup_droplet.sh"
  exit 1
fi

apt-get update
apt-get install -y python3 python3-pip python3-venv git

id -u "$APP_USER" &>/dev/null || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR/logs"

if [[ -f requirements.txt ]]; then
  python3 -m venv "$APP_DIR/venv"
  "$APP_DIR/venv/bin/pip" install --upgrade pip
  "$APP_DIR/venv/bin/pip" install -r requirements.txt
else
  echo "requirements.txt not found — run this from /opt/kalshibot after copying the repo"
  exit 1
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

install -m 644 deploy/kalshibot.service /etc/systemd/system/kalshibot.service
systemctl daemon-reload
systemctl enable kalshibot

echo ""
echo "Setup complete. Before starting:"
echo "  1. Create $APP_DIR/.env (see .env.example)"
echo "  2. Copy your demo PEM to $APP_DIR/kalshi_demo_private_key.pem"
echo "  3. chown kalshibot:kalshibot $APP_DIR/.env $APP_DIR/*.pem"
echo "  4. chmod 600 $APP_DIR/.env $APP_DIR/*.pem"
echo ""
echo "Then:"
echo "  systemctl start kalshibot"
echo "  journalctl -u kalshibot -f"
echo "  tail -f $APP_DIR/logs/bot.log"
