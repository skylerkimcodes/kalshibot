#!/usr/bin/env bash
# Kalshi crypto 15m spot-lag bot.
# Usage:
#   ./run_bot.sh                 # dry-run loop
#   ./run_bot.sh --live          # live orders (demo by default)
#   ./run_bot.sh --live --allow-prod   # live on prod (careful)
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH:-.}"

LOG_DIR="${LOG_DIR:-./logs}"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/bot-$STAMP.log"
PID_FILE="$LOG_DIR/bot.pid"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Bot already running (pid $(cat "$PID_FILE")). Stop with: ./stop_bot.sh"
  exit 1
fi

nohup python3 -u -m kalshibot "$@" >>"$LOG_FILE" 2>&1 &

echo $! >"$PID_FILE"
echo "Started crypto15m bot pid $(cat "$PID_FILE")"
echo "Logging to $LOG_FILE"
echo "Tail:   tail -f $LOG_FILE"
echo "Stop:   ./stop_bot.sh"
