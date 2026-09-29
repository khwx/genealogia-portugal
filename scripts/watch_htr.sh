#!/bin/bash
# watch_htr.sh — Guardian contínuo do worker de casamentos (output/workers/marr_all.py)
#
# - Relança o worker em ~1 min se cair (com .env carregado).
# - Proteção contra o bug de 20 Set: se o worker está vivo mas faz 0 ficheiros
#   novos durante 45 min, o teto diário das chaves está gasto: mata-o e
#   descansa até à meia-noite, relançando no dia seguinte.
# - Regista um ponto de estado a cada 8h (00h/08h/16h) em output/daily_logs/watch_htr.log
#
# Uso: scripts/watch_htr.sh            (loop principal)
#      scripts/watch_htr.sh --status   (uma verificação pontual / inicio de log)

set -u

OB="/home/pxtkhw/projetos/obitos"
WORKER="$OB/output/workers/marr_all.py"
WORKER_LOG="$OB/output/marr_all.log"
LOG_DIR="$OB/output/daily_logs"
LOG="$LOG_DIR/watch_htr.log"
LOCK="$LOG_DIR/watch_htr.lock"
STUCK_MIN=45
STUCK_SECS=$((STUCK_MIN * 60))
SLEEP=60
MAX_QUICK_RESTARTS=3

mkdir -p "$LOG_DIR"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

worker_alive() { pgrep -f "output/workers/[m]arr_all.py" >/dev/null 2>&1; }

total_files() { find "$OB/output/htr_text" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l; }

keys_today() {
    python3 -c "
import json,sys
try:
    u=json.load(open('$OB/output/key_usage.json'))
except Exception:
    sys.exit(0)
import time
d=time.strftime('%Y-%m-%d')
print(sum(u.get(d,{}).values()))
" 2>/dev/null
}

launch_worker() {
    [ -e "$LOCK" ] && return 1  # outro supervisor já tratou
    ( flock -x 9
        # desl.igamos o nounset: o .env contém "$iw" (password Transkribus) que
        # rebenta com "unbound variable" sob set -u
        set +u
        cd "$OB" && set -a && source .env && set +a && \
        setsid nohup python3 -u "$WORKER" >> "$WORKER_LOG" 2>&1 < /dev/null &
        echo $! > "$LOCK"
        sleep 1
        rm -f "$LOCK"
    ) 9>"$LOCK"
    sleep 2
}

status_line() {
    local total done_mode alive keys
    total=$(total_files)
    alive="falecido"
    worker_alive && alive="vivo"
    keys=$(keys_today)
    local marr=0
    marr=$(grep -rl '"record_type": "MARR"' "$OB/output/htr_text" 2>/dev/null | wc -l)
    log "ESTADO | worker=$alive | ficheiros_json=$total | MARR_feitos=$marr | chaves_usadas_hoje=$keys"
}

if [ "${1:-}" = "--status" ]; then
    status_line
    exit 0
fi

# --- loop principal ---
LAST_TOTAL=$(total_files)
STUCK_START=""
WAIT_DAY=""
LAST_8H=""
QUICK_RESTARTS=0
LAST_RESTART_EPOCH=0

log "=== watch_htr arrancou (relança em ~60s se o worker cair) ==="
status_line

while true; do
    now=$(date +%s)
    total=$(total_files)

    if worker_alive; then
        if [ "$total" -gt "$LAST_TOTAL" ]; then
            STUCK_START=""
            LAST_TOTAL=$total
            QUICK_RESTARTS=0
        elif [ -z "$STUCK_START" ]; then
            STUCK_START=$now
        fi

        if [ -n "$STUCK_START" ] && [ $((now - STUCK_START)) -ge $STUCK_SECS ]; then
            log "aviso: 0 ficheiros novos em ${STUCK_MIN}min com worker vivo — teto diário provavelmente gasto. A matar e a descansar até à meia-noite."
            pkill -f "output/workers/[m]arr_all.py"
            STUCK_START=""
            WAIT_DAY=$(date +%Y-%m-%d)
            LAST_TOTAL=$total
        fi
    else
        # worker morto: relança, exceto se estamos a aguardar o reset diário
        if [ "$WAIT_DAY" != "$(date +%Y-%m-%d)" ] || [ -z "$WAIT_DAY" ]; then
            # crash em cadeia? backoff se relança sem nenhum progresso
            if [ $((now - LAST_RESTART_EPOCH)) -lt 120 ]; then
                QUICK_RESTARTS=$((QUICK_RESTARTS + 1))
            else
                QUICK_RESTARTS=0
            fi
            if [ "$QUICK_RESTARTS" -ge "$MAX_QUICK_RESTARTS" ]; then
                log "aviso: $MAX_QUICK_RESTARTS relanços sem progresso — pausa de 10 min."
                sleep 600
                QUICK_RESTARTS=0
                continue
            fi
            log "worker falecido — a relançar."
            launch_worker
            LAST_RESTART_EPOCH=$(date +%s)
            sleep 5
            worker_alive && log "worker relançado." || log "ERRO: relanço falhou."
            LAST_TOTAL=$(total_files)
        fi
    fi

    # ponto de estado a cada 8h (00/08/16)
    hour_tag=$(date +%H)
    case "$hour_tag" in
        00|08|16)
            if [ "$LAST_8H" != "$hour_tag" ]; then
                status_line
                LAST_8H=$hour_tag
            fi
            ;;
        *) LAST_8H="" ;;
    esac

    sleep "$SLEEP"
done