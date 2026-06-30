from __future__ import annotations

from typing import Any

from allbrain.policy_routing.model import POLICY_ROUTING_TEMPLATE_VERSION

FAMILY_SELECTED_KEYS: frozenset[str] = frozenset(
    {
        "family",
        "strategies",
        "fault_type",
        "signal_type",
        "confidence",
    }
)
CANDIDATE_EVALUATED_KEYS: frozenset[str] = frozenset(
    {
        "candidate_id",
        "fault_type",
        "strategy",
        "score",
        "success_rate",
        "risk_penalty",
        "stability_bonus",
        "drift_penalty",
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


def validate_policy_family_selected(p: dict[str, Any]) -> None:
    _check_keys(p, FAMILY_SELECTED_KEYS, "policy_family_selected")
    _check_str(p["family"], "family")
    strategies = p.get("strategies")
    if not isinstance(strategies, (list, tuple)):
        raise ValueError("strategies must be list/tuple")
    _check_str(p["fault_type"], "fault_type")
    _check_str(p["signal_type"], "signal_type")
    _check_float_in_range(p["confidence"], "confidence")


def validate_family_candidate_evaluated(p: dict[str, Any]) -> None:
    _check_keys(p, CANDIDATE_EVALUATED_KEYS, "family_candidate_evaluated")
    _check_str(p["candidate_id"], "candidate_id")
    _check_str(p["fault_type"], "fault_type")
    _check_str(p["strategy"], "strategy")
    _check_float_in_range(p["score"], "score", -2.0, 2.0)
    _check_float_in_range(p["success_rate"], "success_rate")
    _check_float_in_range(p["risk_penalty"], "risk_penalty", 0.0, 2.0)
    _check_float_in_range(p["stability_bonus"], "stability_bonus", -1.0, 1.0)
    _check_float_in_range(p["drift_penalty"], "drift_penalty", 0.0, 2.0)


def make_policy_family_selected_payload(
    *,
    family: str,
    strategies: list[str],
    fault_type: str,
    signal_type: str,
    confidence: float,
    tv: int = POLICY_ROUTING_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "family": family,
        "strategies": strategies,
        "fault_type": fault_type,
        "signal_type": signal_type,
        "confidence": confidence,
        "template_version": tv,
    }
    validate_policy_family_selected(p)
    return p


def make_family_candidate_evaluated_payload(
    *,
    candidate_id: str,
    fault_type: str,
    strategy: str,
    score: float,
    success_rate: float,
    risk_penalty: float,
    stability_bonus: float,
    drift_penalty: float,
    tv: int = POLICY_ROUTING_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "candidate_id": candidate_id,
        "fault_type": fault_type,
        "strategy": strategy,
        "score": score,
        "success_rate": success_rate,
        "risk_penalty": risk_penalty,
        "stability_bonus": stability_bonus,
        "drift_penalty": drift_penalty,
        "template_version": tv,
    }
    validate_family_candidate_evaluated(p)
    return p
