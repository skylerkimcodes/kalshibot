#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PID_FILE="${LOG_DIR:-./logs}/bot.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No pid file — bot not running?"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Stopped bot pid $PID"
else
  echo "Process $PID not running"
fi
rm -f "$PID_FILE"
