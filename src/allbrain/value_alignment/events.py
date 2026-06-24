from __future__ import annotations

from typing import Any
from allbrain.value_alignment.model import VALUE_ALIGNMENT_TEMPLATE_VERSION

ALIGNMENT_FAILED_KEYS: frozenset[str] = frozenset({"fault_type", "overall_score", "hard_violations", "soft_penalties"})


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
    if not (lo <= float(v) <= hi):
        raise ValueError(f"{label} in [{lo},{hi}], got {v}")
    return float(v)


def validate_alignment_failed(p: dict[str, Any]) -> None:
    _check_keys(p, ALIGNMENT_FAILED_KEYS, "alignment_failed")
    _check_str(p["fault_type"], "fault_type")
    _check_float(p["overall_score"], "overall_score")


def make_alignment_failed_payload(*, fault_type: str, overall_score: float,
    hard_violations: list[str], soft_penalties: list[str],
    tv: int = VALUE_ALIGNMENT_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p = {"fault_type": fault_type, "overall_score": round(overall_score, 4),
         "hard_violations": list(hard_violations), "soft_penalties": list(soft_penalties),
         "template_version": tv}
    validate_alignment_failed(p)
    return p