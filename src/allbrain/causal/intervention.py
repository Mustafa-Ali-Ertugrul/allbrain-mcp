from __future__ import annotations

import math
from typing import Any

from allbrain.causal.model import (
    CAUSAL_DIVERSITY_CLUSTERS,
    CAUSAL_IMPACT_THRESHOLD,
    CAUSAL_MIN_SAMPLES,
    COUNTERFACTUAL_TOP_K,
    ImpactDirection,
    CounterfactualResult,
)
from allbrain.events.schemas import EventType


def _stable_causal_id(key: str, event_ids: list[str] | None = None) -> str:
    import hashlib
    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode("utf-8")).digest()
    return f"causal-{d.hex()[:12]}"


def _agent_task_outcomes(events: list[Any]) -> dict[str, list[float]]:
    """Extract (agent_id+task_type) -> outcomes from event stream."""
    outcomes: dict[str, list[float]] = {}
    for event in events:
        et = str(getattr(event, "type", ""))
        if et not in (EventType.TASK_COMPLETED.value, EventType.RUNTIME_FEEDBACK_RECORDED.value):
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        aid = payload.get("agent_id")
        if not isinstance(aid, str) or not aid:
            continue
        tt = payload.get("task_type")
        if not isinstance(tt, str) or not tt:
            tt = "default"
        score = payload.get("outcome_score") or payload.get("success_score") or payload.get("runtime_score")
        if isinstance(score, (int, float)):
            key = f"{aid}::{tt}"
            outcomes.setdefault(key, []).append(max(0.0, min(1.0, float(score))))
    return outcomes


def _capability_cluster(agent_id: str, events: list[Any]) -> str:
    """Simple cluster: hash of agent_id prefix + registered capabilities."""
    capabilities: set[str] = set()
    for event in events:
        et = str(getattr(event, "type", ""))
        if et != EventType.AGENT_CAPABILITY_REGISTERED.value:
            continue
        payload = getattr(event, "payload", None)
        if isinstance(payload, dict) and payload.get("agent_id") == agent_id:
            cap = payload.get("capability")
            if isinstance(cap, str) and cap:
                capabilities.add(cap)
    if not capabilities:
        import hashlib
        return f"cluster-{hashlib.sha256(agent_id.encode()).hexdigest()[:4]}"
    import hashlib
    key = "|".join(sorted(capabilities))
    return f"cluster-{hashlib.sha256(key.encode()).hexdigest()[:6]}"


def _diverse_top_k(
    actual_agent: str,
    agent_keys: set[str],
    outcomes: dict[str, list[float]],
    events: list[Any],
) -> list[str]:
    """Top-K alternatives with diversity constraint (Refinement #3).

    Returns up to COUNTERFACTUAL_TOP_K alternatives ensuring
    at least CAUSAL_DIVERSITY_CLUSTERS different capability clusters.
    """
    candidates: list[tuple[str, float, str]] = []
    actual_task_type = actual_agent.split("::", 1)[1] if "::" in actual_agent else "default"
    actual_cluster = _capability_cluster(actual_agent.split("::")[0] if "::" in actual_agent else actual_agent, events)

    for key in sorted(agent_keys):
        if key == actual_agent:
            continue
        aid = key.split("::")[0] if "::" in key else key
        tt = key.split("::")[1] if "::" in key else "default"

        if tt == actual_task_type:
            scores = outcomes.get(key, [])
            if len(scores) >= CAUSAL_MIN_SAMPLES:
                mean = sum(scores) / len(scores)
                cluster = _capability_cluster(aid, events)
                candidates.append((aid, mean, cluster))

    candidates.sort(key=lambda x: -x[1])

    selected: list[str] = []
    seen_clusters: set[str] = set()
    seen_clusters.add(actual_cluster)

    for aid, mean, cluster in candidates:
        if len(selected) >= COUNTERFACTUAL_TOP_K:
            break
        if len(seen_clusters) < CAUSAL_DIVERSITY_CLUSTERS:
            selected.append(aid)
            seen_clusters.add(cluster)
        elif cluster in seen_clusters:
            if len(selected) < COUNTERFACTUAL_TOP_K:
                selected.append(aid)

    return selected[:COUNTERFACTUAL_TOP_K]


def simulate_intervention(
    *,
    agent_id: str,
    task_type: str,
    actual_agent: str,
    alternative_agent: str,
    events: list[Any],
    event_ids: list[str] | None = None,
) -> CounterfactualResult:
    """do(select_agent = alternative_agent) — pure projection.

    Causal purity (Refinement #1): reads ONLY event stream.
    Does NOT depend on dynamics/learning/routing state.
    """
    if event_ids is None:
        event_ids = []
    key = f"{agent_id}::{task_type}"
    alt_key = f"{alternative_agent}::{task_type}"
    analysis_id = _stable_causal_id(f"{key}->{alt_key}", event_ids)

    outcomes = _agent_task_outcomes(events)
    actual_scores = outcomes.get(key, [])
    alt_scores = outcomes.get(alt_key, [])

    actual_n = len(actual_scores)
    alt_n = len(alt_scores)
    min_n = min(actual_n, alt_n)

    if min_n < CAUSAL_MIN_SAMPLES:
        return CounterfactualResult(
            agent_id=agent_id, task_type=task_type,
            actual_agent=actual_agent, alternative_agent=alternative_agent,
            actual_outcome=sum(actual_scores) / actual_n if actual_n > 0 else 0.0,
            alternative_outcome=sum(alt_scores) / alt_n if alt_n > 0 else 0.0,
            impact_score=0.0, confidence=0.0,
            sample_count=min_n, direction=ImpactDirection.NEUTRAL,
            analysis_id=analysis_id,
        )

    actual_mean = sum(actual_scores) / actual_n
    alt_mean = sum(alt_scores) / alt_n
    impact = alt_mean - actual_mean

    confidence = 1.0 - math.exp(-min_n / float(CAUSAL_MIN_SAMPLES))

    if impact > CAUSAL_IMPACT_THRESHOLD:
        direction = ImpactDirection.POSITIVE
    elif impact < -CAUSAL_IMPACT_THRESHOLD:
        direction = ImpactDirection.NEGATIVE
    else:
        direction = ImpactDirection.NEUTRAL

    return CounterfactualResult(
        agent_id=agent_id, task_type=task_type,
        actual_agent=actual_agent, alternative_agent=alternative_agent,
        actual_outcome=actual_mean, alternative_outcome=alt_mean,
        impact_score=max(-1.0, min(1.0, impact)),
        confidence=confidence,
        sample_count=min_n,
        direction=str(direction),
        analysis_id=analysis_id,
    )


def top_alternatives(
    *,
    agent_id: str,
    task_type: str,
    events: list[Any],
    event_ids: list[str] | None = None,
) -> list[CounterfactualResult]:
    """Run counterfactual simulation for top-K alternatives (diversity-aware)."""
    if event_ids is None:
        event_ids = []
    outcomes = _agent_task_outcomes(events)
    actual_key = f"{agent_id}::{task_type}"
    all_keys = set(outcomes.keys())
    alternatives = _diverse_top_k(actual_key, all_keys, outcomes, events)

    results: list[CounterfactualResult] = []
    for alt in alternatives:
        r = simulate_intervention(
            agent_id=agent_id, task_type=task_type,
            actual_agent=agent_id, alternative_agent=alt,
            events=events, event_ids=event_ids,
        )
        results.append(r)
    return results