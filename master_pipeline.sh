#!/bin/bash
# master_pipeline.sh - Pipeline master para processar freguesias automaticamente
# 1. Baixar fotos de uma freguesia
# 2. Processar com HTR
# 3. Sincronizar para Supabase
# 4. Commit + push para GitHub
# 5. Apagar fotos (libertar espaço)
# 6. Próxima freguesia

PROJECT_DIR="/home/pxtkhw/projetos/obitos"
LOG_FILE="$PROJECT_DIR/output/pipeline_master.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Step 1: Download images for next freguesia
# Step 2: Run HTR
# Step 3: Sync to Supabase
# Step 4: Commit + push to GitHub
# Step 5: Cleanup images

# ... orchestrator script content ...
