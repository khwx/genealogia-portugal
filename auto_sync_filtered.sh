#!/bin/bash
cd /home/pxtkhw/projetos/obitos

while true; do
    echo "[$(date)] Syncing HTR results to Supabase (with filters)..."
    python3 sync_htr_supabase.py 2>&1 | tail -5
    echo "[$(date)] Sync complete. Waiting 300s..."
    sleep 300
done
