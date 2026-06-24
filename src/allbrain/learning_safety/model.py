from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LEARNING_SAFETY_TEMPLATE_VERSION = 1

DEFAULT_BASE_EPSILON = 0.10
DEFAULT_DECAY_RATE = 0.95

MAX_SIMULATION_WEIGHT = 0.70

DRIFT_THRESHOLD = 0.30
MIN_RECENT_RECORDS = 5

SAFETY_EXPLORATION_TRIGGERED = "exploration_triggered"
SAFETY_SIMULATION_WEIGHT_CAPPED = "simulation_weight_capped"
SAFETY_LEARNING_DRIFT_DETECTED = "learning_drift_detected"


@dataclass(frozen=True)
class EntropyState:
    entropy: float
    n_strategies: int
    epsilon_current: float
    cycle_count: int


@dataclass(frozen=True)
class ExplorationDecision:
    fault_type: str
    signal_type: str
    selected_strategy: str
    was_exploration: bool
    epsilon: float
    entropy_at_decision: float


@dataclass(frozen=True)
class SafetyEvent:
    event_type: str
    fault_type: str
    signal_type: str
    metric_value: float
    threshold: float
    details: dict[str, Any] = field(default_factory=dict)
