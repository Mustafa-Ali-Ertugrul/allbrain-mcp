from __future__ import annotations

from allbrain.episodic.model import (
    HIGH_REWARD_THRESHOLD,
    IMPORTANCE_THRESHOLD,
    LOW_REWARD_THRESHOLD,
)


def should_store_episode(
    *,
    reward: float,
    importance: float,
    importance_threshold: float = IMPORTANCE_THRESHOLD,
    high_reward_threshold: float = HIGH_REWARD_THRESHOLD,
    low_reward_threshold: float = LOW_REWARD_THRESHOLD,
) -> bool:
    """Store if importance >= threshold OR extreme rewards (very high OR very low).

    Rule: importance >= threshold → store
          reward >= high_reward_threshold → store (big success)
          reward <= low_reward_threshold → store (big failure)
          otherwise → forget
    """
    if importance >= importance_threshold:
        return True
    if reward >= high_reward_threshold:
        return True
    if reward <= low_reward_threshold:
        return True
    return False
