from __future__ import annotations

from typing import Any

from allbrain.domains.reasoning.objective_system.model import OBJECTIVE_SYSTEM_TEMPLATE_VERSION

OBJECTIVE_UPDATED_KEYS: frozenset[str] = frozenset(
    {
        "fault_type",
        "safety",
        "stability",
        "success",
        "efficiency",
        "safety_pass",
    }
)
OBJECTIVE_REBALANCED_KEYS: frozenset[str] = frozenset(
    {
        "fault_type",
        "safety",
        "stability",
        "success",
        "efficiency",
        "version",
    }
)


def _check_keys(p: dict[str, Any], keys: frozenset[str], label: str) -> None:
    missing = keys - set(p.keys())
    if missing:
        raise ValueError(f"{label} missing: {missing}")


def _check_str(v: Any, label: str) -> str:
    if not isinstance(v, str):
        raise ValueError(f"{label} must be str, got {type(v).__name__}")
    return v


def _check_float_in_range(v: Any, label: str, lo: float = 0.0, hi: float = 1.0) -> float:
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


def validate_objective_updated(p: dict[str, Any]) -> None:
    _check_keys(p, OBJECTIVE_UPDATED_KEYS, "objective_updated")
    _check_str(p["fault_type"], "fault_type")
    _check_float_in_range(p["safety"], "safety")
    _check_float_in_range(p["stability"], "stability")
    _check_float_in_range(p["success"], "success")
    _check_float_in_range(p["efficiency"], "efficiency")


def validate_objective_rebalanced(p: dict[str, Any]) -> None:
    _check_keys(p, OBJECTIVE_REBALANCED_KEYS, "objective_rebalanced")
    _check_str(p["fault_type"], "fault_type")
    _check_float_in_range(p["safety"], "safety")
    _check_int_ge(p["version"], "version", 1)


def make_objective_updated_payload(
    *,
    fault_type: str,
    safety: float,
    stability: float,
    success: float,
    efficiency: float,
    safety_pass: bool,
    tv: int = OBJECTIVE_SYSTEM_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p = {
        "fault_type": fault_type,
        "safety": round(safety, 4),
        "stability": round(stability, 4),
        "success": round(success, 4),
        "efficiency": round(efficiency, 4),
        "safety_pass": safety_pass,
        "template_version": tv,
    }
    validate_objective_updated(p)
    return p


def make_objective_rebalanced_payload(
    *,
    fault_type: str,
    safety: float,
    stability: float,
    success: float,
    efficiency: float,
    version: int,
    tv: int = OBJECTIVE_SYSTEM_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p = {
        "fault_type": fault_type,
        "safety": round(safety, 4),
        "stability": round(stability, 4),
        "success": round(success, 4),
        "efficiency": round(efficiency, 4),
        "version": version,
        "template_version": tv,
    }
    validate_objective_rebalanced(p)
    return p
