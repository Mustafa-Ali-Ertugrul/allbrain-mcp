from __future__ import annotations

from allbrain.fusion.model import (
    FUSION_DEFAULT_WEIGHT,
    SignalVector,
    SignalWeights,
)


def unified_decision_score(
    signal_vector: SignalVector,
    weights: SignalWeights | None = None,
) -> float:
    """Sprint 56 core: f(signal_vector) = Σ vector[i] * weights[i].

    Pure deterministic function — no state, no IO, no side effects.

    Default weights: uniform 0.25 each when none provided.
    """
    if weights is None:
        weights = SignalWeights(
            capability=FUSION_DEFAULT_WEIGHT,
            learning=FUSION_DEFAULT_WEIGHT,
            dynamics=FUSION_DEFAULT_WEIGHT,
            causal=FUSION_DEFAULT_WEIGHT,
        )
    raw = (
        signal_vector.capability * weights.capability
        + signal_vector.learning * weights.learning
        + signal_vector.dynamics * weights.dynamics
        + signal_vector.causal * weights.causal
    )
    return max(0.0, min(1.0, raw))


def build_signal_vector(
    *,
    agent_id: str,
    task_type: str,
    capability_match: float,
    learned_capability: float,
    dynamics_score: float,
    causal_score: float,
) -> SignalVector:
    """Pack 4 channel scores into SignalVector."""
    return SignalVector(
        agent_id=agent_id,
        task_type=task_type,
        capability=float(capability_match),
        learning=float(learned_capability),
        dynamics=float(dynamics_score),
        causal=float(causal_score),
    )
