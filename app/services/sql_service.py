"""
Serviço especializado para mode SQL com validação e sumarização.

Responsabilidades:
- Validação de escopo (tabelas permitidas)
- Execução segura de queries
- Sumarização contextualizadas
"""

import logging
import re

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.llm_provider import LLMProvider
from app.infrastructure.sql_gateway import SQLGateway

logger = logging.getLogger(__name__)


class SQLService:
    """Serviço para execução controlada de SQL."""

    def __init__(
        self, sql_gateway: SQLGateway | None = None, llm_provider: LLMProvider | None = None
    ) -> None:
        self.settings = get_settings()
        self.sql_gateway = sql_gateway or SQLGateway()
        self.llm_provider = llm_provider or LLMProvider()

    def execute_with_summary(self, query: str, question: str) -> dict[str, str | list]:
        """
        Executa query SQL e retorna resultado com sumarização.

        Args:
            query: Query SQL a executar.
            question: Pergunta original (para contexto de sumarização).

        Returns:
            Dict com 'rows', 'summary' e 'row_count'.

        Raises:
            AppError se query inválida ou tabela não permitida.
        """
        # Validação
        self._validate_allowed_tables(query)

        logger.info(f"sql_execute: query_len={len(query)}")

        # Execução
        rows = self.sql_gateway.execute_allowed_query(query)
        if not rows:
            logger.warning("sql_no_results")
            return {
                "rows": [],
                "summary": "A consulta não retornou resultados.",
                "row_count": 0,
            }

        # Sumarização contextualizada
        summary = self.llm_provider.summarize_sql_result(question, rows)

        logger.info(f"sql_execute_success: rows={len(rows)}")

        return {
            "rows": rows,
            "summary": summary,
            "row_count": len(rows),
        }

    def _validate_allowed_tables(self, query: str) -> None:
        """
        Valida se query usa apenas tabelas permitidas.

        Detecta FROM e JOIN, extrai nomes de tabelas.
        Levanta AppError se tabela não autorizada.
        """
        allowed_tables = {table.lower() for table in self.settings.normalized_allowed_sql_tables}

        # Regex: captura tabelas após FROM/JOIN
        detected_tables = {
            match.lower()
            for match in re.findall(
                r"(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", query, re.IGNORECASE
            )
        }

        if not detected_tables:
            logger.error("sql_no_table_detected")
            raise AppError(
                message="Não foi possível identificar tabelas na consulta SQL.",
                code="sql.no_table_detected",
                status_code=400,
            )

        disallowed_tables = sorted(detected_tables - allowed_tables)
        if disallowed_tables:
            logger.warning(f"sql_forbidden_tables: {disallowed_tables}")
            raise AppError(
                message="Consulta não permitida para as tabelas: " + ", ".join(disallowed_tables),
                code="sql.forbidden_table",
                status_code=403,
            )

        logger.debug(f"sql_validation_ok: tables={detected_tables}")
