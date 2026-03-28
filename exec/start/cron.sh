#!/bin/bash

DEV_MODE=$(echo "${DEV_MODE:-0}" | awk '{print tolower($0)}')
CORS_LOCALHOST=$(echo "${CORS_LOCALHOST:-0}" | awk '{print tolower($0)}')

if [ "$DEV_MODE" == "0" ] || [ "$DEV_MODE" == "false" ]; then
    cp /app/exec/cron/cron_job /etc/cron.d/cron_job
    chmod 0644 /etc/cron.d/cron_job
    crontab /etc/cron.d/cron_job
fi

printenv | grep -v "no_proxy" >> /etc/environment

NOW=$(date -Iseconds)
echo "[$NOW] [*] [CRON_SCH] Scheduler started."

exec cron -f