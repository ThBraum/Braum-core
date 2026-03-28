#!/bin/bash

PYTHON_BIN="/app/.venv/bin/python"
MODULE="$1"

execute_script() {
    N_RUNNING=$(ps -ef | grep -v "grep" | grep "$MODULE" | grep "$PYTHON_BIN" | wc -l)

    if [ "$N_RUNNING" != 0 ]; then
        echo "[CRON_SCH] Script hasn't finished yet."
        exit 1
    fi

    cd /app
    echo "[CRON_SCH] Starting script."
    "$PYTHON_BIN" -m "$MODULE" 2>&1
}

execute_script >/proc/1/fd/1 2>/proc/1/fd/2
