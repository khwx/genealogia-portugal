#!/bin/bash
# Watchdog: verifica a cada 5 minutos se HTR está a correr
# Se não estiver, reinicia automaticamente

LOGFILE="/home/pxtkhw/projetos/obitos/output/watchdog.log"
HTR_SCRIPT="/home/pxtkhw/projetos/obitos/htr_cloud_v2.py"
HTR_DIR="/home/pxtkhw/projetos/obitos"
PIDFILE="/home/pxtkhw/projetos/obitos/output/htr.pid"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOGFILE"
}

restart_htr() {
    log "=== Reiniciando HTR ==="
    cd "$HTR_DIR"
    # Mata qualquer processo anterior
    pkill -f "htr_cloud_v2.py" 2>/dev/null
    sleep 2
    # Inicia novo processo desligado do terminal
    setsid python3 "$HTR_SCRIPT" > /dev/null 2>&1 &
    echo $! > "$PIDFILE"
    log "HTR reiniciado com PID $(cat $PIDFILE)"
}

# Início
log "=== Watchdog iniciado ==="

# Se HTR não está a correr, inicia
if ! pgrep -f "htr_cloud_v2.py" > /dev/null; then
    log "HTR não está a correr. A iniciar..."
    restart_htr
fi

# Loop de verificação a cada 5 minutos
while true; do
    sleep 3600  # 1 hora
    
    if ! pgrep -f "htr_cloud_v2.py" > /dev/null; then
        log "HTR parou! A reiniciar..."
        restart_htr
    else
        PID=$(pgrep -f "htr_cloud_v2.py" | head -1)
        log "HTR OK (PID $PID)"
    fi
done
