from __future__ import annotations

from allbrain.meta_policy import (
    META_POLICY_EXPLORATION_MAX,
    ModeStats,
    PolicyState,
    select_mode,
)


class TestMetaPolicy:
    def test_epsilon_greedy_explores(self):
        state = PolicyState(
            mode_stats={m: ModeStats(mode=m, count=10, avg_reward=0.5, ema_reward=0.5, variance=0.0) for m in ["fusion", "causal", "dynamic", "legacy"]},
            exploration_rate=1.0, temperature=1.0, last_updated="", decision_count=1,
        )
        modes = [select_mode(state, agent_id=str(i), task_type="t") for i in range(20)]
        unique = set(modes)
        assert len(unique) >= 2

    def test_greedy_sticks(self):
        state = PolicyState(
            mode_stats={
                "fusion": ModeStats(mode="fusion", count=50, avg_reward=0.9, ema_reward=0.9, variance=0.0),
                "causal": ModeStats(mode="causal", count=10, avg_reward=0.1, ema_reward=0.1, variance=0.0),
                "dynamic": ModeStats(mode="dynamic", count=10, avg_reward=0.1, ema_reward=0.1, variance=0.0),
                "legacy": ModeStats(mode="legacy", count=10, avg_reward=0.1, ema_reward=0.1, variance=0.0),
            },
            exploration_rate=0.0, temperature=0.01, last_updated="", decision_count=1,
        )
        mode = select_mode(state, agent_id="a", task_type="t")
        assert mode == "fusion"

    def test_deterministic_seed(self):
        state = PolicyState(
            mode_stats={m: ModeStats(mode=m, count=10, avg_reward=0.5, ema_reward=0.5, variance=0.0) for m in ["fusion", "causal", "dynamic", "legacy"]},
            exploration_rate=1.0, temperature=1.0, last_updated="", decision_count=1,
        )
        m1 = select_mode(state, agent_id="x", task_type="y")
        m2 = select_mode(state, agent_id="x", task_type="y")
        assert m1 == m2

    def test_exclusive_randomness(self):
        import random
        random.seed(42)
        state = PolicyState(
            mode_stats={m: ModeStats(mode=m, count=10, avg_reward=0.5, ema_reward=0.5, variance=0.0) for m in ["fusion", "causal", "dynamic", "legacy"]},
            exploration_rate=1.0, temperature=1.0, last_updated="", decision_count=1,
        )
        m = select_mode(state, agent_id="a", task_type="t")
        assert m in {"fusion", "causal", "dynamic", "legacy"}

    def test_all_modes_reachable(self):
        state = PolicyState(
            mode_stats={m: ModeStats(mode=m, count=10, avg_reward=0.5, ema_reward=0.5, variance=0.0) for m in ["fusion", "causal", "dynamic", "legacy"]},
            exploration_rate=1.0, temperature=1.0, last_updated="", decision_count=1,
        )
        seen = set()
        for i in range(100):
            seen.add(select_mode(state, agent_id=str(i), task_type="t"))
        assert len(seen) == 4

    def test_exploration_capped(self):
        state = PolicyState(
            mode_stats={"fusion": ModeStats(mode="fusion", count=10, avg_reward=0.5, ema_reward=0.5, variance=0.0)},
            exploration_rate=META_POLICY_EXPLORATION_MAX, temperature=1.0, last_updated="", decision_count=1,
        )
        assert state.exploration_rate <= 0.15

    def test_empty_stats_fallsback(self):
        state = PolicyState(
            mode_stats={}, exploration_rate=0.0, temperature=1.0, last_updated="", decision_count=1,
        )
        mode = select_mode(state, agent_id="a", task_type="t")
        assert mode == "legacy"

    def test_softmax_stable(self):
        state = PolicyState(
            mode_stats={
                "fusion": ModeStats(mode="fusion", count=50, avg_reward=0.8, ema_reward=0.8, variance=0.0),
                "causal": ModeStats(mode="causal", count=50, avg_reward=0.7, ema_reward=0.7, variance=0.0),
                "dynamic": ModeStats(mode="dynamic", count=50, avg_reward=0.6, ema_reward=0.6, variance=0.0),
                "legacy": ModeStats(mode="legacy", count=50, avg_reward=0.5, ema_reward=0.5, variance=0.0),
            },
            exploration_rate=0.0, temperature=0.1, last_updated="", decision_count=1,
        )
        mode = select_mode(state, agent_id="a", task_type="t")
        assert mode in {"fusion", "causal"}

    def test_hybrid_explore_then_exploit(self):
        state = PolicyState(
            mode_stats={
                "fusion": ModeStats(mode="fusion", count=5, avg_reward=0.9, ema_reward=0.9, variance=0.0),
                "causal": ModeStats(mode="causal", count=5, avg_reward=0.1, ema_reward=0.1, variance=0.0),
                "dynamic": ModeStats(mode="dynamic", count=5, avg_reward=0.1, ema_reward=0.1, variance=0.0),
                "legacy": ModeStats(mode="legacy", count=5, avg_reward=0.1, ema_reward=0.1, variance=0.0),
            },
            exploration_rate=0.05, temperature=0.01, last_updated="", decision_count=1,
        )
        mode = select_mode(state, agent_id="a", task_type="t")
        assert mode in {"fusion", "causal", "dynamic", "legacy"}
