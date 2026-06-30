from __future__ import annotations

from typing import Any

from allbrain.self_repair.model import SELF_REPAIR_TEMPLATE_VERSION

SNAPSHOTTED_KEYS: frozenset[str] = frozenset({
    "snapshot_id", "fault_type", "policy_version", "stability_score",
})
VALIDATION_FAILED_KEYS: frozenset[str] = frozenset({
    "fault_type", "policy_version", "stability_score", "failure_reasons",
})
ROLLBACK_TRIGGERED_KEYS: frozenset[str] = frozenset({
    "rollback_id", "fault_type", "from_version", "to_version",
    "strategy", "triggered_by",
})
ROLLBACK_COMPLETED_KEYS: frozenset[str] = frozenset({
    "rollback_id", "fault_type", "from_version", "to_version", "success",
})
RECOVERED_KEYS: frozenset[str] = frozenset({
    "recovery_id", "rollback_id", "fault_type", "stabilized",
    "post_recovery_stability", "cycles_to_stable",
})


def _check_keys(p: dict[str, Any], keys: frozenset[str], label: str) -> None:
    missing = keys - set(p.keys())
    if missing:
        raise ValueError(f"{label} missing: {missing}")


def _check_str(v: Any, label: str) -> str:
    if not isinstance(v, str):
        raise ValueError(f"{label} must be str, got {type(v).__name__}")
    return v


def _check_float(v: Any, label: str, lo: float = 0.0, hi: float = 1.0) -> float:
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


def validate_policy_snapshotted(p: dict[str, Any]) -> None:
    _check_keys(p, SNAPSHOTTED_KEYS, "policy_snapshotted")
    _check_str(p["snapshot_id"], "snapshot_id")
    _check_str(p["fault_type"], "fault_type")
    _check_int_ge(p["policy_version"], "policy_version", 1)
    _check_float(p["stability_score"], "stability_score")


def validate_policy_validation_failed(p: dict[str, Any]) -> None:
    _check_keys(p, VALIDATION_FAILED_KEYS, "validation_failed")
    _check_str(p["fault_type"], "fault_type")
    _check_int_ge(p["policy_version"], "policy_version", 1)
    _check_float(p["stability_score"], "stability_score")
    reasons = p.get("failure_reasons")
    if not isinstance(reasons, (list, tuple)):
        raise ValueError("failure_reasons must be list/tuple")


def validate_rollback_triggered(p: dict[str, Any]) -> None:
    _check_keys(p, ROLLBACK_TRIGGERED_KEYS, "rollback_triggered")
    _check_str(p["rollback_id"], "rollback_id")
    _check_str(p["fault_type"], "fault_type")
    _check_int_ge(p["from_version"], "from_version", 1)
    _check_int_ge(p["to_version"], "to_version", 1)
    _check_str(p["strategy"], "strategy")
    _check_str(p["triggered_by"], "triggered_by")


def validate_rollback_completed(p: dict[str, Any]) -> None:
    _check_keys(p, ROLLBACK_COMPLETED_KEYS, "rollback_completed")
    _check_str(p["rollback_id"], "rollback_id")
    _check_str(p["fault_type"], "fault_type")
    _check_int_ge(p["from_version"], "from_version", 1)
    _check_int_ge(p["to_version"], "to_version", 1)
    if not isinstance(p.get("success"), bool):
        raise ValueError("success must be bool")


def validate_system_recovered(p: dict[str, Any]) -> None:
    _check_keys(p, RECOVERED_KEYS, "system_recovered")
    _check_str(p["recovery_id"], "recovery_id")
    _check_str(p["rollback_id"], "rollback_id")
    _check_str(p["fault_type"], "fault_type")
    if not isinstance(p.get("stabilized"), bool):
        raise ValueError("stabilized must be bool")
    _check_float(p["post_recovery_stability"], "post_recovery_stability")
    _check_int_ge(p["cycles_to_stable"], "cycles_to_stable", 0)


def make_policy_snapshotted_payload(
    *, snapshot_id: str, fault_type: str, policy_version: int,
    stability_score: float,
    tv: int = SELF_REPAIR_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "snapshot_id": snapshot_id, "fault_type": fault_type,
        "policy_version": policy_version, "stability_score": stability_score,
        "template_version": tv,
    }
    validate_policy_snapshotted(p)
    return p


def make_validation_failed_payload(
    *, fault_type: str, policy_version: int, stability_score: float,
    failure_reasons: list[str],
    tv: int = SELF_REPAIR_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type, "policy_version": policy_version,
        "stability_score": stability_score,
        "failure_reasons": failure_reasons, "template_version": tv,
    }
    validate_policy_validation_failed(p)
    return p


def make_rollback_triggered_payload(
    *, rollback_id: str, fault_type: str, from_version: int, to_version: int,
    strategy: str, triggered_by: str,
    tv: int = SELF_REPAIR_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "rollback_id": rollback_id, "fault_type": fault_type,
        "from_version": from_version, "to_version": to_version,
        "strategy": strategy, "triggered_by": triggered_by,
        "template_version": tv,
    }
    validate_rollback_triggered(p)
    return p


def make_rollback_completed_payload(
    *, rollback_id: str, fault_type: str, from_version: int, to_version: int,
    success: bool,
    tv: int = SELF_REPAIR_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "rollback_id": rollback_id, "fault_type": fault_type,
        "from_version": from_version, "to_version": to_version,
        "success": success, "template_version": tv,
    }
    validate_rollback_completed(p)
    return p


def make_system_recovered_payload(
    *, recovery_id: str, rollback_id: str, fault_type: str,
    stabilized: bool, post_recovery_stability: float, cycles_to_stable: int,
    tv: int = SELF_REPAIR_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "recovery_id": recovery_id, "rollback_id": rollback_id,
        "fault_type": fault_type, "stabilized": stabilized,
        "post_recovery_stability": post_recovery_stability,
        "cycles_to_stable": cycles_to_stable, "template_version": tv,
    }
    validate_system_recovered(p)
    return p
