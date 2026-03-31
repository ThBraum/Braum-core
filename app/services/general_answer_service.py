"""
Serviço especializado para respostas do modo GENERAL.

Usa classificação de perguntas para decidir entre:
- Busca em tempo real (fatos recentes, econômicos)
- Resposta por heurística/cache (conhecimento estável)
- Explicação estruturada (didática)
"""

import json
import logging
import re
from dataclasses import dataclass
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.domain.question_classifier import QuestionCategory, QuestionClassifier
from app.infrastructure.realtime_knowledge_provider import RealtimeKnowledgeProvider

logger = logging.getLogger(__name__)


@dataclass
class GeneralAnswerResult:
    """Resultado de uma resposta no modo GENERAL."""

    answer: str
    used_realtime: bool
    category: QuestionCategory
    sources: list[dict[str, str]] | None = None


class GeneralAnswerService:
    """Serviço para respostas a perguntas abertas (modo GENERAL)."""

    def __init__(self, knowledge_provider: RealtimeKnowledgeProvider | None = None) -> None:
        self.settings = get_settings()
        self.knowledge_provider = knowledge_provider or RealtimeKnowledgeProvider()
        self.classifier = QuestionClassifier()

    def answer(
        self,
        question: str,
        conversation_history: list[str] | None = None,
        allow_web_search: bool = True,
        force_web_search: bool = False,
    ) -> GeneralAnswerResult:
        """
        Responde a uma pergunta de modo GENERAL com estratégia otimizada.

        Args:
            question: Pergunta do usuário.
            conversation_history: Histórico de perguntas anteriores (para contexto).

        Returns:
            GeneralAnswerResult com resposta, categoria e metadados.
        """
        # Classificar pergunta
        classification = self.classifier.classify(question)
        logger.info(
            f"question_classification: category={classification.category}, "
            f"use_realtime={classification.use_realtime}, confidence={classification.confidence:.2f}"
        )

        if not allow_web_search:
            if classification.category == QuestionCategory.COMPARE:
                return self._handle_compare(question, classification)
            if classification.category == QuestionCategory.SUMMARY:
                return self._handle_summary(question, classification)
            return self._handle_stable_knowledge(question, classification)

        if force_web_search:
            forced = self._force_realtime_answer(question, classification)
            if forced is not None:
                return forced

        # Estratégia por categoria
        if classification.category == QuestionCategory.REALTIME_FACT:
            result = self._handle_realtime_fact(question, classification, conversation_history)
            if result:
                return result

        if classification.category == QuestionCategory.ECONOMIC_INDICATOR:
            result = self._handle_economic_indicator(
                question, classification, conversation_history
            )
            if result:
                return result

        if classification.category == QuestionCategory.EXPLAIN:
            result = self._handle_explain(question, classification)
            if result:
                return result

        if classification.category == QuestionCategory.COMPARE:
            return self._handle_compare(question, classification)

        if classification.category == QuestionCategory.SUMMARY:
            return self._handle_summary(question, classification)

        # Fallback: conhecimento estável
        return self._handle_stable_knowledge(question, classification)

    def _force_realtime_answer(self, question: str, classification) -> GeneralAnswerResult | None:
        if not self.settings.realtime_search_enabled:
            return None

        search_query = self._build_forced_search_query(question)
        knowledge = self.knowledge_provider.lookup(search_query)
        if knowledge is None and search_query != question:
            knowledge = self.knowledge_provider.lookup(question)
        if knowledge is None:
            return None

        sources = [
            {"title": s.title, "url": s.url, "tier": s.tier, "score": s.score}
            for s in knowledge.sources
        ]
        if not sources:
            return None

        direct_line = ""
        lower_q = question.lower()
        lower_summary = knowledge.summary.lower()
        if (
            "estado" in lower_q
            and "brasil" in lower_q
            and ("26 estados" in lower_summary or "distrito federal" in lower_summary)
        ):
            direct_line = "O Brasil tem 26 estados e 1 Distrito Federal.\n\n"

        answer = (
            f"Com base em busca web em tempo real:\n\n"
            f"{direct_line}"
            f"{knowledge.summary}\n\n"
            f"Fonte primária: {sources[0]['title']} ({sources[0]['tier']})\n"
            f"Link: {sources[0]['url']}"
        )

        return GeneralAnswerResult(
            answer=answer,
            used_realtime=True,
            category=classification.category,
            sources=sources,
        )

    def _build_forced_search_query(self, question: str) -> str:
        normalized = question.lower()

        if "estado" in normalized and "brasil" in normalized:
            return "estados do Brasil"

        cleaned = re.sub(r"[?!.:,;]", " ", normalized)
        cleaned = re.sub(
            r"\b(quantos|quantas|qual|quais|tem|temos|ha|há|no|na|nos|nas|de|do|da|dos|das|o|a|os|as)\b",
            " ",
            cleaned,
        )
        cleaned = " ".join(cleaned.split())
        return cleaned if cleaned else question

    def _handle_realtime_fact(
        self,
        question: str,
        classification,
        conversation_history: list[str] | None,
    ) -> GeneralAnswerResult | None:
        """Trata perguntas sobre fatos que mudam (ex: atual presidente)."""
        if not self.settings.realtime_search_enabled:
            logger.warning("realtime_search_disabled: falling back to stable knowledge")
            return None

        knowledge = self.knowledge_provider.lookup(question)
        if knowledge is None:
            logger.warning(f"realtime_lookup_failed: question={question}")
            return None

        logger.info(f"realtime_lookup_success: sources_count={len(knowledge.sources)}")

        sources = [
            {"title": s.title, "url": s.url, "tier": s.tier, "score": s.score}
            for s in knowledge.sources
        ]

        answer = (
            f"Com base em busca em tempo real:\n\n"
            f"{knowledge.summary}\n\n"
            f"Fontes:\n" + "\n".join(f"- {s['title']} [{s['tier']}]: {s['url']}" for s in sources)
        )

        return GeneralAnswerResult(
            answer=answer,
            used_realtime=True,
            category=classification.category,
            sources=sources,
        )

    def _handle_economic_indicator(
        self,
        question: str,
        classification,
        conversation_history: list[str] | None,
    ) -> GeneralAnswerResult | None:
        """Trata perguntas sobre indicadores econômicos com prioridade de fontes oficiais."""
        if not self.settings.realtime_search_enabled:
            logger.warning("realtime_search_disabled_for_economic: falling back")
            return None

        pib_value_result = self._try_answer_brazil_gdp_value(question)
        if pib_value_result is not None:
            return pib_value_result

        knowledge = self.knowledge_provider.lookup(
            question, priority_sources=classification.priority_sources
        )
        if knowledge is None:
            logger.warning(f"economic_lookup_failed: question={question}")
            return None

        logger.info(
            f"economic_lookup_success: top_source={knowledge.sources[0].tier if knowledge.sources else 'none'}"
        )

        sources = [
            {"title": s.title, "url": s.url, "tier": s.tier, "score": s.score}
            for s in knowledge.sources
        ]

        answer = (
            f"Baseado em dados econômicos em tempo real:\n\n"
            f"{knowledge.summary}\n\n"
            f"Fonte primária: {sources[0]['title']} ({sources[0]['tier']})\n"
            f"Link: {sources[0]['url']}"
        )

        return GeneralAnswerResult(
            answer=answer,
            used_realtime=True,
            category=classification.category,
            sources=sources,
        )

    def _try_answer_brazil_gdp_value(self, question: str) -> GeneralAnswerResult | None:
        normalized = question.lower()
        asks_pib = any(token in normalized for token in ["pib", "produto interno bruto", "gdp"])
        asks_brazil = any(token in normalized for token in ["brasil", "brazil"])
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", normalized)

        if not asks_pib or not asks_brazil or year_match is None:
            return None

        target_year = year_match.group(1)
        world_bank_url = (
            "https://api.worldbank.org/v2/country/BRA/indicator/NY.GDP.MKTP.CD"
            "?format=json&per_page=80"
        )

        payload = self._fetch_json(world_bank_url)
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            return None

        records = payload[1]
        target_value = None
        latest_available_year = None
        latest_available_value = None

        for item in records:
            if not isinstance(item, dict):
                continue
            item_year = str(item.get("date") or "").strip()
            item_value = item.get("value")
            if not item_year:
                continue
            if item_value is not None and latest_available_year is None:
                latest_available_year = item_year
                latest_available_value = item_value
            if item_year == target_year and item_value is not None:
                target_value = item_value
                break

        sources = [
            {
                "title": "World Bank - GDP (current US$) - Brazil",
                "url": world_bank_url,
                "tier": "official",
                "score": 0.95,
            }
        ]

        if target_value is not None:
            formatted_value = self._format_currency_usd(float(target_value))
            answer = (
                f"O PIB do Brasil em {target_year} (US$ corrente) foi {formatted_value}.\n\n"
                f"Fonte primária: {sources[0]['title']}\n"
                f"Link: {sources[0]['url']}"
            )
            return GeneralAnswerResult(
                answer=answer,
                used_realtime=True,
                category=QuestionCategory.ECONOMIC_INDICATOR,
                sources=sources,
            )

        fallback_line = ""
        if latest_available_year is not None and latest_available_value is not None:
            fallback_line = (
                f"Último ano disponível nessa base: {latest_available_year}, "
                f"com PIB de {self._format_currency_usd(float(latest_available_value))}.\n\n"
            )

        answer = (
            f"Não encontrei valor anual consolidado do PIB do Brasil para {target_year} "
            "na base consultada em tempo real (World Bank).\n\n"
            f"{fallback_line}"
            f"Fonte: {sources[0]['title']}\n"
            f"Link: {sources[0]['url']}"
        )

        return GeneralAnswerResult(
            answer=answer,
            used_realtime=True,
            category=QuestionCategory.ECONOMIC_INDICATOR,
            sources=sources,
        )

    def _fetch_json(self, url: str) -> dict | list | None:
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "BraumCore/1.0",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            return None

    def _format_currency_usd(self, value: float) -> str:
        if value >= 1_000_000_000_000:
            return f"US$ {value / 1_000_000_000_000:.2f} trilhões"
        if value >= 1_000_000_000:
            return f"US$ {value / 1_000_000_000:.2f} bilhões"
        return f"US$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _handle_explain(self, question: str, classification) -> GeneralAnswerResult | None:
        """Trata perguntas que pedem explicação.

        Se classification.use_realtime=True, tenta busca em tempo real primeiro.
        """
        # Se foi classificado com use_realtime=True, tenta buscar antes de retornar template
        if classification.use_realtime and self.settings.realtime_search_enabled:
            knowledge = self.knowledge_provider.lookup(question)
            if knowledge is not None:
                logger.info(f"explain_with_realtime: found {len(knowledge.sources)} sources")
                sources = [
                    {"title": s.title, "url": s.url, "tier": s.tier, "score": s.score}
                    for s in knowledge.sources
                ]

                answer = (
                    f"{knowledge.summary}\n\n"
                    f"Fonte: {sources[0]['title']} ({sources[0]['tier']})\n"
                    f"Link: {sources[0]['url']}"
                )

                return GeneralAnswerResult(
                    answer=answer,
                    used_realtime=True,
                    category=classification.category,
                    sources=sources,
                )

        # Fallback: resposta estruturada (quando não tem realtime ou falhou)
        answer = (
            f"Vou explicar '{question}':\n\n"
            "1. **Conceito central**: o que é e em que contexto aparece.\n"
            "2. **Como funciona**: mecanismo/princípios principais.\n"
            "3. **Aplicação prática**: exemplos e casos de uso.\n\n"
            "Se quiser mais detalhes em algum aspecto, me avise."
        )

        return GeneralAnswerResult(
            answer=answer,
            used_realtime=False,
            category=classification.category,
        )

    def _handle_compare(self, question: str, classification) -> GeneralAnswerResult:
        """Trata perguntas que pedem comparação."""
        answer = (
            f"Vou comparar os elementos em '{question}':\n\n"
            "1. **Definição e escopo**: diferenças fundamentais.\n"
            "2. **Vantagens e desvantagens**: prós e contras de cada um.\n"
            "3. **Casos de uso**: quando usar cada um.\n\n"
            "Se quiser uma análise mais focada, especifique o aspecto."
        )

        return GeneralAnswerResult(
            answer=answer,
            used_realtime=False,
            category=classification.category,
        )

    def _handle_summary(self, question: str, classification) -> GeneralAnswerResult:
        """Trata perguntas que pedem resumo."""
        answer = (
            f"Segue um resumo conciso de '{question}':\n\n"
            "- **Ideia central**: o ponto-chave em uma frase.\n"
            "- **Pontos essenciais**: 2-3 elementos mais importantes.\n"
            "- **Aplicação**: por que é relevante.\n\n"
            "Para expandir qualquer ponto, é só me avisar."
        )

        return GeneralAnswerResult(
            answer=answer,
            used_realtime=False,
            category=classification.category,
        )

    def _handle_stable_knowledge(self, question: str, classification) -> GeneralAnswerResult:
        """Trata perguntas sobre conhecimento estável (não muda frequentemente)."""
        answer = (
            "Com base em conhecimentos estabelecidos, posso explicar o tema de forma geral "
            "e apresentar os conceitos principais disponíveis no momento.\n\n"
            f"Sobre '{question}', o entendimento consolidado é esse contexto mais estável. "
            "Porém, para garantir informações mais atualizadas, gostaria de sugerir uma busca externa. "
            "Quer que eu procure?\n\n"
            "Ou prefere uma resposta didática sobre o tema?"
        )

        return GeneralAnswerResult(
            answer=answer,
            used_realtime=False,
            category=classification.category,
        )
