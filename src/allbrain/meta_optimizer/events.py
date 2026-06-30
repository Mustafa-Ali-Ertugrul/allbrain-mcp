from __future__ import annotations

from typing import Any

from allbrain.meta_optimizer.model import META_OPTIMIZER_TEMPLATE_VERSION

WEIGHTS_ADAPTED_KEYS: frozenset[str] = frozenset({
    "fault_type", "success_weight", "risk_weight",
    "stability_weight", "drift_weight", "version",
})

META_OPTIMIZER_GUARDED_KEYS: frozenset[str] = frozenset({
    "fault_type", "reason", "stability_score",
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


def validate_weights_adapated(p: dict[str, Any]) -> None:
    _check_keys(p, WEIGHTS_ADAPTED_KEYS, "weights_adapated")  # spec typo preserved
    _check_str(p["fault_type"], "fault_type")
    _check_float_in_range(p["success_weight"], "success_weight", 0.0, 1.0)
    _check_float_in_range(p["risk_weight"], "risk_weight", 0.0, 1.0)
    _check_float_in_range(p["stability_weight"], "stability_weight", 0.0, 1.0)
    _check_float_in_range(p["drift_weight"], "drift_weight", 0.0, 1.0)
    _check_int_ge(p["version"], "version", 1)


def validate_meta_optimizer_guarded(p: dict[str, Any]) -> None:
    _check_keys(p, META_OPTIMIZER_GUARDED_KEYS, "meta_optimizer_guarded")
    _check_str(p["fault_type"], "fault_type")
    _check_str(p["reason"], "reason")
    _check_float_in_range(p["stability_score"], "stability_score")


def make_weights_adapated_payload(
    *,
    fault_type: str,
    success_weight: float,
    risk_weight: float,
    stability_weight: float,
    drift_weight: float,
    version: int,
    tv: int = META_OPTIMIZER_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "success_weight": success_weight,
        "risk_weight": risk_weight,
        "stability_weight": stability_weight,
        "drift_weight": drift_weight,
        "version": version,
        "template_version": tv,
    }
    validate_weights_adapated(p)
    return p


def make_meta_optimizer_guarded_payload(
    *,
    fault_type: str,
    reason: str,
    stability_score: float,
    tv: int = META_OPTIMIZER_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "reason": reason,
        "stability_score": stability_score,
        "template_version": tv,
    }
    validate_meta_optimizer_guarded(p)
    return p
