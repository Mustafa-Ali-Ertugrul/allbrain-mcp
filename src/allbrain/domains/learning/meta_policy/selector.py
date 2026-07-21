from __future__ import annotations

import math
import random as _random
from hashlib import sha256

from allbrain.domains.learning.meta_policy.model import (
    PolicyMode,
    PolicyState,
)


def _event_seed(agent_id: str, task_type: str, decision_count: int) -> int:
    """Refinement #1: event-derived seed for replay determinism."""
    key = f"{agent_id}:{task_type}:{decision_count}"
    return int.from_bytes(sha256(key.encode("utf-8")).digest()[:8], "big") % (10**9)


def select_mode(
    policy_state: PolicyState,
    *,
    agent_id: str = "default",
    task_type: str = "default",
) -> str:
    """Hybrid mode selector with exclusive randomness.

    Refinement #2: if exploration active → softmax OFF (pure random).
    Otherwise → softmax only. Never both at the same time to prevent
    double randomness and non-stationary policy.
    """
    seed = _event_seed(agent_id, task_type, policy_state.decision_count)
    rng = _random.Random(seed)

    if rng.random() < policy_state.exploration_rate:
        return rng.choice([PolicyMode.FUSION, PolicyMode.CAUSAL, PolicyMode.DYNAMIC, PolicyMode.LEGACY])

    return _softmax_select(policy_state, seed + 1)


def _softmax_select(policy_state: PolicyState, seed: int) -> str:
    """Temperature-scaled softmax over EMA rewards."""
    rng = _random.Random(seed)
    modes = list(policy_state.mode_stats.keys())
    if not modes:
        return PolicyMode.LEGACY

    rewards = [policy_state.mode_stats[m].ema_reward for m in modes]
    temp = max(policy_state.temperature, 0.01)

    shifted = [(r - max(rewards)) / temp for r in rewards]
    exp_vals = [math.exp(s) for s in shifted]
    total = sum(exp_vals)

    if abs(total) < 1e-12:
        return PolicyMode.LEGACY

    probs = [e / total for e in exp_vals]
    r = rng.random()
    cumulative = 0.0
    for i, p in enumerate(probs):
        cumulative += p
        if r < cumulative:
            return modes[i]
    return PolicyMode.LEGACY
