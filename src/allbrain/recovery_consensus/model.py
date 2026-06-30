from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CONSENSUS_TEMPLATE_VERSION = 1
MAX_CANDIDATES = 4
MIN_CANDIDATES = 3
DEFAULT_SUCCESS_WEIGHT = 0.50
DEFAULT_CONFIDENCE_WEIGHT = 0.30
DEFAULT_RISK_WEIGHT = 0.20
CONSENSUS_MIN_RATIO = 0.60

STRATEGY_PROFILES: dict[str, tuple[float, float, float]] = {
    "retry": (0.20, 0.75, 0.65),
    "rollback": (0.10, 0.90, 0.85),
    "isolate": (0.40, 0.60, 0.55),
    "repair": (0.25, 0.70, 0.60),
}

VALID_RECOVERY_STRATEGIES = frozenset(STRATEGY_PROFILES.keys())


@dataclass(frozen=True)
class CandidateStrategy:
    strategy: str
    confidence: float
    risk: float
    estimated_success: float
    explanation: str
    fault_id: str
    component: str
    template_version: int = CONSENSUS_TEMPLATE_VERSION


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: CandidateStrategy
    score: float
    rank: int


@dataclass(frozen=True)
class RecoveryDecision:
    selected_strategy: str
    consensus_score: float
    rejected_strategies: tuple[str, ...]
    reason: str
    fault_id: str
    decision_id: str
    candidate_count: int
    template_version: int = CONSENSUS_TEMPLATE_VERSION


@dataclass(frozen=True)
class RecoveryConsensusState:
    candidates: tuple[CandidateStrategy, ...] = ()
    decisions: tuple[RecoveryDecision, ...] = ()
    total_decisions: int = 0
    consensus_reached: int = 0
    rejected_count: int = 0
    version: int = CONSENSUS_TEMPLATE_VERSION
