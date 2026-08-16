#!/bin/bash
cd /home/pxtkhw/projetos/obitos

# Load .env
export $(grep -v '^#' .env | xargs)

# Start batch
nohup python3 htr_cloud.py --backend=gemini > output/htr_batch.log 2>&1 &
echo "Batch started with PID: $!"
echo "Monitor: tail -f output/htr_batch.log"
