import unittest

from app.domain.schemas import ChatMode, ChatRequest
from app.infrastructure.llm_provider import LLMProvider
from app.infrastructure.realtime_knowledge_provider import RealtimeKnowledge, RealtimeSource
from app.services.orchestrator import get_chat_orchestrator


class NoopKnowledgeProvider:
    def lookup(self, query: str) -> None:
        return None


class StaticKnowledgeProvider:
    def __init__(self, result: RealtimeKnowledge | None) -> None:
        self.result = result

    def lookup(self, query: str) -> RealtimeKnowledge | None:
        return self.result


class TrackingKnowledgeProvider:
    def __init__(self, result: RealtimeKnowledge | None = None) -> None:
        self.result = result
        self.queries: list[str] = []

    def lookup(self, query: str) -> RealtimeKnowledge | None:
        self.queries.append(query)
        return self.result


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = get_chat_orchestrator()
        self.orchestrator.llm_provider = LLMProvider(knowledge_provider=NoopKnowledgeProvider())

    def test_general_flow_returns_answer(self) -> None:
        question = "Qual é o status?"
        response = self.orchestrator.handle_request(
            ChatRequest(question=question, mode=ChatMode.GENERAL)
        )
        self.assertFalse(response.requires_login)
        self.assertTrue(response.answer)
        self.assertNotEqual(response.answer.strip(), question)

    def test_sql_flow_without_query_raises(self) -> None:
        with self.assertRaises(Exception):
            self.orchestrator.handle_request(
                ChatRequest(
                    question="Liste os registros",
                    mode=ChatMode.SQL,
                    access_token="invalid",
                )
            )

    def test_general_flow_thermodynamics_is_specific(self) -> None:
        response = self.orchestrator.handle_request(
            ChatRequest(question="Me explique sobre termodinâmica", mode=ChatMode.GENERAL)
        )
        self.assertFalse(response.requires_login)
        self.assertIn("1ª Lei", response.answer)
        self.assertIn("ΔU = Q - W", response.answer)

    def test_general_flow_understands_theory_of_strings(self) -> None:
        response = self.orchestrator.handle_request(
            ChatRequest(question="Me explique sobre a lei das cordas", mode=ChatMode.GENERAL)
        )
        self.assertFalse(response.requires_login)
        self.assertIn("Teoria das Cordas", response.answer)

    def test_general_flow_infers_topic_without_template(self) -> None:
        response = self.orchestrator.handle_request(
            ChatRequest(question="Me explique sobre ecossistemas marinhos", mode=ChatMode.GENERAL)
        )
        self.assertFalse(response.requires_login)
        self.assertIn("ecossistemas marinhos", response.answer)

    def test_provider_followup_uses_previous_topic(self) -> None:
        provider = LLMProvider(knowledge_provider=NoopKnowledgeProvider())
        answer = provider.answer_general(
            "Aprofunde",
            [
                "Me explique sobre teoria das cordas",
                "A Teoria das Cordas propõe cordas vibrantes como base das partículas.",
            ],
        )
        self.assertIn("teoria das cordas", answer.lower())

    def test_provider_detects_examples_intent(self) -> None:
        provider = LLMProvider(knowledge_provider=NoopKnowledgeProvider())
        answer = provider.answer_general("Me dê exemplos de regressão linear")
        self.assertIn("exemplos", answer.lower())
        self.assertIn("regressao linear", answer.lower())

    def test_provider_explains_chess_clearly(self) -> None:
        provider = LLMProvider(knowledge_provider=NoopKnowledgeProvider())
        answer = provider.answer_general("O que é xadrez?")
        self.assertIn("tabuleiro 8x8", answer.lower())
        self.assertIn("xeque-mate", answer.lower())

    def test_provider_answers_current_chess_champion(self) -> None:
        provider = LLMProvider(knowledge_provider=NoopKnowledgeProvider())
        answer = provider.answer_general("Quem é o atual campeão mundial de xadrez?")
        self.assertIn("gukesh", answer.lower())
        self.assertIn("março de 2026", answer.lower())

    def test_provider_gives_chess_learning_insights(self) -> None:
        provider = LLMProvider(knowledge_provider=NoopKnowledgeProvider())
        answer = provider.answer_general("Quero aprender a jogar xadrez, me ensina com insights")
        self.assertIn("treine tática", answer.lower())
        self.assertIn("plano de 30 dias", answer.lower())

    def test_provider_followup_conceito_central_uses_history_topic(self) -> None:
        provider = LLMProvider(knowledge_provider=NoopKnowledgeProvider())
        answer = provider.answer_general(
            "conceito central",
            ["Quero aprender como jogar xadrez, pode me explicar?"],
        )
        self.assertIn("xadrez", answer.lower())

    def test_provider_uses_realtime_data_when_available(self) -> None:
        provider = LLMProvider(
            knowledge_provider=StaticKnowledgeProvider(
                RealtimeKnowledge(
                    query="campeão mundial de xadrez",
                    summary="Gukesh Dommaraju é o campeão mundial clássico vigente.",
                    key_points=[
                        "Venceu Ding Liren no ciclo recente.",
                        "A FIDE mantém a listagem oficial.",
                    ],
                    sources=[
                        RealtimeSource(
                            title="FIDE",
                            url="https://www.fide.com",
                            snippet="Federação internacional",
                        )
                    ],
                    fetched_at_iso="2026-03-28T12:00:00+00:00",
                )
            )
        )

        answer = provider.answer_general("Quem é o atual campeão mundial de xadrez?")
        self.assertIn("fontes em tempo real", answer.lower())
        self.assertIn("fide", answer.lower())

    def test_provider_attempts_realtime_for_trivial_question(self) -> None:
        tracking_provider = TrackingKnowledgeProvider(result=None)
        provider = LLMProvider(knowledge_provider=tracking_provider)

        answer = provider.answer_general("Quais as cores do arco-íris?")

        self.assertTrue(tracking_provider.queries)
        self.assertNotIn("entendi que voce quer uma explicacao", answer.lower())

    def test_provider_attempts_realtime_for_followup_question(self) -> None:
        tracking_provider = TrackingKnowledgeProvider(result=None)
        provider = LLMProvider(knowledge_provider=tracking_provider)

        provider.answer_general(
            "conceito central",
            ["Quero aprender como jogar xadrez, pode me explicar?"],
        )

        self.assertTrue(tracking_provider.queries)
        self.assertIn("xadrez", tracking_provider.queries[-1].lower())

    def test_provider_chess_fallback_handles_previous_champion_question(self) -> None:
        provider = LLMProvider(knowledge_provider=NoopKnowledgeProvider())
        answer = provider.answer_general(
            "Antes do Gukesh Dommaraju, quem era o campeão mundial de xadrez?"
        )
        self.assertIn("ding liren", answer.lower())

    def test_provider_realtime_fact_question_extracts_year(self) -> None:
        provider = LLMProvider(
            knowledge_provider=StaticKnowledgeProvider(
                RealtimeKnowledge(
                    query="Em que ano ocorreu a Revolução Francesa?",
                    summary="Revolução Francesa foi um período entre 1789 e 1799 de intensa transformação política.",
                    key_points=["Começa em 1789", "Período até 1799"],
                    sources=[
                        RealtimeSource(
                            title="Revolução Francesa",
                            url="https://pt.wikipedia.org/wiki/Revolu%C3%A7%C3%A3o_Francesa",
                            snippet="Entre 1789 e 1799",
                        )
                    ],
                    fetched_at_iso="2026-03-28T12:00:00+00:00",
                )
            )
        )

        answer = provider.answer_general("Em que ano ocorreu a Revolução Francesa?")
        self.assertIn("1789", answer)
        self.assertIn("fontes consultadas em tempo real", answer.lower())


if __name__ == "__main__":
    unittest.main()
