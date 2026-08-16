#!/bin/bash
cd /home/pxtkhw/projetos/obitos
export DELAY_BETWEEN_REQUESTS=120
export BATCH_SIZE=0
setsid python3 htr_cloud.py --backend=gemini > output/htr_batch.log 2>&1 < /dev/null &
echo "Night batch started with PID: $!"
echo "Delay: 120s between requests"
echo "Monitor: tail -f output/htr_batch.log"
