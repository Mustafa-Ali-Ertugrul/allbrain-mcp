from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

POLICY_COMPETITION_TEMPLATE_VERSION = 1

COMPETITION_SCORE_WEIGHTS: dict[str, float] = {
    "success_rate": 0.50,
    "risk_penalty": 0.20,
    "stability_bonus": 0.20,
    "drift_penalty": 0.10,
}

COMPETITION_CANDIDATE_COUNT = 3
COMPETITION_MIN_CONFIDENCE = 0.05


@dataclass(frozen=True)
class PolicyCandidate:
    policy_id: str
    fault_type: str
    strategy: str
    policy_data: dict[str, Any] = field(default_factory=dict)
    version: int = 0


@dataclass(frozen=True)
class ScoredPolicy:
    candidate: PolicyCandidate
    score: float
    success_rate: float
    risk_penalty: float
    stability_bonus: float
    drift_penalty: float


@dataclass(frozen=True)
class CompetitionResult:
    winner: ScoredPolicy
    score_map: dict[str, float]
    confidence: float
