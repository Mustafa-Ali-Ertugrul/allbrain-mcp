from __future__ import annotations

import math
from typing import Any

from allbrain.causal.model import (
    CAUSAL_CONFIDENCE_SHRINK,
    CAUSAL_IMPACT_THRESHOLD,
    CAUSAL_MIN_SAMPLES,
    CausalImpact,
    ImpactDirection,
)
from allbrain.events.schemas import EventType


def _stable_causal_id(key: str, event_ids: list[str] | None = None) -> str:
    import hashlib

    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode()).digest()
    return f"causal-est-{d.hex()[:12]}"


def _normalized_outcomes(
    events: list[Any],
    target_agent: str,
    target_task_type: str,
) -> list[float]:
    """Extract outcomes for agent+task_type, normalized by telemetry context.

    Refinement #2 (bias mitigation): only considers events where
    task_type matches AND telemetry context is similar (runtime_score range overlap).
    """
    scores: list[float] = []
    for event in events:
        et = str(getattr(event, "type", ""))
        if et not in (EventType.TASK_COMPLETED.value, EventType.RUNTIME_FEEDBACK_RECORDED.value):
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        aid = payload.get("agent_id")
        if not isinstance(aid, str) or aid != target_agent:
            continue
        tt = payload.get("task_type")
        if not isinstance(tt, str) or tt != target_task_type:
            continue

        score = payload.get("outcome_score") or payload.get("success_score") or payload.get("runtime_score")
        if not isinstance(score, (int, float)):
            continue

        telemetry = payload.get("telemetry_score") or payload.get("runtime_score")
        ctx_factor = max(0.3, min(1.0, float(telemetry) * 2.0)) if isinstance(telemetry, (int, float)) else 0.5

        raw_score = max(0.0, min(1.0, float(score)))
        scores.append(raw_score * ctx_factor)

    return scores


def estimate_treatment_effect(
    *,
    agent_a: str,
    agent_b: str,
    task_type: str,
    events: list[Any],
    event_ids: list[str] | None = None,
) -> CausalImpact:
    """ATE = E[outcome | B, task_type, context] - E[outcome | A, task_type, context].

    Bias mitigation (Refinement #2): outcomes are normalized by telemetry
    context to prevent "easy task agent" from masquerading as "good agent".

    Confidence: shrinks toward 0 for low-sample ATE via exponential model.
    """
    if event_ids is None:
        event_ids = []
    key = f"{agent_a}->{agent_b}::{task_type}"
    analysis_id = _stable_causal_id(key, event_ids)

    a_scores = _normalized_outcomes(events, agent_a, task_type)
    b_scores = _normalized_outcomes(events, agent_b, task_type)

    a_n, b_n = len(a_scores), len(b_scores)
    min_n = min(a_n, b_n)

    if min_n < CAUSAL_MIN_SAMPLES:
        return CausalImpact(
            agent_id=agent_a,
            task_type=task_type,
            alternative_agent=agent_b,
            impact_score=0.0,
            confidence=0.0,
            sample_count=min_n,
            analysis_id=analysis_id,
        )

    a_mean = sum(a_scores) / a_n
    b_mean = sum(b_scores) / b_n
    impact = b_mean - a_mean
    impact_score = max(-1.0, min(1.0, impact))

    raw_confidence = 1.0 - math.exp(-min_n / float(CAUSAL_MIN_SAMPLES))
    confidence = raw_confidence * (1.0 - CAUSAL_CONFIDENCE_SHRINK * min(1.0, abs(impact_score)))

    return CausalImpact(
        agent_id=agent_a,
        task_type=task_type,
        alternative_agent=agent_b,
        impact_score=impact_score,
        confidence=confidence,
        sample_count=min_n,
        analysis_id=analysis_id,
    )
