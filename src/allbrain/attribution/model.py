from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


ATTRIBUTION_TEMPLATE_VERSION = 1
ATTRIBUTION_MIN_CONTRIBUTION = 0.05
ATTRIBUTION_CONFIDENCE_ALPHA = 0.10
ATTRIBUTION_COUNTERFACTUAL_WEIGHT = 0.30
ATTRIBUTION_PROPORTIONAL_WEIGHT = 0.70
ATTRIBUTION_CF_CONFIDENCE = 0.5
ATTRIBUTION_COUNTERFACTUAL_INTERVAL = 10
ATTRIBUTION_IMPORTANCE_THRESHOLD = 0.10
ATTRIBUTION_HYSTERESIS = 3
ATTRIBUTION_DECAY = 0.99


class AttributionSignal(StrEnum):
    CAPABILITY = "capability"
    LEARNING = "learning"
    DYNAMICS = "dynamics"
    CAUSAL = "causal"


@dataclass(frozen=True)
class CreditAllocation:
    signal: str
    contribution: float
    confidence: float


@dataclass(frozen=True)
class AttributionResult:
    decision_id: str
    mode: str
    reward: float
    allocations: tuple[CreditAllocation, ...]
    analysis_id: str = ""
    template_version: int = ATTRIBUTION_TEMPLATE_VERSION


@dataclass(frozen=True)
class AttributionState:
    decision_id: str
    signal_rewards: dict[str, float] = field(default_factory=dict)
    signal_counts: dict[str, int] = field(default_factory=dict)
    signal_importance_history: dict[str, int] = field(default_factory=dict)
    last_updated: str = ""
    template_version: int = ATTRIBUTION_TEMPLATE_VERSION