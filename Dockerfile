FROM python:3.10-slim-bookworm AS python_base

WORKDIR /app
ENV \
    # python
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # venv path
    PATH="/app/.venv/bin:${PATH}"

FROM python_base AS poetry_base

ARG POETRY_VERSION=2.1.4
RUN pip install "poetry==${POETRY_VERSION}" && \
    poetry config virtualenvs.in-project true

COPY ./pyproject.toml ./poetry.lock ./
RUN poetry install --only main

FROM python_base

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates cron curl libpq5 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=poetry_base /app /app/
RUN mkdir -p /app/templates/email
COPY ./exec /app/exec
COPY ./alembic /app/alembic
COPY ./app /app/app

ARG DEV=0 VERSION
ENV DEV_MODE=${DEV} APP_VERSION=${VERSION}

HEALTHCHECK CMD ["bash", "/app/exec/healthcheck.sh"]
CMD ["bash", "/app/exec/start.sh"]
