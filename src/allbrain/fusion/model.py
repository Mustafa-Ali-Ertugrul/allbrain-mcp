from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


FUSION_TEMPLATE_VERSION = 1
FUSION_DEFAULT_WEIGHT = 0.25
FUSION_MIN_VARIANCE_EPSILON = 0.01
FUSION_OVERLAP_THRESHOLD = 0.8
FUSION_OVERLAP_PENALTY = 0.5
FUSION_MIN_WEIGHT = 0.05
FUSION_HYSTERESIS = 3
FUSION_SOFT_SCALING_FACTOR = 0.3


class SignalChannel(StrEnum):
    CAPABILITY = "capability"
    LEARNING = "learning"
    DYNAMICS = "dynamics"
    CAUSAL = "causal"


@dataclass(frozen=True)
class SignalVector:
    agent_id: str
    task_type: str
    capability: float
    learning: float
    dynamics: float
    causal: float


@dataclass(frozen=True)
class SignalWeights:
    capability: float
    learning: float
    dynamics: float
    causal: float

    def sum(self) -> float:
        return self.capability + self.learning + self.dynamics + self.causal


@dataclass(frozen=True)
class UnifiedScoreState:
    agent_id: str
    task_type: str
    signal_vector: SignalVector
    signal_weights: SignalWeights
    unified_score: float
    overlap_matrix: dict[str, float]
    analysis_id: str
    template_version: int = FUSION_TEMPLATE_VERSION