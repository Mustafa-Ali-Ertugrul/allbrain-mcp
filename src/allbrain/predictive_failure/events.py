from __future__ import annotations

from typing import Any

from allbrain.predictive_failure.model import PREDICTIVE_FAILURE_TEMPLATE_VERSION

# ── Key sets ───────────────────────────────────────────────────────

SIGNAL_DETECTED_KEYS: frozenset[str] = frozenset({
    "fault_id", "signal_type", "severity", "frequency",
})
RISK_COMPUTED_KEYS: frozenset[str] = frozenset({
    "fault_id", "fault_type", "risk_score", "contributing_signal_types",
})
FAILURE_PREDICTED_KEYS: frozenset[str] = frozenset({
    "fault_id", "fault_type", "probability", "confidence", "level",
})
MITIGATION_PLANNED_KEYS: frozenset[str] = frozenset({
    "plan_id", "fault_id", "fault_type", "strategy", "urgency",
    "expected_risk_reduction",
})
RECOVERY_EXECUTED_KEYS: frozenset[str] = frozenset({
    "action_id", "plan_id", "snapshot_id", "success", "message",
    "rollback_possible",
})
FAILURE_AVOIDED_KEYS: frozenset[str] = frozenset({
    "fault_id", "original_probability", "mitigation_strategy", "snapshot_id",
})

# ── Internal helpers ───────────────────────────────────────────────


def _check_keys(p: dict[str, Any], keys: frozenset[str], label: str) -> None:
    missing = keys - set(p.keys())
    if missing:
        raise ValueError(f"{label} missing: {missing}")


def _check_str(v: Any, label: str) -> str:
    if not isinstance(v, str):
        raise ValueError(f"{label} must be str, got {type(v).__name__}")
    return v


def _check_float_in_range(
    v: Any, label: str, lo: float = 0.0, hi: float = 1.0,
) -> float:
    if not isinstance(v, (int, float)):
        raise ValueError(f"{label} must be numeric, got {type(v).__name__}")
    f = float(v)
    if not (lo <= f <= hi):
        raise ValueError(f"{label} must be in [{lo}, {hi}], got {f}")
    return f


def _check_int_ge(v: Any, label: str, minimum: int = 0) -> int:
    if not isinstance(v, int):
        raise ValueError(f"{label} must be int, got {type(v).__name__}")
    if v < minimum:
        raise ValueError(f"{label} must be >= {minimum}, got {v}")
    return v


# ── Validators ─────────────────────────────────────────────────────


def validate_signal_detected(p: dict[str, Any]) -> None:
    _check_keys(p, SIGNAL_DETECTED_KEYS, "signal_detected")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["signal_type"], "signal_type")
    _check_float_in_range(p["severity"], "severity")
    _check_int_ge(p["frequency"], "frequency", 0)


def validate_risk_computed(p: dict[str, Any]) -> None:
    _check_keys(p, RISK_COMPUTED_KEYS, "risk_computed")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["fault_type"], "fault_type")
    _check_float_in_range(p["risk_score"], "risk_score")
    signal_types = p.get("contributing_signal_types")
    if not isinstance(signal_types, (list, tuple)):
        raise ValueError("contributing_signal_types must be a list/tuple")


def validate_failure_predicted(p: dict[str, Any]) -> None:
    _check_keys(p, FAILURE_PREDICTED_KEYS, "failure_predicted")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["fault_type"], "fault_type")
    _check_float_in_range(p["probability"], "probability")
    _check_float_in_range(p["confidence"], "confidence")
    level = _check_str(p["level"], "level")
    if level not in ("safe", "warning", "failure"):
        raise ValueError(f"level must be safe/warning/failure, got {level}")


def validate_mitigation_planned(p: dict[str, Any]) -> None:
    _check_keys(p, MITIGATION_PLANNED_KEYS, "mitigation_planned")
    _check_str(p["plan_id"], "plan_id")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["fault_type"], "fault_type")
    _check_str(p["strategy"], "strategy")
    _check_float_in_range(p["urgency"], "urgency")
    _check_float_in_range(p["expected_risk_reduction"], "expected_risk_reduction")


def validate_recovery_executed(p: dict[str, Any]) -> None:
    _check_keys(p, RECOVERY_EXECUTED_KEYS, "recovery_executed")
    _check_str(p["action_id"], "action_id")
    _check_str(p["plan_id"], "plan_id")
    _check_str(p["snapshot_id"], "snapshot_id")
    if not isinstance(p.get("success"), bool):
        raise ValueError("success must be bool")
    _check_str(p["message"], "message")
    if not isinstance(p.get("rollback_possible"), bool):
        raise ValueError("rollback_possible must be bool")


def validate_failure_avoided(p: dict[str, Any]) -> None:
    _check_keys(p, FAILURE_AVOIDED_KEYS, "failure_avoided")
    _check_str(p["fault_id"], "fault_id")
    _check_float_in_range(p["original_probability"], "original_probability")
    _check_str(p["mitigation_strategy"], "mitigation_strategy")
    _check_str(p["snapshot_id"], "snapshot_id")


# ── Payload makers ─────────────────────────────────────────────────


def make_signal_detected_payload(
    *,
    fault_id: str,
    signal_type: str,
    severity: float,
    frequency: int,
    tv: int = PREDICTIVE_FAILURE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_id": fault_id,
        "signal_type": signal_type,
        "severity": severity,
        "frequency": frequency,
        "template_version": tv,
    }
    validate_signal_detected(p)
    return p


def make_risk_computed_payload(
    *,
    fault_id: str,
    fault_type: str,
    risk_score: float,
    contributing_signal_types: list[str],
    tv: int = PREDICTIVE_FAILURE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_id": fault_id,
        "fault_type": fault_type,
        "risk_score": risk_score,
        "contributing_signal_types": contributing_signal_types,
        "template_version": tv,
    }
    validate_risk_computed(p)
    return p


def make_failure_predicted_payload(
    *,
    fault_id: str,
    fault_type: str,
    probability: float,
    confidence: float,
    level: str,
    tv: int = PREDICTIVE_FAILURE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_id": fault_id,
        "fault_type": fault_type,
        "probability": probability,
        "confidence": confidence,
        "level": level,
        "template_version": tv,
    }
    validate_failure_predicted(p)
    return p


def make_mitigation_planned_payload(
    *,
    plan_id: str,
    fault_id: str,
    fault_type: str,
    strategy: str,
    urgency: float,
    expected_risk_reduction: float,
    tv: int = PREDICTIVE_FAILURE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "plan_id": plan_id,
        "fault_id": fault_id,
        "fault_type": fault_type,
        "strategy": strategy,
        "urgency": urgency,
        "expected_risk_reduction": expected_risk_reduction,
        "template_version": tv,
    }
    validate_mitigation_planned(p)
    return p


def make_recovery_executed_payload(
    *,
    action_id: str,
    plan_id: str,
    snapshot_id: str,
    success: bool,
    message: str,
    rollback_possible: bool,
    tv: int = PREDICTIVE_FAILURE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "action_id": action_id,
        "plan_id": plan_id,
        "snapshot_id": snapshot_id,
        "success": success,
        "message": message,
        "rollback_possible": rollback_possible,
        "template_version": tv,
    }
    validate_recovery_executed(p)
    return p


def make_failure_avoided_payload(
    *,
    fault_id: str,
    original_probability: float,
    mitigation_strategy: str,
    snapshot_id: str,
    tv: int = PREDICTIVE_FAILURE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_id": fault_id,
        "original_probability": original_probability,
        "mitigation_strategy": mitigation_strategy,
        "snapshot_id": snapshot_id,
        "template_version": tv,
    }
    validate_failure_avoided(p)
    return p
