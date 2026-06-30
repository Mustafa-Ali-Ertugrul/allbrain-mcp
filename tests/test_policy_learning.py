from __future__ import annotations

from allbrain.meta_policy import ModeStats, compute_reward, update_mode_stats


class TestPolicyLearning:
    def test_ema_update(self):
        s = ModeStats(mode="fusion", count=5, avg_reward=0.5, ema_reward=0.5, variance=0.0)
        updated = update_mode_stats(s, 0.9)
        assert updated.count == 6
        assert updated.ema_reward > 0.5

    def test_variance_tracking(self):
        s = ModeStats(mode="fusion", count=10, avg_reward=0.5, ema_reward=0.5, variance=0.0)
        updated = update_mode_stats(s, 0.9)
        assert updated.variance > 0.0

    def test_reward_weights(self):
        r = compute_reward(decision_score=0.8, outcome_quality=0.9, stability_penalty=0.1)
        expected = 0.7 * 0.9 + 0.2 * 0.8 - 0.1 * 0.1
        assert abs(r - expected) < 1e-9

    def test_multi_update(self):
        s = ModeStats(mode="causal", count=0, avg_reward=0.0, ema_reward=0.0, variance=0.0)
        for r in [0.1, 0.3, 0.5, 0.7, 0.9]:
            s = update_mode_stats(s, r)
        assert s.ema_reward > 0.2

    def test_negative_reward(self):
        s = ModeStats(mode="dynamic", count=10, avg_reward=0.5, ema_reward=0.5, variance=0.0)
        updated = update_mode_stats(s, -0.5)
        assert updated.ema_reward < 0.5

    def test_count_increment(self):
        s = ModeStats(mode="legacy", count=0, avg_reward=0.0, ema_reward=0.0, variance=0.0)
        updated = update_mode_stats(s, 0.5)
        assert updated.count == 1

    def test_avg_update(self):
        s = ModeStats(mode="fusion", count=5, avg_reward=0.4, ema_reward=0.4, variance=0.0)
        updated = update_mode_stats(s, 0.6)
        assert abs(updated.avg_reward - (0.4 * 5 + 0.6) / 6) < 1e-9

    def test_stability_isolation(self):
        s1 = update_mode_stats(ModeStats(mode="a", count=0, avg_reward=0, ema_reward=0, variance=0), 0.8)
        s2 = update_mode_stats(ModeStats(mode="b", count=0, avg_reward=0, ema_reward=0, variance=0), 0.2)
        assert s1.ema_reward != s2.ema_reward
