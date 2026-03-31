from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceTier(str, Enum):
    OFFICIAL = "official"
    INSTITUTIONAL = "institutional"
    TRUSTED_SECONDARY = "trusted_secondary"
    WIKIPEDIA = "wikipedia"
    SEARCH_RESULT = "search_result"


@dataclass(frozen=True)
class SourceCandidate:
    title: str
    url: str
    snippet: str
    tier: SourceTier
    score: float


OFFICIAL_DOMAINS = {
    "gov.br",
    "ibge.gov.br",
    "bcb.gov.br",
    "planalto.gov.br",
    "in.gov.br",
    "fide.com",
    "who.int",
    "imf.org",
    "worldbank.org",
    "oecd.org",
    "un.org",
}

INSTITUTIONAL_DOMAINS = {
    "edu",
    "org",
}

TRUSTED_SECONDARY_DOMAINS = {
    "britannica.com",
    "investopedia.com",
    "ourworldindata.org",
}

WIKIPEDIA_DOMAINS = {
    "wikipedia.org",
}


def domain_score(url: str) -> tuple[SourceTier, float]:
    normalized = url.lower()

    if any(domain in normalized for domain in OFFICIAL_DOMAINS):
        return (SourceTier.OFFICIAL, 1.00)

    if any(domain in normalized for domain in TRUSTED_SECONDARY_DOMAINS):
        return (SourceTier.TRUSTED_SECONDARY, 0.82)

    if any(domain in normalized for domain in WIKIPEDIA_DOMAINS):
        return (SourceTier.WIKIPEDIA, 0.60)

    if any(domain in normalized for domain in INSTITUTIONAL_DOMAINS):
        return (SourceTier.INSTITUTIONAL, 0.72)

    return (SourceTier.SEARCH_RESULT, 0.35)
