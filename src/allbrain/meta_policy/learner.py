from __future__ import annotations

from allbrain.meta_policy.model import (
    META_POLICY_EMA_ALPHA,
    ModeStats,
)


def update_mode_stats(
    stats: ModeStats,
    reward: float,
    *,
    alpha: float = META_POLICY_EMA_ALPHA,
) -> ModeStats:
    """EMA update + variance tracking.

    new_ema = α * reward + (1 - α) * old_ema
    new_variance = α * (reward - old_ema)^2 + (1 - α) * old_variance
    """
    new_ema = alpha * reward + (1.0 - alpha) * float(stats.ema_reward)
    diff = reward - stats.ema_reward
    new_variance = alpha * (diff * diff) + (1.0 - alpha) * float(stats.variance)
    new_count = stats.count + 1
    new_avg = (float(stats.avg_reward) * stats.count + reward) / new_count

    return ModeStats(
        mode=stats.mode,
        count=new_count,
        avg_reward=new_avg,
        ema_reward=max(-1.0, min(1.0, new_ema)),
        variance=max(0.0, new_variance),
    )


def update_temperature(
    old_temp: float,
    decision_count: int,
) -> float:
    from allbrain.meta_policy.model import META_POLICY_TEMPERATURE_DECAY

    return max(0.1, old_temp * META_POLICY_TEMPERATURE_DECAY)


def update_exploration_rate(
    old_rate: float,
    decision_count: int,
) -> float:
    from allbrain.meta_policy.model import META_POLICY_EXPLORATION_MAX, META_POLICY_EXPLORATION_MIN

    decay = max(META_POLICY_EXPLORATION_MIN, old_rate * 0.99)
    return min(META_POLICY_EXPLORATION_MAX, max(META_POLICY_EXPLORATION_MIN, decay))


def default_mode_stats() -> dict[str, ModeStats]:
    from allbrain.meta_policy.model import PolicyMode

    return {
        m.value: ModeStats(mode=m.value, count=0, avg_reward=0.0, ema_reward=0.0, variance=0.0)
        for m in [PolicyMode.FUSION, PolicyMode.CAUSAL, PolicyMode.DYNAMIC, PolicyMode.LEGACY]
    }


def _default_mode_stats() -> dict[str, ModeStats]:
    from allbrain.meta_policy.model import PolicyMode

    return {
        m.value: ModeStats(mode=m.value, count=0, avg_reward=0.0, ema_reward=0.0, variance=0.0)
        for m in [PolicyMode.FUSION, PolicyMode.CAUSAL, PolicyMode.DYNAMIC, PolicyMode.LEGACY]
    }
