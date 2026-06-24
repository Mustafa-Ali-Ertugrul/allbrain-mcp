from __future__ import annotations

from allbrain.attention.model import (
    ATTENTION_IMPORTANCE_ALPHA,
    ATTENTION_COST_CAP,
    SIGNAL_COSTS,
)


def estimate_signal_importance(
    *,
    reward: float,
    attribution: float,
    previous_importance: float = 0.0,
    alpha: float = ATTENTION_IMPORTANCE_ALPHA,
) -> float:
    """EMA: new = α × (reward × attribution) + (1 − α) × old"""
    signal_reward = float(reward) * float(attribution)
    return alpha * signal_reward + (1.0 - alpha) * previous_importance


def estimate_signal_cost(signal: str) -> float:
    cost = SIGNAL_COSTS.get(signal, 1.0)
    return min(float(cost), ATTENTION_COST_CAP)