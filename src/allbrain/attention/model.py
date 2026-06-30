from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

ATTENTION_TEMPLATE_VERSION = 1

ATTENTION_MIN_ALLOCATION = 0.10
ATTENTION_MAX_ALLOCATION = 0.60
ATTENTION_BUDGET_DEFAULT = 1.0
ATTENTION_IMPORTANCE_ALPHA = 0.10
ATTENTION_COST_CAP = 2.0
ATTENTION_REALLOCATION_THRESHOLD = 0.15
ATTENTION_DECAY = 0.99

SIGNAL_COST_CAPABILITY = 0.2
SIGNAL_COST_LEARNING = 0.3
SIGNAL_COST_DYNAMICS = 0.6
SIGNAL_COST_CAUSAL = 1.0

SIGNAL_COSTS: dict[str, float] = {
    "capability": SIGNAL_COST_CAPABILITY,
    "learning": SIGNAL_COST_LEARNING,
    "dynamics": SIGNAL_COST_DYNAMICS,
    "causal": SIGNAL_COST_CAUSAL,
}


class AttentionSignal(StrEnum):
    CAPABILITY = "capability"
    LEARNING = "learning"
    DYNAMICS = "dynamics"
    CAUSAL = "causal"


@dataclass(frozen=True)
class AttentionWeight:
    signal: str
    importance: float
    cost: float
    allocation: float


@dataclass(frozen=True)
class ResourceBudget:
    total_budget: float
    allocated_budget: dict[str, float]
    unused_budget: float

    def allocated_total(self) -> float:
        return sum(self.allocated_budget.values())


@dataclass(frozen=True)
class AttentionState:
    signal_weights: dict[str, float]
    resource_budget: ResourceBudget
    last_updated: str
    template_version: int = ATTENTION_TEMPLATE_VERSION
