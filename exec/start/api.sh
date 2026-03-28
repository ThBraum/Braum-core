#!/bin/bash

HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"
APP_NAME="${ASGI_APP:-app.main:app}"

GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}

DEV_MODE=$(echo "${DEV_MODE:-0}" | awk '{print tolower($0)}')

if [ "$DEV_MODE" == "0" ] || [ "$DEV_MODE" == "false" ]; then
    exec gunicorn \
        --log-config /app/exec/gunicorn.cnf \
        --bind "$HOST:$PORT" \
        --max-requests 400 \
        --max-requests-jitter 40 \
        --workers $GUNICORN_WORKERS \
        --worker-class uvicorn.workers.UvicornWorker \
        "$APP_NAME"
else
    exec uvicorn --host "$HOST" --port "$PORT" --reload "$APP_NAME"
fi
