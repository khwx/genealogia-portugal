#!/bin/bash
cd /home/pxtkhw/projetos/obitos
while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running sync..."
    python3 sync_htr_supabase.py 2>&1 | tail -5
    echo "---"
    sleep 3600  # 1 hora
done
