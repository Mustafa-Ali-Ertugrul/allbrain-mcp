from __future__ import annotations

from allbrain.causal.model import CAUSAL_TEMPLATE_VERSION

COUNTERFACTUAL_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_type", "actual_agent", "alternative_agent",
     "actual_outcome", "alternative_outcome", "impact_score", "confidence", "sample_count"}
)

IMPACT_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_type", "alternative_agent", "impact_score", "confidence", "sample_count"}
)


def validate_counterfactual(p: dict) -> None:
    m = COUNTERFACTUAL_KEYS - set(p.keys())
    if m:
        raise ValueError("counterfactual payload missing: " + str(m))
    for f in ("agent_id", "task_type", "actual_agent", "alternative_agent"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    for f in ("actual_outcome", "alternative_outcome", "impact_score", "confidence"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")
    if not isinstance(p.get("sample_count"), int):
        raise ValueError("sample_count must be int")


def validate_impact(p: dict) -> None:
    m = IMPACT_KEYS - set(p.keys())
    if m:
        raise ValueError("impact payload missing: " + str(m))
    for f in ("agent_id", "task_type", "alternative_agent"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    for f in ("impact_score", "confidence"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")
    if not isinstance(p.get("sample_count"), int):
        raise ValueError("sample_count must be int")


def make_counterfactual_payload(
    *,
    agent_id: str,
    task_type: str,
    actual_agent: str,
    alternative_agent: str,
    actual_outcome: float,
    alternative_outcome: float,
    impact_score: float,
    confidence: float,
    sample_count: int,
    tv: int = CAUSAL_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_type": str(task_type),
        "actual_agent": str(actual_agent),
        "alternative_agent": str(alternative_agent),
        "actual_outcome": float(actual_outcome),
        "alternative_outcome": float(alternative_outcome),
        "impact_score": float(impact_score),
        "confidence": float(confidence),
        "sample_count": int(sample_count),
        "template_version": int(tv),
    }
    validate_counterfactual(p)
    return p


def make_impact_payload(
    *,
    agent_id: str,
    task_type: str,
    alternative_agent: str,
    impact_score: float,
    confidence: float,
    sample_count: int,
    tv: int = CAUSAL_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_type": str(task_type),
        "alternative_agent": str(alternative_agent),
        "impact_score": float(impact_score),
        "confidence": float(confidence),
        "sample_count": int(sample_count),
        "template_version": int(tv),
    }
    validate_impact(p)
    return p
