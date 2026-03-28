from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from uuid import uuid4

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.domain.schemas import ChatMode, ChatRequest, ChatResponse
from app.infrastructure.sql_gateway import SQLGateway
from app.infrastructure.vector_store import VectorStore
from app.services.general_answer_service import GeneralAnswerService
from app.services.rag_service import RAGService
from app.services.session_manager import SessionCounter
from app.services.sql_service import SQLService

logger = logging.getLogger(__name__)


@dataclass
class ChatOrchestrator:
    """Orquestrador principal que coordena os 3 modos de chat.
    
    Responsabilidades:
    - Roteamento por modo (GENERAL, RAG, SQL)
    - Validação de acesso (login, limites)
    - Delegação para serviços especializados
    """

    session_counter: SessionCounter
    general_answer_service: GeneralAnswerService
    rag_service: RAGService
    sql_service: SQLService
    vector_store: VectorStore

    def handle_request(self, request: ChatRequest) -> ChatResponse:
        """Processa requisição de chat por modo."""
        settings = get_settings()
        session_id = request.session_id or str(uuid4())

        user_claims = None
        if request.access_token:
            user_claims = decode_access_token(request.access_token)

        # Validações de acesso
        if request.mode in {ChatMode.RAG, ChatMode.SQL} and not user_claims:
            logger.warning(f"unauthorized_request: mode={request.mode}")
            return ChatResponse(
                session_id=session_id,
                mode=request.mode,
                answer="Login obrigatório para este modo.",
                requires_login=True,
                next_action="authenticate",
            )

        # Modo GENERAL: com limite de questões gratuitas
        if request.mode == ChatMode.GENERAL:
            question_count = self.session_counter.get(session_id)
            if question_count >= settings.free_general_questions and not user_claims:
                logger.info(f"free_limit_reached: session_id={session_id}")
                return ChatResponse(
                    session_id=session_id,
                    mode=request.mode,
                    answer="Limite gratuito atingido. Faça login para continuar.",
                    requires_login=True,
                    next_action="authenticate",
                )

            logger.info(f"general_request: question={request.question[:50]}")
            general_result = self.general_answer_service.answer(request.question)
            self.session_counter.increment(session_id)

            return ChatResponse(
                session_id=session_id,
                mode=request.mode,
                answer=general_result.answer,
            )

        # Modo RAG: recuperação com documentos do usuário
        if request.mode == ChatMode.RAG:
            user_id = str(user_claims.get("sub"))
            logger.info(f"rag_request: user_id={user_id}")

            if not self.vector_store.has_indexed_documents(user_id):
                logger.warning(f"no_documents: user_id={user_id}")
                return ChatResponse(
                    session_id=session_id,
                    mode=request.mode,
                    answer="Nenhum documento indexado para o usuário.",
                    next_action="upload_and_index_documents",
                )

            rag_result = self.rag_service.retrieve_context(request.question, user_id=user_id)
            if rag_result is None:
                logger.warning(f"rag_no_context: user_id={user_id}")
                return ChatResponse(
                    session_id=session_id,
                    mode=request.mode,
                    answer="Não encontrei documentos relevantes para sua pergunta.",
                )

            answer = self.llm_provider.answer_with_context(request.question, rag_result.context_text)

            sources = [
                {
                    "chunk_id": chunk.chunk_id,
                    "file_name": chunk.file_name,
                    "page": chunk.page,
                    "vector_score": chunk.vector_score,
                    "lexical_score": chunk.lexical_score,
                    "final_score": chunk.final_score,
                    "citation": chunk.citation,
                }
                for chunk in rag_result.chunks
            ]

            return ChatResponse(
                session_id=session_id,
                mode=request.mode,
                answer=answer,
                sources=sources,
            )

        # Modo SQL: execução controlada de queries
        if request.mode == ChatMode.SQL:
            sql_query = request.sql_query
            if not sql_query:
                logger.error("sql_query_missing")
                raise AppError(
                    message="`sql_query` é obrigatório no modo SQL.",
                    code="sql.query_required",
                    status_code=422,
                )

            user_id = str(user_claims.get("sub"))
            logger.info(f"sql_request: user_id={user_id}")

            result = self.sql_service.execute_with_summary(sql_query, request.question)

            return ChatResponse(
                session_id=session_id,
                mode=request.mode,
                answer=result["summary"],
                sources=result["rows"],
            )

        logger.error(f"invalid_mode: {request.mode}")
        raise AppError(
            message="Modo de execução inválido.",
            code="mode.invalid",
            status_code=400,
        )


@lru_cache(maxsize=1)
def get_chat_orchestrator() -> ChatOrchestrator:
    """Factory para instanciar orquestrador com todas as dependências."""
    vector_store = VectorStore()
    sql_gateway = SQLGateway()

    return ChatOrchestrator(
        session_counter=SessionCounter(),
        general_answer_service=GeneralAnswerService(knowledge_provider=None),
        rag_service=RAGService(vector_store=vector_store),
        sql_service=SQLService(sql_gateway=sql_gateway, llm_provider=None),
        vector_store=vector_store,
    )