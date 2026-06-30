from __future__ import annotations

from allbrain.episodic.consolidation import should_store_episode


class TestShouldStoreEpisode:
    def test_high_importance(self):
        assert should_store_episode(reward=0.5, importance=0.60) is True

    def test_exact_threshold(self):
        assert should_store_episode(reward=0.5, importance=0.50) is True

    def test_below_threshold(self):
        assert should_store_episode(reward=0.5, importance=0.30) is False

    def test_zero_importance_low_reward(self):
        # reward=0.1 <= LOW_REWARD_THRESHOLD=0.20 → big failure → stored
        assert should_store_episode(reward=0.1, importance=0.0) is True

    def test_very_high_reward(self):
        assert should_store_episode(reward=0.90, importance=0.1) is True

    def test_exact_high_reward_threshold(self):
        assert should_store_episode(reward=0.80, importance=0.1) is True

    def test_very_low_reward(self):
        assert should_store_episode(reward=0.10, importance=0.1) is True

    def test_exact_low_reward_threshold(self):
        assert should_store_episode(reward=0.20, importance=0.1) is True

    def test_mid_reward_low_importance(self):
        assert should_store_episode(reward=0.50, importance=0.1) is False

    def test_high_importance_extreme_reward(self):
        assert should_store_episode(reward=0.95, importance=0.90) is True

    def test_boundary_high_reward_just_below(self):
        assert should_store_episode(reward=0.79, importance=0.49) is False

    def test_boundary_low_reward_just_above(self):
        assert should_store_episode(reward=0.21, importance=0.49) is False

    def test_custom_thresholds(self):
        assert (
            should_store_episode(
                reward=0.6,
                importance=0.4,
                importance_threshold=0.3,
            )
            is True
        )

    def test_custom_high_reward(self):
        assert (
            should_store_episode(
                reward=0.5,
                importance=0.2,
                high_reward_threshold=0.4,
            )
            is True
        )
