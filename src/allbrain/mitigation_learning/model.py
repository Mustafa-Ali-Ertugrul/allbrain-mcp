from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MITIGATION_LEARNING_TEMPLATE_VERSION = 1

MIN_USES_FOR_OPTIMIZER = 4
MIN_USES_FOR_DISABLE = 5
DISABLE_SUCCESS_RATE_THRESHOLD = 0.32
POLICY_UPDATE_MIN_RECORDS = 10
POLICY_UPDATE_SUCCESS_RATE_DELTA = 0.10
LEARNING_EMA_ALPHA = 0.30

STRATEGY_BASE_EFFECTIVENESS: dict[str, float] = {
    "throttle_retry": 0.70,
    "circuit_warmup": 0.65,
    "rate_limit": 0.75,
    "pre_rollback_snapshot": 0.85,
    "alternative_route": 0.60,
    "log_warning": 0.20,
}


@dataclass(frozen=True)
class OutcomeRecord:
    outcome_id: str
    fault_id: str
    fault_type: str
    plan_id: str
    strategy: str
    pre_risk: float
    post_risk: float
    risk_delta: float
    failure_prevented: bool
    stability_delta: float
    timestamp: float


@dataclass(frozen=True)
class LearningRecord:
    learning_id: str
    fault_id: str
    fault_type: str
    signal_type: str
    strategy: str
    effectiveness_score: float
    success: bool
    occurred_at: float
    policy_version: int = 0


@dataclass
class StrategyStats:
    fault_type: str
    signal_type: str
    strategy: str
    total_uses: int = 0
    successes: int = 0
    failures: int = 0
    avg_effectiveness: float = 0.0
    success_rate: float = 0.0
    last_used_at: float = 0.0
    disabled: bool = False


@dataclass(frozen=True)
class PolicyVersion:
    version: int
    created_at: float
    fault_type: str
    strategy_preferences: dict[str, float] = field(default_factory=dict)
    disabled_strategies: frozenset[str] = field(default_factory=frozenset)
    urgency_multipliers: dict[str, float] = field(default_factory=dict)
    stats_snapshot: dict[str, Any] = field(default_factory=dict)
