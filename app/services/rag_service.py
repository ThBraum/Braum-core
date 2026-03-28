from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.infrastructure.vector_store import RetrievedChunk, VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RerankedChunk:
    """Chunk após reranking com scores e citações estruturadas."""

    chunk_id: str
    user_id: str
    file_id: str
    file_name: str
    page: int | None
    vector_score: float
    lexical_score: float
    final_score: float
    chunk: str
    citation: str


@dataclass
class RAGResult:
    query: str
    user_id: str
    context_text: str
    chunks: list[RerankedChunk]
    total_tokens: int


class RAGService:
    """Serviço de busca e recuperação com reranking e citações estruturadas."""

    def __init__(self, vector_store: VectorStore) -> None:
        self.vector_store = vector_store

    def retrieve_context(
        self,
        question: str,
        user_id: str,
        top_k: int = 12,
        score_threshold: float = 0.45,
        max_results: int = 6,
    ) -> RAGResult | None:
        """
        Recupera contexto relevante com reranking.

        Args:
            question: Pergunta/query de busca.
            user_id: ID do usuário para filtragem.
            top_k: Chunks iniciais a recuperar.
            score_threshold: Score mínimo do vetor.
            max_results: Máximo de chunks a retornar (após reranking).

        Returns:
            RAGResult com contexto e metadata, ou None se vazio.
        """
        logger.info(f"rag_retrieve_start: user_id={user_id}, question_len={len(question)}")

        chunks = self.vector_store.find_relevant_chunks(
            question,
            user_id=user_id,
            top_k=top_k,
            score_threshold=score_threshold,
        )

        if not chunks:
            logger.warning(f"rag_no_chunks: user_id={user_id}")
            return None

        logger.info(f"rag_raw_chunks: count={len(chunks)}, top_score={chunks[0].score:.3f}")

        reranked = self._rerank_chunks(question, chunks)[:max_results]
        context_text = self._build_structured_context(reranked)
        total_tokens = self._estimate_tokens(context_text)

        logger.info(f"rag_retrieve_success: final_chunks={len(reranked)}, tokens≈{total_tokens}")

        return RAGResult(
            query=question,
            user_id=user_id,
            context_text=context_text,
            chunks=reranked,
            total_tokens=total_tokens,
        )

    def _rerank_chunks(self, question: str, chunks: list[RetrievedChunk]) -> list[RerankedChunk]:
        """
        Reranking lexical: aumenta score de chunks com palavras-chave da pergunta.

        Método:
        1. Extrai termos da pergunta (>3 chars)
        2. Para cada chunk, conta palavras-chave encontradas
        3. lexical_score = vector_score * (1 + keyword_ratio * 0.3)
        4. final_score = média ponderada
        """
        question_terms = set(self._tokenize(question))
        if not question_terms:
            question_terms = {word for word in question.lower().split()}

        logger.debug(f"rerank_question_terms: {question_terms}")

        reranked: list[RerankedChunk] = []

        for chunk in chunks:
            chunk_terms = set(self._tokenize(chunk.chunk))
            matched = len(question_terms & chunk_terms)
            keyword_ratio = matched / max(len(question_terms), 1)

            lexical_score = chunk.score * (1 + keyword_ratio * 0.3)
            final_score = (chunk.score + lexical_score) / 2

            reranked.append(
                RerankedChunk(
                    chunk_id=chunk.chunk_id,
                    user_id=chunk.user_id,
                    file_id=chunk.file_id,
                    file_name=chunk.file_name,
                    page=chunk.page,
                    vector_score=chunk.score,
                    lexical_score=lexical_score,
                    final_score=final_score,
                    chunk=chunk.chunk,
                    citation=self._format_citation(chunk),
                )
            )

        # Sort por final_score
        return sorted(reranked, key=lambda c: c.final_score, reverse=True)

    def _build_structured_context(self, chunks: list[RerankedChunk]) -> str:
        """Monta contexto com citações estruturadas."""
        parts: list[str] = []

        for idx, chunk in enumerate(chunks, start=1):
            citation = f"[Fonte {idx}: {chunk.citation}]"
            parts.append(f"{citation}\n{chunk.chunk.strip()}")

        return "\n\n".join(parts)

    def _format_citation(self, chunk: RetrievedChunk) -> str:
        """Formata citação como 'arquivo.pdf, página 5' ou 'arquivo.pdf'."""
        citation = chunk.file_name
        if chunk.page is not None:
            citation += f", página {chunk.page}"
        return citation

    def _tokenize(self, text: str) -> list[str]:
        """Extrai tokens: palavras com 3+ caracteres."""
        return [word for word in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(word) > 3]

    def _estimate_tokens(self, text: str) -> int:
        """Estimativa simples: ~1 token por 4 caracteres."""
        return max(1, len(text) // 4)