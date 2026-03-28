"""
Classificador de perguntas para determinar a estratégia de resposta otimizada.
"""

from dataclasses import dataclass
from enum import Enum
import re


class QuestionCategory(str, Enum):
    """Categorias de perguntas com estratégias específicas de resposta."""

    STABLE_KNOWLEDGE = "stable_knowledge"
    REALTIME_FACT = "realtime_fact"
    ECONOMIC_INDICATOR = "economic_indicator"
    EXPLAIN = "explain"
    COMPARE = "compare"
    SUMMARY = "summary"
    PROCEDURAL = "procedural"


@dataclass
class ClassificationResult:
    category: QuestionCategory
    confidence: float  # 0.0 a 1.0
    use_realtime: bool
    priority_sources: list[str] | None = None  # ex: ["official", "institutional"]
    keywords: list[str] | None = None


class QuestionClassifier:
    """Classifica perguntas para otimizar a estratégia de busca e resposta."""

    RECENCY_INDICATORS = {
        "hoje",
        "agora",
        "atual",
        "atualmente",
        "ultimo",
        "ultimos",
        "ultimas",
        "recente",
        "tempo real",
        "2025",
        "2026",
        "agora",
        "recentemente",
    }

    ECONOMIC_TERMS = {
        "pib",
        "inflacao",
        "inflação",
        "taxa",
        "cotacao",
        "cotação",
        "bolsa",
        "indice",
        "índice",
        "desemprego",
        "renda",
        "salario",
        "salário",
        "deficit",
        "déficit",
        "reserva",
        "cambio",
        "câmbio",
    }

    FACTS_THAT_CHANGE = {
        "presidente",
        "ceo",
        "diretor",
        "campeao",
        "campeão",
        "ranking",
        "lider",
        "líder",
        "ministro",
    }

    EXPLAIN_PATTERNS = [
        r"o que (e|é|são)",
        r"quais",
        r"quais (sao|são)",
        r"como funciona",
        r"explique",
        r"defina",
        r"me explique sobre",
    ]

    COMPARE_PATTERNS = [
        r"compare",
        r"diferenca",
        r"diferença",
        r"versus",
        r"vs\.",
        r"vs",
        r"em relacao a",
        r"em relação a",
    ]

    SUMMARY_PATTERNS = [
        r"resuma",
        r"resumo",
        r"sintese",
        r"síntese",
        r"em poucas palavras",
    ]

    @classmethod
    def classify(cls, question: str) -> ClassificationResult:
        """
        Classifica a pergunta e retorna uma estratégia de resposta.

        Retorna:
            ClassificationResult com categoria, confiança e configurações.
        """
        normalized = cls._normalize(question)
        keywords = cls._extract_keywords(normalized)

        # Detectar padrões de pergunta
        intent_category = cls._detect_intent(normalized)

        # Verificar se é pergunta factual que muda
        if cls._is_changing_fact(normalized, keywords):
            if cls._has_recency_indicators(normalized, keywords):
                return ClassificationResult(
                    category=QuestionCategory.REALTIME_FACT,
                    confidence=0.95,
                    use_realtime=True,
                    keywords=keywords,
                )

        # Detectar econômico/indicador
        if cls._is_economic_indicator(normalized, keywords):
            return ClassificationResult(
                category=QuestionCategory.ECONOMIC_INDICATOR,
                confidence=0.90,
                use_realtime=True,
                priority_sources=["official", "institutional"],
                keywords=keywords,
            )

        # Detectar recência geral (outro indicador de realtime)
        if cls._has_recency_indicators(normalized, keywords):
            return ClassificationResult(
                category=QuestionCategory.REALTIME_FACT,
                confidence=0.75,
                use_realtime=True,
                keywords=keywords,
            )

        # Padrões de explicitação/comparação/resumo
        if intent_category == QuestionCategory.COMPARE:
            return ClassificationResult(
                category=QuestionCategory.COMPARE,
                confidence=0.85,
                use_realtime=False,
                keywords=keywords,
            )

        if intent_category == QuestionCategory.SUMMARY:
            return ClassificationResult(
                category=QuestionCategory.SUMMARY,
                confidence=0.85,
                use_realtime=False,
                keywords=keywords,
            )

        if intent_category == QuestionCategory.EXPLAIN:
            # Perguntas EXPLAIN podem ter respostas factuais em tempo real
            # Ex: "Quais as cores do arco-íris?" → busca Wikipedia
            return ClassificationResult(
                category=QuestionCategory.EXPLAIN,
                confidence=0.85,
                use_realtime=True,  # Permite busca realtime para EXPLAIN
                keywords=keywords,
            )

        # Fallback: conhecimento estável (não muda frequentemente)
        return ClassificationResult(
            category=QuestionCategory.STABLE_KNOWLEDGE,
            confidence=0.50,
            use_realtime=False,
            keywords=keywords,
        )

    @classmethod
    def _normalize(cls, text: str) -> str:
        """Normaliza texto para análise."""
        import unicodedata

        normalized = unicodedata.normalize("NFD", text)
        without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return without_accents.lower().strip()

    @classmethod
    def _extract_keywords(cls, normalized: str) -> list[str]:
        """Extrai palavras-chave da pergunta."""
        words = normalized.split()
        return [w.strip(" .,!?:;\"'") for w in words if len(w) > 2]

    @classmethod
    def _detect_intent(cls, normalized: str) -> QuestionCategory:
        """Detecta a intenção explícita da pergunta."""
        for pattern in cls.EXPLAIN_PATTERNS:
            if re.search(pattern, normalized):
                return QuestionCategory.EXPLAIN

        for pattern in cls.COMPARE_PATTERNS:
            if re.search(pattern, normalized):
                return QuestionCategory.COMPARE

        for pattern in cls.SUMMARY_PATTERNS:
            if re.search(pattern, normalized):
                return QuestionCategory.SUMMARY

        return QuestionCategory.STABLE_KNOWLEDGE

    @classmethod
    def _is_changing_fact(cls, normalized: str, keywords: list[str]) -> bool:
        """Verifica se a pergunta é sobre um fato que muda com frequência."""
        for fact_term in cls.FACTS_THAT_CHANGE:
            if fact_term in normalized:
                return True

        for kw in keywords:
            if kw in cls.FACTS_THAT_CHANGE:
                return True

        return False

    @classmethod
    def _is_economic_indicator(cls, normalized: str, keywords: list[str]) -> bool:
        """Verifica se a pergunta é sobre indicador econômico."""
        for econ_term in cls.ECONOMIC_TERMS:
            if econ_term in normalized:
                return True

        for kw in keywords:
            if kw in cls.ECONOMIC_TERMS:
                return True

        return False

    @classmethod
    def _has_recency_indicators(cls, normalized: str, keywords: list[str]) -> bool:
        """Verifica se há indicadores de recência na pergunta."""
        for recency in cls.RECENCY_INDICATORS:
            if recency in normalized:
                return True

        for kw in keywords:
            if kw in cls.RECENCY_INDICATORS:
                return True

        return False
