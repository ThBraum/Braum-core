# Braum-core

<img width="2122" height="1181" alt="braum-core_ai_bpmn drawio" src="https://github.com/user-attachments/assets/fb62ef67-ad8b-4d74-bd77-584073993ccb" />

## Visão geral

Este projeto implementa uma API FastAPI com orquestração baseada no BPMN para três modos:

- `general`: sessão + contador gratuito, com login obrigatório ao ultrapassar limite.
- `rag`: valida JWT e busca chunks relevantes para resposta com fontes.
- `sql`: valida JWT, escopo de tabelas permitidas e executa consulta de forma controlada.

## Estrutura principal

- `app/main.py`: bootstrap da aplicação e rotas.
- `app/api/routes/chat.py`: endpoint `POST /api/v1/chat`.
- `app/services/orchestrator.py`: fluxo central seguindo o BPMN.
- `app/core/security.py`: validação JWT.
- `app/core/errors.py`: erro controlado da API.
- `app/infrastructure/db/models.py`: modelo SQLAlchemy para auditoria.
- `alembic/env.py`: integração do Alembic com settings e metadata do app.

## Configuração local

1. Instale dependências:

```zsh
poetry install --no-root
```

2. Crie a migration inicial:

```zsh
poetry run alembic revision --autogenerate -m "initial schema"
```

3. Aplique migrations:

```zsh
poetry run alembic upgrade head
```

4. Rode a API:

```zsh
poetry run uvicorn app.main:app --reload
```

5. Abra a interface de chat no navegador:

```zsh
http://localhost:8000/
```

## Interface de Chat (estilo assistente)

A aplicação agora expõe uma interface web responsiva em `/` com:

- Nova conversa com seleção de modo (`general`, `rag`, `sql`)
- Lista de documentos internos para RAG
- Lista de tabelas (`.csv` e `.xlsx`) para SQL
- Histórico de conversas clicável
- Gerenciamento e exclusão da conversa atual
- Upload de arquivos com thumbnail (ícone por tipo)

### Regras de autenticação na UI

- `general`: funciona sem autenticação.
- `rag` e `sql`: ao tentar usar o ícone de upload sem login, a UI solicita autenticação.
- A autenticação demo pode ser feita pela barra lateral (gera JWT local via endpoint de desenvolvimento).

### Endpoints principais da nova experiência

- `POST /api/v1/workspace/auth/dev-token`
- `POST /api/v1/workspace/conversations`
- `GET /api/v1/workspace/conversations`
- `PATCH /api/v1/workspace/conversations/{conversation_id}`
- `DELETE /api/v1/workspace/conversations/{conversation_id}`
- `GET /api/v1/workspace/conversations/{conversation_id}/messages`
- `POST /api/v1/workspace/conversations/{conversation_id}/messages`
- `POST /api/v1/workspace/files/upload`
- `GET /api/v1/workspace/files/documents`
- `GET /api/v1/workspace/files/tables`

## Gerenciamento via Docker

Este projeto usa `docker compose` (CLI moderna). O serviço da API no compose é `api`.

### Inicialização

```zsh
docker compose up -d --build
```

Se você precisar usar `sudo` no seu ambiente:

```zsh
sudo docker compose up -d --build
```

### Logs

Logs da API:

```zsh
docker compose logs -f api
```

Logs de outros serviços:

```zsh
docker compose logs -f postgres
docker compose logs -f redis
docker compose logs -f worker
docker compose logs -f flower
```

### Acessar shell do container da API

```zsh
docker compose exec api /bin/bash
```

## Alembic via Docker

### Criar nova revisão

```zsh
docker compose run --rm api alembic revision --autogenerate -m "comentario"
```

### Aplicar migrações

```zsh
docker compose run --rm api alembic upgrade head
```

### Corrigir permissões da pasta do Alembic (quando necessário)

Se os arquivos em `alembic/` forem gerados com owner `root`, execute:

```zsh
sudo chown -R "$USER" ./alembic
```

### Fluxo recomendado de atualização do Alembic

1. Gerar revisão:

```zsh
docker compose run --rm api alembic revision --autogenerate -m "comentario"
```

2. Revisar o arquivo gerado em `alembic/versions/`.
3. Aplicar atualização no banco:

```zsh
docker compose run --rm api alembic upgrade head
```

4. Ajustar owner dos arquivos (se necessário):

```zsh
sudo chown -R "$USER" ./alembic
```

## Variáveis de ambiente

- `DATABASE_URL` (default: `postgresql+psycopg://postgres:postgres@localhost:5432/braum`)
- `JWT_SECRET` (default de desenvolvimento em `app/core/config.py`)
- `JWT_ALGORITHM` (default: `HS256`)
- `FREE_GENERAL_QUESTIONS` (default: `10`)
- `REALTIME_SEARCH_ENABLED` (default: `true`)
- `REALTIME_SEARCH_TIMEOUT_SECONDS` (default: `1.8`)
- `REALTIME_SEARCH_CACHE_TTL_SECONDS` (default: `300`)
- `REALTIME_SEARCH_MAX_SOURCES` (default: `3`)

## Teste rápido

```zsh
poetry run python -m unittest app.tests.test_orchestrator
```
