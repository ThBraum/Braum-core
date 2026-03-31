from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RetrievedChunk:
    chunk_id: str
    user_id: str
    file_id: str
    file_name: str
    page: int | None
    score: float
    chunk: str


class VectorStore:
    def has_indexed_documents(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        # TODO: implementar consulta real no Qdrant/pgvector/etc
        return True

    def find_relevant_chunks(
        self,
        question: str,
        *,
        user_id: str,
        top_k: int = 12,
        score_threshold: float = 0.45,
    ) -> list[RetrievedChunk]:
        # TODO: trocar por consulta real ao seu banco vetorial
        # Exemplo esperado do retorno do banco vetorial:
        raw_results: list[dict[str, Any]] = [
            {
                "chunk_id": "c1",
                "user_id": user_id,
                "file_id": "f1",
                "file_name": "manual_interno.pdf",
                "page": 2,
                "score": 0.89,
                "chunk": "Trecho do documento relevante para a pergunta...",
            },
            {
                "chunk_id": "c2",
                "user_id": user_id,
                "file_id": "f1",
                "file_name": "manual_interno.pdf",
                "page": 3,
                "score": 0.61,
                "chunk": "Outro trecho relevante...",
            },
        ]

        filtered = [
            RetrievedChunk(**item)
            for item in raw_results
            if item["user_id"] == user_id and float(item["score"]) >= score_threshold
        ]

        return filtered[:top_k]
