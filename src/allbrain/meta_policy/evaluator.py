from __future__ import annotations

import math

from allbrain.meta_policy.model import (
    META_POLICY_KL_THRESHOLD,
    META_POLICY_SNAPSHOT_INTERVAL,
    ModeStats,
    PolicyState,
)


def _to_prob_distribution(mode_stats: dict[str, ModeStats]) -> dict[str, float]:
    total = sum(stats.ema_reward + 0.01 for stats in mode_stats.values())
    if abs(total) < 1e-12:
        n = len(mode_stats) or 1
        return {m: 1.0 / n for m in mode_stats}
    return {m: (stats.ema_reward + 0.01) / total for m, stats in mode_stats.items()}


def compute_kl_divergence(
    old_dist: dict[str, float],
    new_dist: dict[str, float],
) -> float:
    """KL(new_dist || old_dist)."""
    kl = 0.0
    for mode in old_dist:
        p = new_dist.get(mode, 1e-12)
        q = old_dist[mode]
        if q > 0 and p > 0:
            kl += p * math.log(p / q)
    return kl


def detect_policy_drift(
    old_policy: PolicyState,
    new_policy: PolicyState,
    *,
    threshold: float = META_POLICY_KL_THRESHOLD,
) -> bool:
    """KL divergence between old and new policy distributions.

    Refinement #4: threshold-gated detection.
    Refinement #3: snapshot triggered every META_POLICY_SNAPSHOT_INTERVAL decisions.
    """
    old_dist = _to_prob_distribution(old_policy.mode_stats)
    new_dist = _to_prob_distribution(new_policy.mode_stats)
    kl = compute_kl_divergence(old_dist, new_dist)
    return kl > threshold


def should_snapshot(policy_state: PolicyState) -> bool:
    """Interval-based snapshot check — Refinement #3.

    Returns True if decision_count is a multiple of SNAPSHOT_INTERVAL.
    """
    return policy_state.decision_count > 0 and policy_state.decision_count % META_POLICY_SNAPSHOT_INTERVAL == 0
