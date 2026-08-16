#!/bin/bash
cd /home/pxtkhw/projetos/obitos

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Start batch in background properly
setsid python3 htr_cloud.py --backend=gemini > output/htr_batch.log 2>&1 &
echo "Started with PID: $!"
