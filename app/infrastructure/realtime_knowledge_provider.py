from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.infrastructure.source_policy import SourceCandidate, SourceTier, domain_score


@dataclass
class RealtimeSource:
    title: str
    url: str
    snippet: str
    tier: str
    score: float


@dataclass
class RealtimeKnowledge:
    query: str
    summary: str
    key_points: list[str]
    sources: list[RealtimeSource]
    fetched_at_iso: str


class RealtimeKnowledgeProvider:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.timeout_seconds = max(1.0, float(self.settings.realtime_search_timeout_seconds))
        self.max_sources = max(1, int(self.settings.realtime_search_max_sources))
        self.cache_ttl_seconds = max(60, int(self.settings.realtime_search_cache_ttl_seconds))
        self._cache: dict[str, tuple[datetime, RealtimeKnowledge]] = {}

    def lookup(self, query: str, priority_sources: list[str] | None = None) -> RealtimeKnowledge | None:
        """
        Busca conhecimento em tempo real.

        Args:
            query: Pergunta ou termo de busca.
            priority_sources: Lista de tiers prioritários (ex: ["official", "institutional"]).
                              Ordena fontes a priorizar no ranking.

        Returns:
            RealtimeKnowledge com resumo e fontes ranqueadas, ou None se não encontrar.
        """
        cleaned_query = " ".join(query.strip().split())
        if not cleaned_query:
            return None

        cached = self._get_from_cache(cleaned_query)
        if cached is not None:
            return cached

        candidates = self._discover_candidates(cleaned_query)
        if not candidates:
            return None

        ranked = self._rank_candidates(cleaned_query, candidates, priority_sources=priority_sources)
        resolved = self._resolve_best_sources(cleaned_query, ranked)
        if resolved is not None:
            self._set_cache(cleaned_query, resolved)

        return resolved

    def _discover_candidates(self, query: str) -> list[SourceCandidate]:
        candidates: list[SourceCandidate] = []

        # Wikipedia entra como fallback, não como dominante.
        wiki = self._discover_wikipedia_candidate(query)
        if wiki is not None:
            candidates.append(wiki)

        # DuckDuckGo entra como descoberta de links, não como resposta final.
        candidates.extend(self._discover_duckduckgo_candidates(query))

        return self._deduplicate_candidates(candidates)

    def _discover_wikipedia_candidate(self, query: str) -> SourceCandidate | None:
        """
        Busca Wikipedia com fallback para simplificação de query.
        
        Estratégia:
        1. Extrai palavras-chave principais (remove stop words)
        2. Tenta query original
        3. Se falhar, tenta com keywords (maiores primeiro - mais específicas)
        4. Se falhar, tenta expansões (PIB -> Produto Interno Bruto)
        """
        # Stop words: palavras genéricas que não ajudam na busca
        stop_words = {
            "qual", "quais", "que", "o", "a", "de", "da", "do", "das", "dos",
            "e", "é", "são", "em", "para", "com", "por", "por que", "foi",
            "como", "onde", "quando", "quem", "explique", "me", "nos",
            "cores", "tipo", "tipos", "forma", "formas", "quero", "saber",
            "soma", "bens", "servico", "servicos", "produzidos", "brasil",
        }
        
        # Keywords econômicos e suas expansões
        expansions = {
            "pib": "Produto Interno Bruto",
            "gdp": "Gross Domestic Product",
            "ibovespa": "índice bovespa",
            "dolar": "dólar",
            "inflacao": "inflação",
        }
        
        # Extrai keywords principais (remove stop words e acentos para comparação)
        def extract_keywords(text: str) -> list[str]:
            normalized = unicodedata.normalize("NFD", text.lower())
            without_accents = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
            
            words = without_accents.split()
            return [w.strip(".,!?:;\"'") for w in words 
                    if len(w) > 2 and w not in stop_words]
        
        keywords = extract_keywords(query)
        
        # Sort keywords por tamanho (maiores/mais específicas primeiro)
        keywords.sort(key=len, reverse=True)
        
        # Build search queries com diferentes estratégias
        search_queries = []
        
        # 1. Query original (se não for muito longa)
        if len(query) <= 50:
            search_queries.append(query)
        
        # 2. Todos os keywords juntos
        if keywords:
            search_queries.append(" ".join(keywords))
        
        # 3. Keywords individuais (maiores primeiro)
        search_queries.extend(keywords)
        
        # 4. Expansões para termos econômicos
        for short, long in expansions.items():
            if short in " ".join(keywords):
                search_queries.append(f"{long} Brasil")
                search_queries.append(f"{long}")
                break
        
        # Remove duplicatas preservando ordem
        search_queries = list(dict.fromkeys(search_queries))
        
        best_candidate: SourceCandidate | None = None
        best_score = -1.0

        for language in ("pt", "en"):
            for search_query in search_queries:
                if not search_query or len(search_query) > 50:
                    continue
                    
                opensearch_url = (
                    f"https://{language}.wikipedia.org/w/api.php"
                    f"?action=opensearch&search={quote(search_query)}&limit=5&namespace=0&format=json"
                )
                payload = self._fetch_json(opensearch_url)
                if not isinstance(payload, list) or len(payload) < 4:
                    continue

                titles = payload[1] if isinstance(payload[1], list) else []
                links = payload[3] if isinstance(payload[3], list) else []
                if not titles or not links:
                    continue

                for idx, (raw_title, raw_url) in enumerate(zip(titles, links, strict=False)):
                    title = str(raw_title).strip()
                    url = str(raw_url).strip()
                    if not title or not url:
                        continue

                    tier, base_score = domain_score(url)
                    relevance = self._candidate_relevance(query, title, "")
                    position_bonus = max(0.0, 0.08 - idx * 0.02)
                    final_score = base_score + relevance + position_bonus

                    if final_score > best_score:
                        best_score = final_score
                        best_candidate = SourceCandidate(
                            title=title,
                            url=url,
                            snippet="Wikipedia candidate",
                            tier=tier,
                            score=min(1.0, final_score),
                        )

        if best_candidate is None or best_score < 0.55:
            return None

        return best_candidate

    def _discover_duckduckgo_candidates(self, query: str) -> list[SourceCandidate]:
        url = (
            "https://api.duckduckgo.com/"
            f"?q={quote(query)}&format=json&no_redirect=1&no_html=1"
        )
        payload = self._fetch_json(url)
        if not isinstance(payload, dict):
            return []

        results: list[SourceCandidate] = []

        abstract = str(payload.get("AbstractText") or "").strip()
        abstract_url = str(payload.get("AbstractURL") or "").strip()
        heading = str(payload.get("Heading") or query).strip()

        if abstract and abstract_url:
            tier, score = domain_score(abstract_url)
            results.append(
                SourceCandidate(
                    title=heading or self._host_label(abstract_url),
                    url=abstract_url,
                    snippet=abstract[:240],
                    tier=tier,
                    score=score,
                )
            )

        related_topics = payload.get("RelatedTopics")
        if isinstance(related_topics, list):
            for topic in related_topics:
                results.extend(self._extract_ddg_topic_candidates(topic))
                if len(results) >= self.max_sources * 3:
                    break

        return results[: self.max_sources * 3]

    def _extract_ddg_topic_candidates(self, topic: dict[str, Any]) -> list[SourceCandidate]:
        candidates: list[SourceCandidate] = []

        text = str(topic.get("Text") or "").strip()
        first_url = str(topic.get("FirstURL") or "").strip()
        if text and first_url:
            tier, score = domain_score(first_url)
            candidates.append(
                SourceCandidate(
                    title=text.split(" - ")[0][:120],
                    url=first_url,
                    snippet=text[:240],
                    tier=tier,
                    score=score,
                )
            )

        nested_topics = topic.get("Topics")
        if isinstance(nested_topics, list):
            for nested in nested_topics:
                if not isinstance(nested, dict):
                    continue
                nested_text = str(nested.get("Text") or "").strip()
                nested_url = str(nested.get("FirstURL") or "").strip()
                if nested_text and nested_url:
                    tier, score = domain_score(nested_url)
                    candidates.append(
                        SourceCandidate(
                            title=nested_text.split(" - ")[0][:120],
                            url=nested_url,
                            snippet=nested_text[:240],
                            tier=tier,
                            score=score,
                        )
                    )

        return candidates

    def _rank_candidates(
        self,
        query: str,
        candidates: list[SourceCandidate],
        priority_sources: list[str] | None = None,
    ) -> list[SourceCandidate]:
        """
        Ranqueia candidatos de fonte por tier e score.

        Prioridades:
        1. Se priority_sources fornecido, coloca tiers nessa ordem primeiro
        2. Depois: OFFICIAL > INSTITUTIONAL > TRUSTED_SECONDARY > WIKIPEDIA > GENERIC
        3. Desempate por score

        Args:
            candidates: Fontes descobertas.
            priority_sources: Lista de valores de tier para prioridade (ex: ["official", "institutional"]).

        Returns:
            Candidatos ordenados por prioridade descrescente.
        """
        tier_priority_map = {
            "official": 5,
            "institutional": 4,
            "trusted_secondary": 3,
            "wikipedia": 2,
            "generic_search": 1,
        }

        # Se há priority_sources, ajusta o mapa
        if priority_sources:
            for idx, tier_str in enumerate(priority_sources):
                tier_priority_map[tier_str] = 10 + (100 - idx * 10)

        def sort_key(candidate: SourceCandidate) -> tuple[float, float, float]:
            tier_value = tier_priority_map.get(candidate.tier.value, 0)
            relevance = self._candidate_relevance(query, candidate.title, candidate.snippet)
            composite = float(tier_value) + (relevance * 2.0) + candidate.score
            return (composite, relevance, candidate.score)

        return sorted(candidates, key=sort_key, reverse=True)

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFD", text.lower())
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

    def _tokenize(self, text: str) -> set[str]:
        stop = {
            "qual", "quais", "que", "de", "da", "do", "das", "dos", "e", "em",
            "para", "com", "por", "como", "onde", "quando", "quem", "sobre",
            "quero", "saber", "foi", "ano", "atual", "hoje",
        }
        clean = self._normalize_text(text)
        words = re.findall(r"[a-z0-9]+", clean)
        return {w for w in words if len(w) > 2 and w not in stop}

    def _candidate_relevance(self, query: str, title: str, snippet: str) -> float:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return 0.0

        candidate_tokens = self._tokenize(f"{title} {snippet}")
        if not candidate_tokens:
            return 0.0

        overlap = query_tokens.intersection(candidate_tokens)
        overlap_score = len(overlap) / max(1, len(query_tokens))

        q_norm = self._normalize_text(query)
        t_norm = self._normalize_text(title)

        has_pib_intent = any(token in q_norm for token in ("pib", "produto interno bruto", "gdp"))
        if has_pib_intent and any(token in t_norm for token in ("pib", "produto interno bruto", "gdp")):
            overlap_score += 0.35

        if has_pib_intent and "servico publico" in t_norm:
            overlap_score -= 0.25

        return max(0.0, min(1.0, overlap_score))

    def _resolve_best_sources(
        self,
        query: str,
        ranked: list[SourceCandidate],
    ) -> RealtimeKnowledge | None:
        resolved_sources: list[RealtimeSource] = []
        best_summary = ""
        best_points: list[str] = []

        for candidate in ranked[: self.max_sources]:
            extracted = self._extract_source_content(candidate)
            if extracted is None:
                continue

            summary, key_points = extracted
            
            if not best_summary:
                best_summary = summary
                best_points = key_points

            resolved_sources.append(
                RealtimeSource(
                    title=candidate.title,
                    url=candidate.url,
                    snippet=summary[:240],
                    tier=candidate.tier.value,
                    score=candidate.score,
                )
            )

        if not resolved_sources or not best_summary:
            return None

        return RealtimeKnowledge(
            query=query,
            summary=best_summary,
            key_points=best_points[:3],
            sources=resolved_sources[: self.max_sources],
            fetched_at_iso=datetime.now(timezone.utc).isoformat(),
        )

    def _extract_source_content(
        self,
        candidate: SourceCandidate,
    ) -> tuple[str, list[str]] | None:
        normalized_url = candidate.url.lower()

        # Tratamento bom para Wikipedia.
        if "wikipedia.org/wiki/" in normalized_url:
            # Extrai o título já URL-encoded
            title = candidate.url.rsplit("/", 1)[-1]
            # NÃO fazer quote() novamente - já está encoded!
            
            # Detecta linguagem corretamente
            if "pt.wikipedia" in normalized_url:
                language = "pt"
            elif "en.wikipedia" in normalized_url:
                language = "en"
            else:
                # Default português
                language = "pt"
            
            summary_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{title}"
            payload = self._fetch_json(summary_url)
            
            if not isinstance(payload, dict):
                return None
            
            summary = str(payload.get("extract") or "").strip()
            if not summary:
                return None
            
            return (summary, self._extract_key_points(summary))

        # Fallback genérico: tenta baixar HTML e extrair texto.
        html = self._fetch_text(candidate.url)
        if not html:
            return None

        text = self._extract_main_text_from_html(html)
        if not text:
            return None

        summary = text[:1200].strip()
        return (summary, self._extract_key_points(summary))

    def _extract_main_text_from_html(self, html: str) -> str:
        cleaned = unescape(html)

        cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", cleaned)
        cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", cleaned)
        cleaned = re.sub(r"(?is)<svg.*?>.*?</svg>", " ", cleaned)
        cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)

        return cleaned.strip()

    def _extract_key_points(self, text: str) -> list[str]:
        clean = " ".join(text.split())
        if not clean:
            return []
        pieces = [piece.strip() for piece in re.split(r"[.!?]", clean)]
        return [piece for piece in pieces if piece][:3]

    def _deduplicate_candidates(self, candidates: list[SourceCandidate]) -> list[SourceCandidate]:
        seen: set[str] = set()
        deduped: list[SourceCandidate] = []

        for candidate in candidates:
            key = candidate.url.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)

        return deduped

    def _host_label(self, url: str) -> str:
        try:
            return urlparse(url).netloc
        except Exception:
            return "source"

    def _fetch_json(self, url: str) -> Any | None:
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "BraumCore/1.0",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=self.timeout_seconds) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read().decode(charset, errors="replace")
                return json.loads(raw)
        except Exception:
            return None

    def _fetch_text(self, url: str) -> str | None:
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "BraumCore/1.0",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urlopen(request, timeout=self.timeout_seconds) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except Exception:
            return None

    def _get_from_cache(self, query: str) -> RealtimeKnowledge | None:
        cache_item = self._cache.get(query)
        if cache_item is None:
            return None

        expires_at, value = cache_item
        if datetime.now(timezone.utc) >= expires_at:
            self._cache.pop(query, None)
            return None
        return value

    def _set_cache(self, query: str, value: RealtimeKnowledge) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.cache_ttl_seconds)
        self._cache[query] = (expires_at, value)