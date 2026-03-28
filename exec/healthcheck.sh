#!/bin/bash

APP_ROLE_VALUE="${APP_ROLE:-${APP:-api}}"
APP_ROLE_VALUE=$(echo "$APP_ROLE_VALUE" | awk '{print tolower($0)}')

if [ "$APP_ROLE_VALUE" == "api" ]; then
    curl -f http://localhost:${API_PORT:-8000}/health || exit 1
elif [ "$APP_ROLE_VALUE" == "cron" ]; then
    exit 0
fi

exit 0
