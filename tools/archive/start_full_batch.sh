#!/bin/bash
cd /home/pxtkhw/projetos/obitos
export BATCH_SIZE=0
setsid python3 htr_cloud.py --backend=gemini > output/htr_batch.log 2>&1 < /dev/null &
echo "Batch started with PID: $!"
