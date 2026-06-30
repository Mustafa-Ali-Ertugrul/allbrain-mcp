from __future__ import annotations

from dataclasses import dataclass, field

MAX_CONCEPTS = 500
CONSOLIDATION_MIN_EPISODES = 3
CONSOLIDATION_THRESHOLD = 0.30
CONFIDENCE_DECAY_RATE = 0.05
SEMANTIC_TEMPLATE_VERSION = 1
DEFAULT_SEMANTIC_LIMIT = 5


@dataclass(frozen=True)
class SemanticConcept:
    concept_id: str
    pattern_signature: frozenset[str]
    episodes: tuple[str, ...]
    confidence: float
    retrieval_count: int
    last_activated: int | None
    template_version: int = SEMANTIC_TEMPLATE_VERSION


@dataclass(frozen=True)
class SemanticState:
    concepts: tuple[SemanticConcept, ...]
    total_concepts: int
    retained_concepts: int
    forgotten_concepts: int = 0
    version: int = SEMANTIC_TEMPLATE_VERSION
