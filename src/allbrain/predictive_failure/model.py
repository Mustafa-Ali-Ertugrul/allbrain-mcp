from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PREDICTIVE_FAILURE_TEMPLATE_VERSION = 1

# ── Risk thresholds ────────────────────────────────────────────────
RISK_THRESHOLD_WARNING = 0.40
RISK_THRESHOLD_FAILURE = 0.70

# ── Prediction levels ──────────────────────────────────────────────
LEVEL_SAFE = "safe"
LEVEL_WARNING = "warning"
LEVEL_FAILURE = "failure"

# ── Signal-type → fault-type mapping ───────────────────────────────
SIGNAL_TO_FAULT_TYPE: dict[str, str] = {
    "retry_spike": "timeout",
    "latency_rise": "timeout",
    "circuit_breaker_open": "connection",
    "failure_pattern": "failure",
    "anomaly": "anomaly",
    "orphan": "orphan",
}

# ── Mitigation strategy mapping ────────────────────────────────────
MITIGATION_STRATEGIES: dict[str, str] = {
    "retry_spikes": "throttle_retry",
    "latency_rise": "circuit_warmup",
    "circuit_breaker_open": "rate_limit",
    "failure_pattern": "pre_rollback_snapshot",
    "anomaly": "alternative_route",
}

DEFAULT_MITIGATION = "log_warning"

STRATEGY_URGENCY: dict[str, float] = {
    "throttle_retry": 0.80,
    "circuit_warmup": 0.70,
    "rate_limit": 0.85,
    "pre_rollback_snapshot": 0.90,
    "alternative_route": 0.60,
    "log_warning": 0.30,
}


@dataclass(frozen=True)
class RiskSignal:
    """A single risk signal observed from the environment."""
    signal_type: str
    severity: float
    frequency: int
    timestamp: float = 0.0


@dataclass(frozen=True)
class FailurePrediction:
    """Result of predicting a failure from risk signals."""
    fault_id: str
    fault_type: str
    probability: float
    confidence: float
    top_signals: tuple[str, ...]
    level: str


@dataclass(frozen=True)
class MitigationPlan:
    """A planned proactive mitigation action."""
    plan_id: str
    fault_id: str
    fault_type: str
    strategy: str
    urgency: float
    expected_risk_reduction: float


@dataclass(frozen=True)
class ProactiveAction:
    """The result of executing a proactive mitigation."""
    action_id: str
    plan_id: str
    snapshot_id: str
    success: bool
    message: str
    rollback_possible: bool
