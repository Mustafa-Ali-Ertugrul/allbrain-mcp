from __future__ import annotations

from typing import Any

from allbrain.tradeoff_engine.model import TRADEOFF_ENGINE_TEMPLATE_VERSION

TRADEOFF_ANALYZED_KEYS: frozenset[str] = frozenset({"fault_type", "frontier_size", "dominated_count"})
UTILITY_COMPUTED_KEYS: frozenset[str] = frozenset({"policy_id", "fault_type", "utility", "safety_pass"})


def _check_keys(p, keys, label):
    missing = keys - set(p.keys())
    if missing:
        raise ValueError(f"{label} missing: {missing}")


def _check_str(v, label):
    if not isinstance(v, str):
        raise ValueError(f"{label} must be str")
    return v


def _check_float(v, label, lo=0.0, hi=1.0):
    if not isinstance(v, (int, float)):
        raise ValueError(f"{label} must be numeric")
    f = float(v)
    if f == float("-inf"):
        return f  # allow -inf for safety-fail utility
    if not (lo <= f <= hi):
        raise ValueError(f"{label} in [{lo},{hi}], got {f}")
    return f


def validate_tradeoff_analyzed(p: dict[str, Any]) -> None:
    _check_keys(p, TRADEOFF_ANALYZED_KEYS, "tradeoff_analyzed")
    _check_str(p["fault_type"], "fault_type")


def validate_utility_computed(p: dict[str, Any]) -> None:
    _check_keys(p, UTILITY_COMPUTED_KEYS, "utility_computed")
    _check_str(p["policy_id"], "policy_id")
    safety_pass = p["safety_pass"]
    if safety_pass:
        _check_float(p["utility"], "utility", -2.0, 2.0)
    else:
        _check_float(p["utility"], "utility", float("-inf"), 2.0)


def make_tradeoff_analyzed_payload(
    *,
    fault_type: str,
    frontier_size: int,
    dominated_count: int,
    tv: int = TRADEOFF_ENGINE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p = {
        "fault_type": fault_type,
        "frontier_size": frontier_size,
        "dominated_count": dominated_count,
        "template_version": tv,
    }
    validate_tradeoff_analyzed(p)
    return p


def make_utility_computed_payload(
    *,
    policy_id: str,
    fault_type: str,
    utility: float,
    safety_pass: bool,
    tv: int = TRADEOFF_ENGINE_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p = {
        "policy_id": policy_id,
        "fault_type": fault_type,
        "utility": round(utility, 4),
        "safety_pass": safety_pass,
        "template_version": tv,
    }
    validate_utility_computed(p)
    return p
