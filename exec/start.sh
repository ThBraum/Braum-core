#!/bin/bash

if [ -f /app/.env ]; then
    set -a
    . /app/.env
    set +a
fi

APP_ROLE_VALUE="${APP_ROLE:-${APP:-api}}"
APP_ROLE_VALUE=$(echo "$APP_ROLE_VALUE" | awk '{print tolower($0)}')

if [ "$APP_ROLE_VALUE" == "api" ]; then
    exec bash /app/exec/start/api.sh
elif [ "$APP_ROLE_VALUE" == "cron" ]; then
    exec bash /app/exec/start/cron.sh
elif [ "$APP_ROLE_VALUE" == "worker" ]; then
    if [ -f /app/exec/start/worker.sh ]; then
        exec bash /app/exec/start/worker.sh
    elif [ -f /app/exec/start-worker.sh ]; then
        exec bash /app/exec/start-worker.sh
    else
        echo "[WARN] Worker não configurado: nenhum script de start encontrado."
        exec sleep infinity
    fi
elif [ "$APP_ROLE_VALUE" == "flower" ]; then
    if [ -f /app/exec/start/flower.sh ]; then
        exec bash /app/exec/start/flower.sh
    elif [ -f /app/exec/start-flower.sh ]; then
        exec bash /app/exec/start-flower.sh
    else
        echo "[WARN] Flower não configurado: nenhum script de start encontrado."
        exec sleep infinity
    fi
else
    echo "[WARN] APP_ROLE desconhecido ($APP_ROLE_VALUE), iniciando API."
    exec bash /app/exec/start/api.sh
fi
