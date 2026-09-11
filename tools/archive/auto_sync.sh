#!/bin/bash
# Auto-sync HTR results to Supabase every 5 minutes

while true; do
    echo "[$(date)] Syncing HTR results to Supabase..."
    python3 /home/pxtkhw/projetos/obitos/sync_htr_supabase.py 2>&1 | tail -5
    echo "[$(date)] Sync complete. Waiting 300s..."
    sleep 300
done
