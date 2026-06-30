from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SELF_REPAIR_TEMPLATE_VERSION = 1

MIN_STABILITY_THRESHOLD = 0.45
STABLE_BASELINE = 0.70
MIN_CYCLES_BETWEEN_ROLLBACKS = 3
ROLLBACK_COOLDOWN_CYCLES = 5
MAX_SNAPSHOTS_PER_FAULT = 10


@dataclass(frozen=True)
class StabilityReport:
    fault_type: str
    policy_version: int
    stability_score: float
    success_rate: float
    drift_consistency: float
    outcome_variance: float
    safety_violations: int
    is_stable: bool


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    stability_score: float
    failure_reasons: tuple[str, ...] = ()
    recommendations: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicySnapshot:
    snapshot_id: str
    policy_version: int
    fault_type: str
    created_at: float
    stats_snapshot: dict[str, Any] = field(default_factory=dict)
    stability_score: float = 0.0


@dataclass(frozen=True)
class RollbackPlan:
    rollback_id: str
    fault_type: str
    from_version: int
    to_version: int
    strategy: str
    triggered_by: str
    created_at: float


@dataclass(frozen=True)
class RecoveryReport:
    recovery_id: str
    rollback_id: str
    fault_type: str
    stabilized: bool
    post_recovery_stability: float
    cycles_to_stable: int
