from __future__ import annotations

from typing import Any

from allbrain.meta_scoring.model import META_SCORING_TEMPLATE_VERSION

SCORING_PROFILE_UPDATED_KEYS: frozenset[str] = frozenset(
    {
        "fault_type",
        "success_weight",
        "risk_weight",
        "stability_weight",
        "drift_weight",
        "exploration_bonus",
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


def validate_scoring_profile_updated(p: dict[str, Any]) -> None:
    _check_keys(p, SCORING_PROFILE_UPDATED_KEYS, "scoring_profile_updated")
    _check_str(p["fault_type"], "fault_type")
    _check_float_in_range(p["success_weight"], "success_weight", 0.0, 1.0)
    _check_float_in_range(p["risk_weight"], "risk_weight", 0.0, 1.0)
    _check_float_in_range(p["stability_weight"], "stability_weight", 0.0, 1.0)
    _check_float_in_range(p["drift_weight"], "drift_weight", 0.0, 1.0)
    _check_float_in_range(p["exploration_bonus"], "exploration_bonus", 0.0, 1.0)
    _check_int_ge(p["version"], "version", 1)


def make_scoring_profile_updated_payload(
    *,
    fault_type: str,
    success_weight: float,
    risk_weight: float,
    stability_weight: float,
    drift_weight: float,
    exploration_bonus: float,
    version: int,
    tv: int = META_SCORING_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "success_weight": success_weight,
        "risk_weight": risk_weight,
        "stability_weight": stability_weight,
        "drift_weight": drift_weight,
        "exploration_bonus": exploration_bonus,
        "version": version,
        "template_version": tv,
    }
    validate_scoring_profile_updated(p)
    return p
