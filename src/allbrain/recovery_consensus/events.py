from __future__ import annotations

from typing import Any
from allbrain.recovery_consensus.model import (
    CONSENSUS_TEMPLATE_VERSION,
    VALID_RECOVERY_STRATEGIES,
)

STRATEGIES_GENERATED_KEYS: frozenset[str] = frozenset(
    {"fault_id", "candidate_count", "strategies"}
)
STRATEGY_EVALUATED_KEYS: frozenset[str] = frozenset(
    {"fault_id", "strategy", "score", "risk", "estimated_success", "confidence"}
)
CONSENSUS_REACHED_KEYS: frozenset[str] = frozenset(
    {"decision_id", "fault_id", "selected_strategy", "consensus_score", "candidate_count"}
)
STRATEGY_REJECTED_KEYS: frozenset[str] = frozenset(
    {"decision_id", "fault_id", "strategy", "score", "reason"}
)
STRATEGY_SELECTED_KEYS: frozenset[str] = frozenset(
    {"decision_id", "fault_id", "selected_strategy", "consensus_score", "reason"}
)

VALID_SCORE_RANGE = (0.0, 1.0)


def _clamp_score(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def validate_strategies_generated(p: dict[str, Any]) -> None:
    m = STRATEGIES_GENERATED_KEYS - set(p.keys())
    if m:
        raise ValueError("strategies_generated missing: " + str(m))
    if not isinstance(p.get("fault_id"), str):
        raise ValueError("fault_id must be str")
    count = p.get("candidate_count")
    if not isinstance(count, int) or count < 1:
        raise ValueError("candidate_count must be int >= 1")
    strategies = p.get("strategies")
    if not isinstance(strategies, (list, tuple)):
        raise ValueError("strategies must be a list")


def validate_strategy_evaluated(p: dict[str, Any]) -> None:
    m = STRATEGY_EVALUATED_KEYS - set(p.keys())
    if m:
        raise ValueError("strategy_evaluated missing: " + str(m))
    if not isinstance(p.get("fault_id"), str):
        raise ValueError("fault_id must be str")
    strategy = p.get("strategy")
    if strategy not in VALID_RECOVERY_STRATEGIES:
        raise ValueError("strategy must be one of " + str(VALID_RECOVERY_STRATEGIES))
    for key in ("score", "risk", "estimated_success", "confidence"):
        val = p.get(key)
        if not isinstance(val, (int, float)):
            raise ValueError(f"{key} must be numeric")
        if not (0.0 <= float(val) <= 1.0):
            raise ValueError(f"{key} must be in [0, 1]")


def validate_consensus_reached(p: dict[str, Any]) -> None:
    m = CONSENSUS_REACHED_KEYS - set(p.keys())
    if m:
        raise ValueError("consensus_reached missing: " + str(m))
    if not isinstance(p.get("decision_id"), str):
        raise ValueError("decision_id must be str")
    if not isinstance(p.get("fault_id"), str):
        raise ValueError("fault_id must be str")
    strategy = p.get("selected_strategy")
    if strategy not in VALID_RECOVERY_STRATEGIES:
        raise ValueError("selected_strategy must be one of " + str(VALID_RECOVERY_STRATEGIES))
    score = p.get("consensus_score")
    if not isinstance(score, (int, float)):
        raise ValueError("consensus_score must be numeric")
    if not (0.0 <= float(score) <= 1.0):
        raise ValueError("consensus_score must be in [0, 1]")


def validate_strategy_rejected(p: dict[str, Any]) -> None:
    m = STRATEGY_REJECTED_KEYS - set(p.keys())
    if m:
        raise ValueError("strategy_rejected missing: " + str(m))
    if not isinstance(p.get("decision_id"), str):
        raise ValueError("decision_id must be str")
    if not isinstance(p.get("fault_id"), str):
        raise ValueError("fault_id must be str")
    strategy = p.get("strategy")
    if strategy not in VALID_RECOVERY_STRATEGIES:
        raise ValueError("strategy must be one of " + str(VALID_RECOVERY_STRATEGIES))
    if not isinstance(p.get("reason"), str):
        raise ValueError("reason must be str")


def validate_strategy_selected(p: dict[str, Any]) -> None:
    m = STRATEGY_SELECTED_KEYS - set(p.keys())
    if m:
        raise ValueError("strategy_selected missing: " + str(m))
    if not isinstance(p.get("decision_id"), str):
        raise ValueError("decision_id must be str")
    if not isinstance(p.get("fault_id"), str):
        raise ValueError("fault_id must be str")
    strategy = p.get("selected_strategy")
    if strategy not in VALID_RECOVERY_STRATEGIES:
        raise ValueError("selected_strategy must be one of " + str(VALID_RECOVERY_STRATEGIES))
    if not isinstance(p.get("reason"), str):
        raise ValueError("reason must be str")


def make_strategies_generated_payload(
    *,
    fault_id: str,
    candidate_count: int,
    strategies: list[str],
    tv: int = CONSENSUS_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_id": fault_id,
        "candidate_count": candidate_count,
        "strategies": list(strategies),
        "template_version": tv,
    }
    validate_strategies_generated(p)
    return p


def make_strategy_evaluated_payload(
    *,
    fault_id: str,
    strategy: str,
    score: float,
    risk: float,
    estimated_success: float,
    confidence: float,
    tv: int = CONSENSUS_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_id": fault_id,
        "strategy": strategy,
        "score": _clamp_score(score),
        "risk": _clamp_score(risk),
        "estimated_success": _clamp_score(estimated_success),
        "confidence": _clamp_score(confidence),
        "template_version": tv,
    }
    validate_strategy_evaluated(p)
    return p


def make_consensus_reached_payload(
    *,
    decision_id: str,
    fault_id: str,
    selected_strategy: str,
    consensus_score: float,
    candidate_count: int,
    tv: int = CONSENSUS_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "decision_id": decision_id,
        "fault_id": fault_id,
        "selected_strategy": selected_strategy,
        "consensus_score": _clamp_score(consensus_score),
        "candidate_count": candidate_count,
        "template_version": tv,
    }
    validate_consensus_reached(p)
    return p


def make_strategy_rejected_payload(
    *,
    decision_id: str,
    fault_id: str,
    strategy: str,
    score: float,
    reason: str,
    tv: int = CONSENSUS_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "decision_id": decision_id,
        "fault_id": fault_id,
        "strategy": strategy,
        "score": _clamp_score(score),
        "reason": reason,
        "template_version": tv,
    }
    validate_strategy_rejected(p)
    return p


def make_strategy_selected_payload(
    *,
    decision_id: str,
    fault_id: str,
    selected_strategy: str,
    consensus_score: float,
    reason: str,
    tv: int = CONSENSUS_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "decision_id": decision_id,
        "fault_id": fault_id,
        "selected_strategy": selected_strategy,
        "consensus_score": _clamp_score(consensus_score),
        "reason": reason,
        "template_version": tv,
    }
    validate_strategy_selected(p)
    return p
