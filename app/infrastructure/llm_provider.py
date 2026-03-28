from __future__ import annotations

import re
import unicodedata

from app.core.config import get_settings
from app.infrastructure.realtime_knowledge_provider import RealtimeKnowledge, RealtimeKnowledgeProvider


class LLMProvider:
    FOLLOW_UP_MARKERS = {
        "aprofunde",
        "continue",
        "continua",
        "detalhe",
        "detalhar",
        "me de exemplos",
        "de exemplos",
        "exemplos",
        "explique melhor",
        "fale mais",
        "resuma",
        "conceito central",
        "principios principais",
        "aplicacao pratica",
        "aplicacao",
        "insights",
        "me ensina",
        "me ensine",
    }

    RECENCY_MARKERS = {
        "hoje",
        "agora",
        "atual",
        "atualmente",
        "ultimo",
        "ultimos",
        "ultimas",
        "2025",
        "2026",
        "tempo real",
        "pesquise",
        "procure",
        "noticia",
        "cotacao",
        "preco",
        "taxa",
        "pib",
    }

    FACTS_THAT_CHANGE = {
        "presidente",
        "ceo",
        "campeao",
        "campeão",
        "ranking",
        "taxa",
        "pib",
        "inflacao",
        "inflação",
        "cotacao",
        "cotação",
    }

    def __init__(self, knowledge_provider: RealtimeKnowledgeProvider | None = None) -> None:
        self.settings = get_settings()
        self.knowledge_provider = knowledge_provider or RealtimeKnowledgeProvider()

    def answer_general(self, question: str, conversation_history: list[str] | None = None) -> str:
        normalized_question = self._normalize(question)
        inferred_intent = self._infer_intent(normalized_question)

        realtime_query = self._build_realtime_query(question, normalized_question, conversation_history)
        if self._should_use_realtime(normalized_question, inferred_intent):
            realtime_knowledge = self.knowledge_provider.lookup(realtime_query)
            if realtime_knowledge is not None:
                return self._render_realtime_answer(realtime_knowledge, inferred_intent, normalized_question)

        topic_answer = self._answer_by_topic(normalized_question)
        if topic_answer:
            return topic_answer

        inferred_topic = self._infer_topic(normalized_question, conversation_history)
        return self._fallback_general_answer(inferred_topic, inferred_intent)

    def _should_use_realtime(self, normalized_question: str, inferred_intent: str) -> bool:
        if not self.settings.realtime_search_enabled:
            return False

        stripped = normalized_question.strip(" .,!?:;\"'")
        if len(stripped) < 2:
            return False

        if any(marker in stripped for marker in self.RECENCY_MARKERS):
            return True

        if inferred_intent == "fact" and any(token in stripped for token in self.FACTS_THAT_CHANGE):
            return True

        return False

    def _render_realtime_answer(
        self,
        knowledge: RealtimeKnowledge,
        inferred_intent: str,
        normalized_question: str,
    ) -> str:
        key_points = knowledge.key_points[:3]
        sources_text = "\n".join(
            f"- {source.title} [{source.tier} | {source.score:.2f}]: {source.url}"
            for source in knowledge.sources
        )
        timestamp = knowledge.fetched_at_iso

        if inferred_intent == "fact":
            years = self._extract_years(knowledge.summary)
            if any(token in normalized_question for token in {"em que ano", "que ano", "quando"}) and years:
                return (
                    f"Com base nas fontes consultadas, a resposta mais provável é: {years[0]}.\n\n"
                    f"Fontes:\n{sources_text}\n"
                    f"Atualizado em: {timestamp}"
                )

            return (
                f"Pelas fontes consultadas, encontrei: {knowledge.summary}\n\n"
                f"Fontes:\n{sources_text}\n"
                f"Atualizado em: {timestamp}"
            )

        bullet_points = "\n".join(f"- {point}" for point in key_points) if key_points else "- Sem pontos adicionais."
        return (
            f"Com base nas fontes consultadas, encontrei:\n\n"
            f"Resumo: {knowledge.summary}\n\n"
            f"Pontos-chave:\n{bullet_points}\n\n"
            f"Fontes:\n{sources_text}\n"
            f"Atualizado em: {timestamp}"
        )
        
    def answer_with_context(self, question: str, context_text: str) -> str:
        if not context_text.strip():
            return (
                "Não encontrei contexto suficiente nos documentos para responder com segurança."
            )

        return (
            "Responda usando apenas o contexto abaixo. "
            "Se a resposta não estiver claramente suportada, diga isso explicitamente.\n\n"
            f"Pergunta: {question}\n\n"
            f"Contexto:\n{context_text}\n\n"
            "Formato desejado:\n"
            "- resposta objetiva\n"
            "- pontos principais\n"
            "- referências [Fonte N] quando usar informação do contexto"
        )

    def _build_realtime_query(
        self,
        question: str,
        normalized_question: str,
        conversation_history: list[str] | None,
    ) -> str:
        if self._is_follow_up(normalized_question):
            topic_from_history = self._infer_topic_from_history(conversation_history)
            if topic_from_history:
                return topic_from_history
        return question

    def _fallback_general_answer(self, inferred_topic: str, inferred_intent: str) -> str:
        if inferred_intent == "summary":
            return f"Resumo de '{inferred_topic}': conceito central, pontos essenciais e aplicação prática."
        if inferred_intent == "deepen":
            return f"Vamos aprofundar '{inferred_topic}': fundamentos, funcionamento e casos de uso."
        return f"Posso te explicar '{inferred_topic}' de forma direta: o que é, como funciona e onde isso aparece."

    def _answer_by_topic(self, normalized_question: str) -> str | None:
        if "leis de newton" in normalized_question or ("newton" in normalized_question and "lei" in normalized_question):
            return (
                "As 3 Leis de Newton são:\n"
                "1) Inércia.\n"
                "2) F = m·a.\n"
                "3) Ação e reação."
            )
        return None

    def _infer_topic(self, normalized_question: str, conversation_history: list[str] | None = None) -> str:
        if self._is_follow_up(normalized_question):
            topic_from_history = self._infer_topic_from_history(conversation_history)
            if topic_from_history:
                return topic_from_history

        patterns = [
            r"me explique sobre (.+)",
            r"explique (.+)",
            r"o que e (.+)",
            r"como funciona (.+)",
            r"fale sobre (.+)",
            r"quero entender (.+)",
            r"me fale de (.+)",
            r"qual a diferenca entre (.+)",
            r"compare (.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, normalized_question)
            if match:
                extracted = match.group(1).strip(" .,!?:;\"'")
                if extracted:
                    return extracted

        simplified = normalized_question.strip(" .,!?:;\"'")
        return simplified if simplified else "esse tema"

    def _infer_topic_from_history(self, conversation_history: list[str] | None) -> str | None:
        if not conversation_history:
            return None

        for raw_item in reversed(conversation_history):
            normalized_item = self._normalize(raw_item)
            cleaned_item = normalized_item.strip(" .,!?:;\"'")
            if not cleaned_item or self._is_follow_up(cleaned_item):
                continue
            if len(cleaned_item.split()) >= 3:
                return cleaned_item

        return None

    def _infer_intent(self, normalized_question: str) -> str:
        if any(token in normalized_question for token in {"quem", "quando", "em que ano", "que ano", "qual"}):
            return "fact"
        if any(token in normalized_question for token in {"resuma", "resumo", "sintese"}):
            return "summary"
        if any(token in normalized_question for token in {"aprofunde", "detalhe", "explique melhor", "continue"}):
            return "deepen"
        return "explain"

    def _is_follow_up(self, normalized_question: str) -> bool:
        stripped = normalized_question.strip(" .,!?:;\"'")
        return stripped in self.FOLLOW_UP_MARKERS

    def _extract_years(self, text: str) -> list[str]:
        return re.findall(r"\b(1[0-9]{3}|20[0-9]{2})\b", text)

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFD", value)
        without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return without_accents.lower()