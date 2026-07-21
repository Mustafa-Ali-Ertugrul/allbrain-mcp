from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["low", "medium", "high", "critical"]

RESILIENCE_TEMPLATE_VERSION = 1
MAX_FAULTS = 200
MAX_PLANS = 100
MAX_SNAPSHOTS = 50
DEFAULT_GUARDRAIL_THRESHOLD = 0.70
ANOMALY_SEVERITY_THRESHOLD = 0.30
FAILURE_LOOKBACK = 50
RECOVERY_ORPHAN_TIMEOUT = 5
CONSECUTIVE_ANOMALY_LIMIT = 3


@dataclass(frozen=True)
class FaultRecord:
    fault_id: str
    component: str
    severity: Severity
    fault_type: str
    detected_at: int
    context: tuple[str, ...]
    resolved: bool = False
    template_version: int = RESILIENCE_TEMPLATE_VERSION


@dataclass(frozen=True)
class RecoveryPlan:
    plan_id: str
    fault_id: str
    strategy: str
    target_component: str
    priority: int
    reason: str
    parameters: dict[str, Any] = field(default_factory=dict)
    guardrail_score: float | None = None
    created_at: int = 0
    template_version: int = RESILIENCE_TEMPLATE_VERSION


@dataclass(frozen=True)
class MetricsSnapshot:
    snapshot_id: str
    component: str
    state: dict[str, Any]
    created_at: int
    event_id: str = ""
    pipeline_stage: str = ""


@dataclass(frozen=True)
class ResilienceState:
    faults: tuple[FaultRecord, ...] = ()
    plans: tuple[RecoveryPlan, ...] = ()
    snapshots: tuple[MetricsSnapshot, ...] = ()
    total_faults: int = 0
    recovered: int = 0
    failed_recoveries: int = 0
    open_incidents: int = 0
    version: int = RESILIENCE_TEMPLATE_VERSION
