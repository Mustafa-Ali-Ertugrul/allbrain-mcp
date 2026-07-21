from __future__ import annotations

from typing import Any

from allbrain.domains.governance.policy_competition.model import POLICY_COMPETITION_TEMPLATE_VERSION

COMPETITION_HELD_KEYS: frozenset[str] = frozenset(
    {
        "fault_type",
        "winner_policy_id",
        "winner_strategy",
        "winner_score",
        "confidence",
        "candidate_count",
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


def validate_competition_held(p: dict[str, Any]) -> None:
    _check_keys(p, COMPETITION_HELD_KEYS, "competition_held")
    _check_str(p["fault_type"], "fault_type")
    _check_str(p["winner_policy_id"], "winner_policy_id")
    _check_str(p["winner_strategy"], "winner_strategy")
    _check_float_in_range(p["winner_score"], "winner_score", -2.0, 2.0)
    _check_float_in_range(p["confidence"], "confidence")
    _check_int_ge(p["candidate_count"], "candidate_count", 1)


def make_competition_held_payload(
    *,
    fault_type: str,
    winner_policy_id: str,
    winner_strategy: str,
    winner_score: float,
    confidence: float,
    candidate_count: int,
    tv: int = POLICY_COMPETITION_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "winner_policy_id": winner_policy_id,
        "winner_strategy": winner_strategy,
        "winner_score": winner_score,
        "confidence": confidence,
        "candidate_count": candidate_count,
        "template_version": tv,
    }
    validate_competition_held(p)
    return p
