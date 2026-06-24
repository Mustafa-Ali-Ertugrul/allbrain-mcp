from __future__ import annotations

from typing import Any

from allbrain.meta_meta_scoring.model import META_META_SCORING_TEMPLATE_VERSION

EVALUATOR_PROFILE_UPDATED_KEYS: frozenset[str] = frozenset({
    "evaluator_id", "fault_type", "accuracy", "bias",
    "stability", "drift_sensitivity", "version",
})


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


def validate_evaluator_profile_updated(p: dict[str, Any]) -> None:
    _check_keys(p, EVALUATOR_PROFILE_UPDATED_KEYS, "evaluator_profile_updated")
    _check_str(p["evaluator_id"], "evaluator_id")
    _check_str(p["fault_type"], "fault_type")
    _check_float_in_range(p["accuracy"], "accuracy", -1.0, 1.0)
    _check_float_in_range(p["bias"], "bias", -1.0, 1.0)
    _check_float_in_range(p["stability"], "stability")
    _check_float_in_range(p["drift_sensitivity"], "drift_sensitivity")
    _check_int_ge(p["version"], "version", 1)


def make_evaluator_profile_updated_payload(
    *,
    evaluator_id: str,
    fault_type: str,
    accuracy: float,
    bias: float,
    stability: float,
    drift_sensitivity: float,
    version: int,
    tv: int = META_META_SCORING_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "evaluator_id": evaluator_id,
        "fault_type": fault_type,
        "accuracy": round(accuracy, 4),
        "bias": round(bias, 4),
        "stability": round(stability, 4),
        "drift_sensitivity": round(drift_sensitivity, 4),
        "version": version,
        "template_version": tv,
    }
    validate_evaluator_profile_updated(p)
    return p