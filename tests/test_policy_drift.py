from __future__ import annotations

from allbrain.meta_policy import (
    META_POLICY_KL_THRESHOLD,
    META_POLICY_SNAPSHOT_INTERVAL,
    ModeStats,
    PolicyState,
    compute_kl_divergence,
    detect_policy_drift,
    should_snapshot,
)


class TestPolicyDrift:
    def test_kl_divergence(self):
        old = {"a": 0.5, "b": 0.5}
        new = {"a": 0.9, "b": 0.1}
        kl = compute_kl_divergence(old, new)
        assert kl > 0.0

    def test_same_distribution_zero(self):
        d = {"a": 0.5, "b": 0.5}
        kl = compute_kl_divergence(d, d)
        assert kl < 1e-9

    def test_drift_detected(self):
        old = PolicyState(
            mode_stats={
                "a": ModeStats(mode="a", count=10, avg_reward=0.5, ema_reward=0.5, variance=0),
                "b": ModeStats(mode="b", count=10, avg_reward=0.5, ema_reward=0.5, variance=0),
            },
            exploration_rate=0.05, temperature=1.0, last_updated="", decision_count=1,
        )
        new = PolicyState(
            mode_stats={
                "a": ModeStats(mode="a", count=10, avg_reward=1.0, ema_reward=1.0, variance=0),
                "b": ModeStats(mode="b", count=10, avg_reward=0.0, ema_reward=0.0, variance=0),
            },
            exploration_rate=0.05, temperature=1.0, last_updated="", decision_count=2,
        )
        assert detect_policy_drift(old, new)

    def test_no_drift_stable(self):
        state = PolicyState(
            mode_stats={
                "a": ModeStats(mode="a", count=10, avg_reward=0.5, ema_reward=0.5, variance=0),
                "b": ModeStats(mode="b", count=10, avg_reward=0.5, ema_reward=0.5, variance=0),
            },
            exploration_rate=0.05, temperature=1.0, last_updated="", decision_count=1,
        )
        assert not detect_policy_drift(state, state)

    def test_snapshot_interval(self):
        s1 = PolicyState(mode_stats={}, exploration_rate=0, temperature=1, last_updated="", decision_count=1)
        assert not should_snapshot(s1)
        s_at = PolicyState(mode_stats={}, exploration_rate=0, temperature=1, last_updated="", decision_count=META_POLICY_SNAPSHOT_INTERVAL)
        assert should_snapshot(s_at)

    def test_threshold_respected(self):
        assert META_POLICY_KL_THRESHOLD == 0.5
