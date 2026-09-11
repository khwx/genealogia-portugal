#!/bin/bash
# Keep HTR running continuously - FIXED VERSION
LOG="/home/pxtkhw/projetos/obitos/output/daily_logs/keepalive.log"
mkdir -p /home/pxtkhw/projetos/obitos/output/daily_logs

echo "$(date): Keepalive started (PID: $$)" >> "$LOG"

while true; do
    # Check if HTR is running
    if ! pgrep -f "htr_cloud.py" > /dev/null 2>&1; then
        echo "$(date): HTR not running, restarting..." >> "$LOG"
        cd /home/pxtkhw/projetos/obitos
        nohup python3 htr_cloud.py --backend=gemini >> htr_processing.log 2>&1 &
        echo "$(date): HTR restarted with PID: $!" >> "$LOG"
    fi
    
    # Log progress every 6 hours
    HOUR=$(date +%H)
    MIN=$(date +%M)
    if [ "$MIN" = "00" ] && [ "$HOUR" = "00" -o "$HOUR" = "06" -o "$HOUR" = "12" -o "$HOUR" = "18" ]; then
        TOTAL=$(ls output/full_images/*.tiff 2>/dev/null | wc -l)
        DONE=$(ls output/htr_text/*.json 2>/dev/null | wc -l)
        echo "$(date): Progress $DONE/$TOTAL ($(((DONE*100)/TOTAL))%)" >> "$LOG"
    fi
    
    sleep 60  # Check every minute
done
