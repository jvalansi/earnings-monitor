#!/bin/bash
export PATH=$PATH:/home/ubuntu/.npm-global/bin
cd /home/ubuntu/.openclaw/workspace/earnings
# Start earnings monitor as a background process (no LLM needed)
# Usage: start-monitor.sh [pre-market|after-hours]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGFILE="$SCRIPT_DIR/monitor.log"

MODE="${1:-pre-market}"

if [ "$MODE" = "pre-market" ]; then
  DURATION=180
elif [ "$MODE" = "after-hours" ]; then
  DURATION=150
else
  DURATION=180
fi

echo "$(date) Starting $MODE monitor (duration=${DURATION}m)" >> "$LOGFILE"
nohup python3 "$SCRIPT_DIR/monitor.py" --interval 90 --duration "$DURATION" >> "$LOGFILE" 2>&1 &
echo $! > "$SCRIPT_DIR/monitor.pid"
echo "Monitor started (pid=$!)"
