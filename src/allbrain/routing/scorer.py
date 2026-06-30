from __future__ import annotations

from allbrain.routing.model import (
    ROUTING_CONSENSUS_WEIGHT,
    ROUTING_REPUTATION_WEIGHT,
    ROUTING_RUNTIME_WEIGHT,
    ROUTING_TIE_EPSILON,
    ROUTING_TRUST_WEIGHT,
)


def _stable_routing_id(task_type: str, event_ids: list[str] | None = None) -> str:
    import hashlib
    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{task_type}:{ek}".encode()).digest()
    return f"routing-{d.hex()[:12]}"


def selection_score(
    *,
    reputation: float,
    runtime_score: float,
    calibrated_trust: float,
    consensus_score: float,
) -> float:
    raw = (
        float(reputation) * ROUTING_REPUTATION_WEIGHT
        + float(runtime_score) * ROUTING_RUNTIME_WEIGHT
        + float(calibrated_trust) * ROUTING_TRUST_WEIGHT
        + float(consensus_score) * ROUTING_CONSENSUS_WEIGHT
    )
    return max(0.0, min(1.0, raw))


def best_agent(scored: dict[str, float]) -> str | None:
    if not scored:
        return None
    ordered = sorted(scored.items(), key=lambda item: (-item[1], item[0]))
    return ordered[0][0]


def rank_agents(scored: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(scored.items(), key=lambda item: (-item[1], item[0]))


def score_bounds(v: float) -> float:
    return max(0.0, min(1.0, v))


def extended_selection_score(
    *,
    reputation: float,
    runtime_score: float,
    calibrated_trust: float,
    consensus_score: float,
    capability_match: float,
) -> float:
    raw = (
        float(reputation) * 0.30
        + float(runtime_score) * 0.30
        + float(calibrated_trust) * 0.15
        + float(consensus_score) * 0.10
        + float(capability_match) * 0.15
    )
    return max(0.0, min(1.0, raw))


def adaptive_selection_score(
    *,
    reputation: float,
    runtime_score: float,
    calibrated_trust: float,
    consensus_score: float,
    capability_match: float,
    learned_capability: float,
) -> float:
    raw = (
        float(reputation) * 0.25
        + float(runtime_score) * 0.25
        + float(calibrated_trust) * 0.15
        + float(consensus_score) * 0.10
        + float(capability_match) * 0.15
        + float(learned_capability) * 0.10
    )
    return max(0.0, min(1.0, raw))


def dynamics_selection_score(
    *,
    reputation: float,
    runtime_score: float,
    calibrated_trust: float,
    consensus_score: float,
    capability_match: float,
    learned_capability: float,
    drift_score: float = 0.0,
    trend_label: str = "stable",
    forecast_score: float = 0.0,
) -> float:
    base = adaptive_selection_score(
        reputation=reputation,
        runtime_score=runtime_score,
        calibrated_trust=calibrated_trust,
        consensus_score=consensus_score,
        capability_match=capability_match,
        learned_capability=learned_capability,
    )
    drift_penalty = max(0.85, 1.0 - float(drift_score))
    trend_boost_map = {
        "improving": 0.05,
        "stable": 0.0,
        "degrading": -0.05,
        "unstable": -0.05,
    }
    trend_boost = trend_boost_map.get(str(trend_label).lower(), 0.0)
    forecast_bonus = float(forecast_score) * 0.05
    raw = base * drift_penalty * (1.0 + trend_boost) + forecast_bonus
    return max(0.0, min(1.0, raw))


def causal_selection_score(
    *,
    reputation: float,
    runtime_score: float,
    calibrated_trust: float,
    consensus_score: float,
    capability_match: float,
    learned_capability: float,
    drift_score: float = 0.0,
    trend_label: str = "stable",
    forecast_score: float = 0.0,
    impact_score: float = 0.0,
    causal_confidence: float = 0.0,
) -> float:
    """Sprint 55: wraps dynamics with causal refinement.

    Causal purity: only adds after dynamics is computed.
    Does NOT depend on any intermediate state — pure function.
    """
    base = dynamics_selection_score(
        reputation=reputation, runtime_score=runtime_score,
        calibrated_trust=calibrated_trust, consensus_score=consensus_score,
        capability_match=capability_match, learned_capability=learned_capability,
        drift_score=drift_score, trend_label=trend_label, forecast_score=forecast_score,
    )
    counterfactual_bonus = float(impact_score) * 0.10
    confidence_adjustment = float(causal_confidence) * 0.05
    raw = base + counterfactual_bonus + confidence_adjustment
    return max(0.0, min(1.0, raw))


def unified_decision_score(
    *,
    capability: float = 0.0,
    learning: float = 0.0,
    dynamics: float = 0.0,
    causal: float = 0.0,
    capability_weight: float = 0.25,
    learning_weight: float = 0.25,
    dynamics_weight: float = 0.25,
    causal_weight: float = 0.25,
) -> float:
    """Sprint 56: f(signal_vector) = Σ vector[i] * weights[i].

    Single-point decision function replacing the 5-layer chain.
    Default weights: uniform 0.25 each.
    """
    raw = (
        float(capability) * float(capability_weight)
        + float(learning) * float(learning_weight)
        + float(dynamics) * float(dynamics_weight)
        + float(causal) * float(causal_weight)
    )
    return max(0.0, min(1.0, raw))
