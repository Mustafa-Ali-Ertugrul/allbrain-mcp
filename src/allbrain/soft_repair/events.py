from __future__ import annotations

from typing import Any

from allbrain.soft_repair.model import SOFT_REPAIR_TEMPLATE_VERSION

POLICY_BLENDED_KEYS: frozenset[str] = frozenset(
    {
        "old_policy_id",
        "new_policy_id",
        "fault_type",
        "old_weight",
        "new_weight",
        "stability_score",
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


def validate_policy_blended(p: dict[str, Any]) -> None:
    _check_keys(p, POLICY_BLENDED_KEYS, "policy_blended")
    _check_str(p["old_policy_id"], "old_policy_id")
    _check_str(p["new_policy_id"], "new_policy_id")
    _check_str(p["fault_type"], "fault_type")
    _check_float_in_range(p["old_weight"], "old_weight")
    _check_float_in_range(p["new_weight"], "new_weight")
    _check_float_in_range(p["stability_score"], "stability_score")


def make_policy_blended_payload(
    *,
    old_policy_id: str,
    new_policy_id: str,
    fault_type: str,
    old_weight: float,
    new_weight: float,
    stability_score: float,
    tv: int = SOFT_REPAIR_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "old_policy_id": old_policy_id,
        "new_policy_id": new_policy_id,
        "fault_type": fault_type,
        "old_weight": old_weight,
        "new_weight": new_weight,
        "stability_score": stability_score,
        "template_version": tv,
    }
    validate_policy_blended(p)
    return p
