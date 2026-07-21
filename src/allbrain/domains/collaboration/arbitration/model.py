from __future__ import annotations

from dataclasses import dataclass

ARBITRATION_TEMPLATE_VERSION = 1

VOTE_CONFIDENCE_WEIGHT = 0.4
VOTE_REPUTATION_WEIGHT = 0.4
VOTE_TRUST_WEIGHT = 0.2

ARBITRATION_METHODS: frozenset[str] = frozenset({"majority", "weighted"})


@dataclass(frozen=True)
class VoteRecord:
    agent_id: str
    candidate_id: str
    confidence: float
    reputation: float
    calibrated_trust: float


@dataclass(frozen=True)
class ArbitrationState:
    context_key: str
    winner_candidate: str | None
    agreement_ratio: float
    arbitration_score: float
    vote_count: int
    method: str
    analysis_id: str
    template_version: int = ARBITRATION_TEMPLATE_VERSION
