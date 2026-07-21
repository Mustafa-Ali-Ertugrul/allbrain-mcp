from __future__ import annotations

from typing import Any

from allbrain.domains.governance.resilience.model import RESILIENCE_TEMPLATE_VERSION

ANOMALY_DETECTED_KEYS: frozenset[str] = frozenset({"fault_id", "component", "severity", "fault_type", "detected_at"})
RECOVERY_PLANNED_KEYS: frozenset[str] = frozenset(
    {"plan_id", "fault_id", "strategy", "target_component", "priority", "reason"}
)
RECOVERY_CANCELLED_KEYS: frozenset[str] = frozenset({"plan_id", "reason"})
SNAPSHOT_CREATED_KEYS: frozenset[str] = frozenset({"snapshot_id", "component", "created_at"})
FAILURE_ANALYZED_KEYS: frozenset[str] = frozenset({"fault_id", "root_cause", "confidence"})

VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_STRATEGIES = {"retry", "rollback", "isolate", "repair"}


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_anomaly_detected(p: dict[str, Any]) -> None:
    m = ANOMALY_DETECTED_KEYS - set(p.keys())
    if m:
        raise ValueError("anomaly_detected missing: " + str(m))
    if not isinstance(p.get("fault_id"), str):
        raise ValueError("fault_id must be str")
    if p.get("severity") not in VALID_SEVERITIES:
        raise ValueError("severity must be one of " + str(VALID_SEVERITIES))
    if not isinstance(p.get("detected_at"), int):
        raise ValueError("detected_at must be int")


def validate_recovery_planned(p: dict[str, Any]) -> None:
    m = RECOVERY_PLANNED_KEYS - set(p.keys())
    if m:
        raise ValueError("recovery_planned missing: " + str(m))
    if not isinstance(p.get("plan_id"), str):
        raise ValueError("plan_id must be str")
    if p.get("strategy") not in VALID_STRATEGIES:
        raise ValueError("strategy must be one of " + str(VALID_STRATEGIES))
    prio = p.get("priority")
    if not isinstance(prio, int) or not (1 <= prio <= 5):
        raise ValueError("priority must be int between 1 and 5")
    if not isinstance(p.get("reason"), str):
        raise ValueError("reason must be str")


def validate_recovery_cancelled(p: dict[str, Any]) -> None:
    m = RECOVERY_CANCELLED_KEYS - set(p.keys())
    if m:
        raise ValueError("recovery_cancelled missing: " + str(m))
    if not isinstance(p.get("plan_id"), str):
        raise ValueError("plan_id must be str")
    if not isinstance(p.get("reason"), str):
        raise ValueError("reason must be str")


def validate_snapshot_created(p: dict[str, Any]) -> None:
    m = SNAPSHOT_CREATED_KEYS - set(p.keys())
    if m:
        raise ValueError("snapshot_created missing: " + str(m))
    if not isinstance(p.get("snapshot_id"), str):
        raise ValueError("snapshot_id must be str")
    if not isinstance(p.get("created_at"), int):
        raise ValueError("created_at must be int")


def validate_failure_analyzed(p: dict[str, Any]) -> None:
    m = FAILURE_ANALYZED_KEYS - set(p.keys())
    if m:
        raise ValueError("failure_analyzed missing: " + str(m))
    if not isinstance(p.get("fault_id"), str):
        raise ValueError("fault_id must be str")
    if not isinstance(p.get("root_cause"), str):
        raise ValueError("root_cause must be str")
    conf = p.get("confidence")
    if not isinstance(conf, (int, float)):
        raise ValueError("confidence must be numeric")


# ---------------------------------------------------------------------------
# Payload makers
# ---------------------------------------------------------------------------


def make_anomaly_detected_payload(
    *,
    fault_id: str,
    component: str,
    severity: str,
    fault_type: str,
    detected_at: int,
    tv: int = RESILIENCE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_id": fault_id,
        "component": component,
        "severity": severity,
        "fault_type": fault_type,
        "detected_at": detected_at,
        "template_version": tv,
    }
    validate_anomaly_detected(p)
    return p


def make_recovery_planned_payload(
    *,
    plan_id: str,
    fault_id: str,
    strategy: str,
    target_component: str,
    priority: int,
    reason: str,
    tv: int = RESILIENCE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "plan_id": plan_id,
        "fault_id": fault_id,
        "strategy": strategy,
        "target_component": target_component,
        "priority": priority,
        "reason": reason,
        "template_version": tv,
    }
    validate_recovery_planned(p)
    return p


def make_recovery_cancelled_payload(
    *,
    plan_id: str,
    reason: str,
    tv: int = RESILIENCE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "plan_id": plan_id,
        "reason": reason,
        "template_version": tv,
    }
    validate_recovery_cancelled(p)
    return p


def make_snapshot_created_payload(
    *,
    snapshot_id: str,
    component: str,
    created_at: int,
    tv: int = RESILIENCE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "component": component,
        "created_at": created_at,
        "template_version": tv,
    }
    validate_snapshot_created(p)
    return p


def make_failure_analyzed_payload(
    *,
    fault_id: str,
    root_cause: str,
    confidence: float,
    tv: int = RESILIENCE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_id": fault_id,
        "root_cause": root_cause,
        "confidence": float(confidence),
        "template_version": tv,
    }
    validate_failure_analyzed(p)
    return p
