# 🚀 Guia de Uso - Arquitetura Refatorada

## Início Rápido

### 1. Instalar Dependências
```bash
pip install -r requirements.txt
# ou
poetry install
```

### 2. Configurar Variáveis de Ambiente
```bash
cp .env.example .env
# Editar .env com valores locais
```

### 3. Iniciar Servidor
```bash
docker compose up --build
# ou para desenvolvimento local
uvicorn app.main:app --reload --port 8000
```

---

## Usando os Modos de Chat

### Modo GENERAL (Perguntas Abertas)

**Request**:
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Qual foi o PIB do Brasil em 2025?"
  }'
```

**Response**:
```json
{
  "session_id": "uuid",
  "mode": "GENERAL",
  "answer": "Com base em busca em tempo real:\n\n[resposta]\n\nFontes:\n- IBGE [official]: https://...",
  "used_realtime": true
}
```

**Fluxo Interno**:
```
1. GeneralAnswerService.answer(question)
2. QuestionClassifier.classify() → ECONOMIC_INDICATOR
3. GeneralAnswerService._handle_economic_indicator()
4. RealtimeKnowledgeProvider.lookup(priority_sources=["official", "institutional"])
5. Retorna: resposta com fontes ordenadas
```

---

### Modo RAG (Busca em Documentos)

**Request** (com autenticação):
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "mode": "RAG",
    "question": "Qual é a política de reembolso?"
  }'
```

**Response**:
```json
{
  "session_id": "uuid",
  "mode": "RAG",
  "answer": "Com base em seus documentos:\n\n[resposta contextualizada]\n\nCitações:\n- documento.pdf, página 5\n- outro.pdf, página 12",
  "sources": [
    {
      "chunk_id": "...",
      "file_name": "documento.pdf",
      "page": 5,
      "vector_score": 0.85,
      "lexical_score": 0.92,
      "final_score": 0.88,
      "citation": "documento.pdf, página 5"
    }
  ]
}
```

**Fluxo Interno**:
```
1. RAGService.retrieve_context(question, user_id, top_k=12)
2. VectorStore.find_relevant_chunks() → 12 chunks
3. RAGService._rerank_chunks() → lexical boost
4. Sort por final_score → top 6
5. Formata contexto com citações
6. LLMProvider.answer_with_context(question, context)
7. Retorna: resposta + chunks com scores decompostos
```

**Scores Decompostos**:
- `vector_score`: Score do embedding (0-1)
- `lexical_score`: Boost por keyword matching
- `final_score`: Média ponderada (usado para ranking)

---

### Modo SQL (Queries Seguras)

**Request** (com autenticação):
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "mode": "SQL",
    "question": "Quantos usuários temos?",
    "sql_query": "SELECT COUNT(*) as total FROM users"
  }'
```

**Response**:
```json
{
  "session_id": "uuid",
  "mode": "SQL",
  "answer": "Você tem um total de 1.234 usuários ativos em janeiro.",
  "sources": [
    {
      "total": 1234
    }
  ]
}
```

**Fluxo Interno**:
```
1. SQLService.execute_with_summary(query, question)
2. SQLService._validate_allowed_tables(query) → whitelist check
3. SQLGateway.execute_allowed_query() → executa
4. LLMProvider.summarize_sql_result(question, rows) → contextualiza
5. Retorna: resposta + rows
```

**Validação de Segurança**:
- Apenas tabelas em `SQL_ALLOWED_TABLES`
- Regex detection de FROM/JOIN
- Logging de todas as queries

---

## Como Integrar Novos Serviços

### Exemplo: Novo Serviço de Tradução

```python
# app/services/translation_service.py
from app.infrastructure.llm_provider import LLMProvider

class TranslationService:
    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm_provider = llm_provider or LLMProvider()
    
    def translate(self, text: str, target_language: str) -> str:
        # Implementar
        pass
```

### Integrar no Orchestrator

```python
# app/services/orchestrator.py
@dataclass
class ChatOrchestrator:
    # ... serviços existentes
    translation_service: TranslationService

# Na factory
def get_chat_orchestrator() -> ChatOrchestrator:
    return ChatOrchestrator(
        # ... serviços existentes
        translation_service=TranslationService(),
    )
```

### Usar no Handle Request

```python
def handle_request(self, request: ChatRequest) -> ChatResponse:
    # ... lógica existente
    
    if request.mode == ChatMode.TRANSLATE:
        result = self.translation_service.translate(
            request.question,
            request.target_language
        )
        return ChatResponse(answer=result)
```

---

## Logging e Observabilidade

### Usar Logging Estruturado

```python
import logging

logger = logging.getLogger(__name__)

# Info
logger.info(f"user_classification: category={result.category}, confidence={result.confidence:.2f}")

# Warning
logger.warning(f"realtime_lookup_failed: question={question}")

# Error
logger.error(f"sql_validation_failed: tables={disallowed_tables}")
```

### Ver Logs em JSON

```bash
# Se LOG_FILE_PATH configurado
tail -f logs/app.log | jq .

# Console output (estruturado em desenvolvimento)
```

### Redação Automática de Dados Sensíveis

O `SensitiveDataFilter` automaticamente remove:
- `password`
- `token`
- `api_key`
- `secret`
- `authorization`
- `access_token`

---

## Testes

### Testar um Serviço Específico

```python
# tests/test_general_answer_service.py
from app.services.general_answer_service import GeneralAnswerService
from app.infrastructure.realtime_knowledge_provider import RealtimeKnowledgeProvider

def test_handle_economic_indicator(mock_realtime_provider):
    service = GeneralAnswerService(knowledge_provider=mock_realtime_provider)
    result = service.answer("Qual foi o PIB do Brasil em 2025?")
    
    assert result.category == QuestionCategory.ECONOMIC_INDICATOR
    assert result.used_realtime is True
```

### Mock de Dependências

```python
from unittest.mock import Mock, patch

@patch('app.infrastructure.realtime_knowledge_provider.RealtimeKnowledgeProvider.lookup')
def test_realtime_search(mock_lookup):
    mock_lookup.return_value = RealtimeKnowledge(
        query="teste",
        summary="Resultado de teste",
        key_points=["a", "b"],
        sources=[...],
        fetched_at_iso="2025-01-01T00:00:00Z"
    )
    
    # Seu teste aqui
```

---

## Debugging

### Habilitar Modo Debug

```bash
DEBUG=true LOG_FILE_PATH=logs/debug.log python -m uvicorn app.main:app
```

### Ver Classificação de Pergunta

```python
from app.domain.question_classifier import QuestionClassifier

classifier = QuestionClassifier()
result = classifier.classify("Sua pergunta aqui")
print(f"Category: {result.category}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Keywords: {result.keywords}")
print(f"Use realtime: {result.use_realtime}")
```

### Ver Scores do RAG

```python
from app.services.rag_service import RAGService
from app.infrastructure.vector_store import VectorStore

rag = RAGService(VectorStore())
result = rag.retrieve_context("pergunta", user_id="user_123")

for chunk in result.chunks:
    print(f"Chunk {chunk.chunk_id}:")
    print(f"  Vector: {chunk.vector_score:.3f}")
    print(f"  Lexical: {chunk.lexical_score:.3f}")
    print(f"  Final: {chunk.final_score:.3f}")
    print(f"  Citation: {chunk.citation}")
```

---

## Performance Tips

### 1. Cache de Realtime Search
```python
# Configurar em .env
REALTIME_SEARCH_CACHE_TTL_SECONDS=600  # 10 minutos
```

### 2. Limitar Chunks RAG
```python
result = rag_service.retrieve_context(
    question,
    user_id,
    top_k=6,  # Primeiros 6 documentos
    max_results=3  # Retornar apenas 3 após reranking
)
```

### 3. Timeout de Busca
```python
# .env
REALTIME_SEARCH_TIMEOUT_SECONDS=1.5  # Máximo 1.5s por endpoint
```

---

## Troubleshooting

### Pergunta cai em fallback genérico
**Causa**: Classificador não detecta como realtime_fact  
**Solução**: Adicione keywords em `question_classifier.py` → `RECENCY_INDICATORS`

### RAG retorna poucos chunks
**Causa**: Score threshold muito alto  
**Solução**: Reduzir `score_threshold` em `retrieve_context()` (ex: 0.3 ao invés de 0.5)

### SQL query rejeitada
**Causa**: Tabela não está em `SQL_ALLOWED_TABLES`  
**Solução**: Adicionar tabela em `.env` → `SQL_ALLOWED_TABLES=users,products,orders,sua_tabela`

### Realtime search timeouts
**Causa**: Endpoints (Wikipedia, DuckDuckGo) lentos  
**Solução**: Aumentar `REALTIME_SEARCH_TIMEOUT_SECONDS` (ex: 2.5)

---

## Arquitetura em Diagrama

```
┌─────────────────────────────────────┐
│         API Gateway (FastAPI)       │
├─────────────────────────────────────┤
│  ChatOrchestrator (thin, roteamento)│
├─────────────────────────────────────┤
│  │  │  │
│  ├─ GeneralAnswerService    ├─ RAGService    ├─ SQLService
│  │  │  │
│  ├─ QuestionClassifier      ├─ VectorStore   ├─ SQLGateway
│  ├─ RealtimeProvider        ├─ LLMProvider   └─ LLMProvider
│  └─ LLMProvider (fallback)  └─ Reranking
│
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│   Infrastructure Layer              │
├─────────────────────────────────────┤
│  PostgreSQL │ Redis │ Qdrant │ Minio│
└─────────────────────────────────────┘
```

---

## Próximas Tarefas

- [ ] Testar modo GENERAL com perguntas reais
- [ ] Testar modo RAG com documentos do usuário
- [ ] Testar modo SQL com queries diversas
- [ ] Performance benchmark
- [ ] Adicionar novos handlers em GeneralAnswerService
- [ ] Expandir RealtimeKnowledgeProvider com APIs oficiais

---

**Documentação**: Versão 1.0  
**Última atualização**: Janeiro 2025
