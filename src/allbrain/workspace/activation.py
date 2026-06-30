from __future__ import annotations

import math

from allbrain.workspace.model import DECAY_RATE


def compute_activation(
    *,
    attention_weight: float,
    reward: float,
    age: int,
    decay_rate: float = DECAY_RATE,
) -> float:
    """activation = attention_weight × reward × exp(-age × decay_rate)"""
    recency = math.exp(-float(age) * decay_rate)
    return float(attention_weight) * float(reward) * recency
