from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


CAUSAL_TEMPLATE_VERSION = 1

COUNTERFACTUAL_TOP_K = 3
CAUSAL_MIN_SAMPLES = 5
CAUSAL_IMPACT_THRESHOLD = 0.05
CAUSAL_CONFIDENCE_SHRINK = 0.5

ROUTING_COUNTERFACTUAL_BONUS_WEIGHT = 0.10
ROUTING_CAUSAL_CONFIDENCE_WEIGHT = 0.05

CAUSAL_DIVERSITY_CLUSTERS = 2


class ImpactDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class CounterfactualResult:
    agent_id: str
    task_type: str
    actual_agent: str
    alternative_agent: str
    actual_outcome: float
    alternative_outcome: float
    impact_score: float
    confidence: float
    sample_count: int
    direction: str
    analysis_id: str
    template_version: int = CAUSAL_TEMPLATE_VERSION


@dataclass(frozen=True)
class CausalImpact:
    agent_id: str
    task_type: str
    alternative_agent: str
    impact_score: float
    confidence: float
    sample_count: int
    analysis_id: str
    template_version: int = CAUSAL_TEMPLATE_VERSION


@dataclass(frozen=True)
class CausalState:
    agent_id: str
    task_type: str
    counterfactuals: dict[str, dict[str, Any]] = field(default_factory=dict)
    impact_history: dict[str, dict[str, Any]] = field(default_factory=dict)
    graph_edges: int = 0
    analysis_id: str = ""
    template_version: int = CAUSAL_TEMPLATE_VERSION