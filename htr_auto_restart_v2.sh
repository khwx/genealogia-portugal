#!/bin/bash
# HTR Auto-Restart V2 - Muito mais lento para evitar rate limits
# 1 requisição a cada 15-60 segundos = ~50-200 imagens/dia

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Configurações - ULTRA LENTO (10 min entre requisições)
HOURS_PER_CYCLE="${1:-24}"          # 24h por ciclo (ultra-sustentável)
RESTART_DELAY="${2:-600}"           # 600s de espera entre ciclos (10 min)
MAX_BACKOFF="${3:-3600}"            # Backoff máximo: 1 hora
LOG_DIR="output/daily_logs"
LOG_FILE="$LOG_DIR/auto_restart_v2_$(date +%Y%m%d).log"
RESTART_COUNT=0
CURRENT_BACKOFF=$RESTART_DELAY

mkdir -p "$LOG_DIR"

log() {
    local msg="$(date '+%Y-%m-%d %H:%M:%S') $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

count_progress() {
    local total done
    TOTAL=$(ls output/full_images/*.tiff 2>/dev/null | wc -l)
    DONE=$(ls output/htr_text/*.json 2>/dev/null | wc -l)
    REMAINING=$((TOTAL - DONE))
    echo "$DONE/$TOTAL ($((DONE*100/TOTAL))%)"
}

# Início
log "=== HTR Auto-Restart V2 Started ==="
log "Cycle time: ${HOURS_PER_CYCLE}h | Base delay: ${RESTART_DELAY}s"

while true; do
    # Verificar se terminou
    TOTAL=$(ls output/full_images/*.tiff 2>/dev/null | wc -l)
    DONE=$(ls output/htr_text/*.json 2>/dev/null | wc -l)
    REMAINING=$((TOTAL - DONE))

    if [ "$REMAINING" -le 0 ]; then
        log "✅ All $TOTAL images processed!"
        log "Waiting 1h then exiting..."
        sleep 3600
        break
    fi

    # Backup do progresso anterior
    RESTART_COUNT=$((RESTART_COUNT + 1))
    log "=== Cycle #$RESTART_COUNT ==="
    log "Progress: $(count_progress)"
    log "Starting HTR V2 (max $HOURS_PER_CYCLE hours)..."

    # Iniciar HTR V2 com limite de tempo
    # Usamos timeout para limitar o tempo de execução
    if timeout "$((HOURS_PER_CYCLE * 3600))" python3 htr_cloud_v2.py > htr_v2_processing.log 2>&1; then
        # Sucesso (completou dentro do tempo limite)
        CURRENT_BACKOFF=$RESTART_DELAY
        log "✅ Cycle complete successfully"
    else
        # Timeout ou erro
        log "⚠️  Cycle ended (timeout or error)"
        CURRENT_BACKOFF=$((CURRENT_BACKOFF * 2))
        if [ "$CURRENT_BACKOFF" -gt "$MAX_BACKOFF" ]; then
            CURRENT_BACKOFF=$MAX_BACKOFF
        fi
    fi

    # Progresso após o ciclo
    DONE_AFTER=$(ls output/htr_text/*.json 2>/dev/null | wc -l)
    NEW=$((DONE_AFTER - DONE))
    log "Progress: +$NEW images ($DONE_AFTER/$TOTAL)"

    # Aguardar antes do próximo ciclo
    log "Waiting ${CURRENT_BACKOFF}s before next cycle..."
    sleep "$CURRENT_BACKOFF"

    # Reset backoff após recuperação bem-sucedida
    if [ "$NEW" -gt 0 ]; then
        CURRENT_BACKOFF=$RESTART_DELAY
    fi
done

log "=== HTR Auto-Restart V2 Stopped ==="
