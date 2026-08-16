#!/bin/bash
# HTR Auto-restart: monitors and restarts HTR when it stops
# Usage: ./htr_auto_restart.sh [hours_per_run]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

HOURS=${1:-3}
LOG_DIR="output/daily_logs"
AUTO_LOG="$LOG_DIR/auto_restart.log"
mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$AUTO_LOG"
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1"
}

log "=== HTR Auto-Restart Started ==="
log "Run time per cycle: ${HOURS}h"

while true; do
    # Count remaining images
    TOTAL=$(ls output/full_images/*.tiff 2>/dev/null | wc -l)
    DONE=$(ls output/htr_text/*.json 2>/dev/null | wc -l)
    REMAINING=$((TOTAL - DONE))
    
    if [ "$REMAINING" -le 0 ]; then
        log "All $TOTAL images processed! Waiting 1h..."
        sleep 3600
        continue
    fi
    
    log "Starting HTR: $DONE/$TOTAL done, $REMAINING remaining"
    
    # Start HTR with time limit (no set -e, use || true)
    BATCH_SIZE=0 python3 htr_cloud.py --backend=gemini --max-runtime=$HOURS >> htr_processing.log 2>&1 || true
    
    # Count progress
    DONE_AFTER=$(ls output/htr_text/*.json 2>/dev/null | wc -l)
    NEW=$((DONE_AFTER - DONE))
    log "HTR cycle ended: +$NEW images ($DONE_AFTER/$TOTAL)"
    
    # Wait before next cycle (let quotas recover)
    log "Waiting 120s before next cycle..."
    sleep 120
done
