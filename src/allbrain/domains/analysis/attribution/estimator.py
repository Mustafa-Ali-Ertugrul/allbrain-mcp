from __future__ import annotations

from allbrain.domains.analysis.attribution.model import ATTRIBUTION_CONFIDENCE_ALPHA


def update_signal_reward(
    old_reward: float,
    contribution: float,
    *,
    alpha: float = ATTRIBUTION_CONFIDENCE_ALPHA,
) -> float:
    """EMA: new = α × contribution + (1 − α) × old"""
    return alpha * float(contribution) + (1.0 - alpha) * float(old_reward)


def update_signal_count(
    old_count: int,
) -> int:
    return old_count + 1


def initial_signal_rewards() -> dict[str, float]:
    return {
        "capability": 0.0,
        "learning": 0.0,
        "dynamics": 0.0,
        "causal": 0.0,
    }


def initial_signal_counts() -> dict[str, int]:
    return {
        "capability": 0,
        "learning": 0,
        "dynamics": 0,
        "causal": 0,
    }
