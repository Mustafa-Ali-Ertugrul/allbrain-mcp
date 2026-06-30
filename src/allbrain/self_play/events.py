from __future__ import annotations

from typing import Any

from allbrain.self_play.model import SELF_PLAY_TEMPLATE_VERSION

MATCH_PLAYED_KEYS: frozenset[str] = frozenset({
    "policy_a", "policy_b", "winner", "score_a", "score_b",
    "confidence", "fault_type",
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


def validate_match_played(p: dict[str, Any]) -> None:
    _check_keys(p, MATCH_PLAYED_KEYS, "match_played")
    _check_str(p["policy_a"], "policy_a")
    _check_str(p["policy_b"], "policy_b")
    _check_str(p["winner"], "winner")
    _check_float_in_range(p["score_a"], "score_a", 0.0, 1.0)
    _check_float_in_range(p["score_b"], "score_b", 0.0, 1.0)
    _check_float_in_range(p["confidence"], "confidence")
    _check_str(p["fault_type"], "fault_type")


def make_match_played_payload(
    *,
    policy_a: str,
    policy_b: str,
    winner: str,
    score_a: float,
    score_b: float,
    confidence: float,
    fault_type: str,
    tv: int = SELF_PLAY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "policy_a": policy_a,
        "policy_b": policy_b,
        "winner": winner,
        "score_a": score_a,
        "score_b": score_b,
        "confidence": confidence,
        "fault_type": fault_type,
        "template_version": tv,
    }
    validate_match_played(p)
    return p
