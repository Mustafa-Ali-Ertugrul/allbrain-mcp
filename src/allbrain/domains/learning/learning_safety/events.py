from __future__ import annotations

from typing import Any

from allbrain.domains.learning.learning_safety.model import LEARNING_SAFETY_TEMPLATE_VERSION

EXPLORATION_KEYS: frozenset[str] = frozenset(
    {
        "fault_type",
        "signal_type",
        "epsilon",
        "selected_strategy",
        "was_exploration",
    }
)
SIMULATION_WEIGHT_CAPPED_KEYS: frozenset[str] = frozenset(
    {
        "fault_type",
        "simulation_weight",
        "real_weight",
        "is_real_provider_set",
    }
)
DRIFT_DETECTED_KEYS: frozenset[str] = frozenset(
    {
        "fault_type",
        "signal_type",
        "metric_value",
        "threshold",
        "details",
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


def _check_float_in_range(
    v: Any,
    label: str,
    lo: float = 0.0,
    hi: float = 1.0,
) -> float:
    if not isinstance(v, (int, float)):
        raise ValueError(f"{label} must be numeric, got {type(v).__name__}")
    f = float(v)
    if not (lo <= f <= hi):
        raise ValueError(f"{label} must be in [{lo}, {hi}], got {f}")
    return f


def _check_bool(v: Any, label: str) -> bool:
    if not isinstance(v, bool):
        raise ValueError(f"{label} must be bool, got {type(v).__name__}")
    return v


def validate_exploration_triggered(p: dict[str, Any]) -> None:
    _check_keys(p, EXPLORATION_KEYS, "exploration_triggered")
    _check_str(p["fault_type"], "fault_type")
    _check_str(p["signal_type"], "signal_type")
    _check_float_in_range(p["epsilon"], "epsilon")
    _check_str(p["selected_strategy"], "selected_strategy")
    _check_bool(p["was_exploration"], "was_exploration")


def validate_simulation_weight_capped(p: dict[str, Any]) -> None:
    _check_keys(p, SIMULATION_WEIGHT_CAPPED_KEYS, "simulation_weight_capped")
    _check_str(p["fault_type"], "fault_type")
    _check_float_in_range(p["simulation_weight"], "simulation_weight")
    _check_float_in_range(p["real_weight"], "real_weight")
    _check_bool(p["is_real_provider_set"], "is_real_provider_set")


def validate_learning_drift_detected(p: dict[str, Any]) -> None:
    _check_keys(p, DRIFT_DETECTED_KEYS, "learning_drift_detected")
    _check_str(p["fault_type"], "fault_type")
    _check_str(p["signal_type"], "signal_type")
    _check_float_in_range(p["metric_value"], "metric_value", -1.0, 1.0)
    _check_float_in_range(p["threshold"], "threshold")
    if not isinstance(p.get("details"), dict):
        raise ValueError("details must be dict")


def make_exploration_triggered_payload(
    *,
    fault_type: str,
    signal_type: str,
    epsilon: float,
    selected_strategy: str,
    was_exploration: bool,
    tv: int = LEARNING_SAFETY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "signal_type": signal_type,
        "epsilon": epsilon,
        "selected_strategy": selected_strategy,
        "was_exploration": was_exploration,
        "template_version": tv,
    }
    validate_exploration_triggered(p)
    return p


def make_simulation_weight_capped_payload(
    *,
    fault_type: str,
    simulation_weight: float,
    real_weight: float,
    is_real_provider_set: bool,
    tv: int = LEARNING_SAFETY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "simulation_weight": simulation_weight,
        "real_weight": real_weight,
        "is_real_provider_set": is_real_provider_set,
        "template_version": tv,
    }
    validate_simulation_weight_capped(p)
    return p


def make_learning_drift_detected_payload(
    *,
    fault_type: str,
    signal_type: str,
    metric_value: float,
    threshold: float,
    details: dict[str, Any],
    tv: int = LEARNING_SAFETY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "signal_type": signal_type,
        "metric_value": metric_value,
        "threshold": threshold,
        "details": details,
        "template_version": tv,
    }
    validate_learning_drift_detected(p)
    return p
