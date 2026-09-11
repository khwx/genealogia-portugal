#!/bin/bash
# Daily HTR processing - runs for limited time to avoid rate limits
# Usage: ./htr_daily.sh [hours] [max_images]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Default: 3 hours, no image limit
HOURS=${1:-3}
MAX_IMAGES=${2:-0}
LOG_DIR="$SCRIPT_DIR/output/daily_logs"
LOG_FILE="$LOG_DIR/htr_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

echo "=== Daily HTR Started at $(date) ===" | tee "$LOG_FILE"
echo "Time limit: ${HOURS}h | Max images: ${MAX_IMAGES}" | tee -a "$LOG_FILE"

# Convert hours to seconds
TIME_LIMIT=$((HOURS * 3600))
START_TIME=$(date +%s)

# Run HTR in background with time limit
export BATCH_SIZE=0
export DELAY_BETWEEN_REQUESTS=60

python3 htr_cloud.py --backend=gemini > "$LOG_FILE" 2>&1 &
PID=$!
echo "HTR PID: $PID" | tee -a "$LOG_FILE"

# Monitor and kill after time limit
while kill -0 "$PID" 2>/dev/null; do
    ELAPSED=$(( $(date +%s) - START_TIME ))
    if [ "$ELAPSED" -ge "$TIME_LIMIT" ]; then
        echo "Time limit reached (${HOURS}h). Stopping..." | tee -a "$LOG_FILE"
        kill -SIGTERM "$PID" 2>/dev/null
        wait "$PID" 2>/dev/null
        break
    fi
    sleep 60
done

echo "=== Daily HTR Finished at $(date) ===" | tee -a "$LOG_FILE"

# Count progress
TOTAL=$(ls output/full_images/*.tiff 2>/dev/null | wc -l)
DONE=$(ls output/htr_text/*.json 2>/dev/null | wc -l)
echo "Progress: $DONE / $TOTAL images" | tee -a "$LOG_FILE"
