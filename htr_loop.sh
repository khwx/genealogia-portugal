#!/bin/bash
# Robust HTR loop - never stops while there are images
LOG="/home/pxtkhw/projetos/obitos/output/daily_logs/loop.log"
mkdir -p /home/pxtkhw/projetos/obitos/output/daily_logs

echo "$(date): Robust HTR loop started" >> "$LOG"

while true; do
    # Check if HTR is running
    if ! pgrep -f "htr_cloud.py" > /dev/null 2>&1; then
        echo "$(date): HTR missing, starting..." >> "$LOG"
        cd /home/pxtkhw/projetos/obitos
        nohup python3 htr_cloud.py --backend=gemini >> htr_processing.log 2>&1 &
        sleep 30  # Wait for it to start
    else
        # Check if HTR is stuck (no progress for 5 minutes)
        LAST_LOG=$(tail -1 htr_processing.log 2>/dev/null)
        if echo "$LAST_LOG" | grep -q "Waiting 56s"; then
            # HTR is rate limited and will restart soon
            sleep 120  # Wait for quota reset
        else
            sleep 60
        fi
    fi
done
