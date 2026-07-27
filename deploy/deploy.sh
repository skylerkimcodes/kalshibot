#!/usr/bin/env bash
# Deploy kalshibot (crypto 15m) to the DigitalOcean Droplet.
# Usage: ./deploy/deploy.sh
set -euo pipefail

HOST="${KALSHIBOT_HOST:-root@192.81.214.13}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Deploying to $HOST …"
rsync -av --delete \
  --exclude logs --exclude data --exclude .venv --exclude venv --exclude __pycache__ \
  --exclude .env --exclude '*.pem' \
  "$ROOT/" "$HOST:/opt/kalshibot/"

scp "$ROOT/deploy/kalshibot.service" "$HOST:/etc/systemd/system/kalshibot.service"

ssh "$HOST" bash -s << 'REMOTE'
set -euo pipefail
cd /opt/kalshibot
if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
mkdir -p logs data
chown -R kalshibot:kalshibot /opt/kalshibot
systemctl daemon-reload
systemctl enable kalshibot
systemctl restart kalshibot
sleep 2
systemctl is-active kalshibot
echo "--- bot log ---"
tail -20 /opt/kalshibot/logs/bot.log 2>/dev/null || journalctl -u kalshibot -n 20 --no-pager
REMOTE

echo "Deploy complete."
