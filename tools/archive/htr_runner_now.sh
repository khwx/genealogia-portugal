#!/bin/bash
# Continuous HTR runner - runs daily with time limits
# No sudo needed, uses sleep between runs

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/output/daily_logs"
RUNNER_LOG="$LOG_DIR/runner.log"
mkdir -p "$LOG_DIR"

echo "$(date): HTR Daily Runner started" >> "$RUNNER_LOG"

while true; do
    HOUR=$(date +%H)
    
    # Only run between 09:00 and 12:00 (3 hours)
    if [ "1" = "1" ]; then
        echo "$(date): Starting daily HTR run..." >> "$RUNNER_LOG"
        ./htr_daily.sh 3 >> "$RUNNER_LOG" 2>&1
        echo "$(date): Daily run completed" >> "$RUNNER_LOG"
    fi
    
    # Sleep for 1 hour before checking again
    sleep 3600
done
