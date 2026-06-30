from __future__ import annotations

from allbrain.episodic.manager import EpisodicManager
from allbrain.episodic.model import MAX_EPISODES


class TestStoreEpisode:
    def test_store_high_importance(self):
        mgr = EpisodicManager()
        result = mgr.store_episode(
            reward=0.8,
            workspace_items=["a", "b"],
            decision_id="dec-1",
            activation=0.5,
        )
        assert result["stored"] is True
        assert result["importance"] > 0

    def test_not_stored_low_importance_mid_reward(self):
        mgr = EpisodicManager()
        result = mgr.store_episode(
            reward=0.5,
            workspace_items=["a"],
            decision_id="dec-1",
            activation=0.1,
        )
        # reward=0.5, activation=0.1, novelty=1.0 → importance=0.05 < 0.5
        # reward not extreme (0.8 > 0.5 < 0.2) → not stored
        assert result["stored"] is False

    def test_store_extreme_low_reward(self):
        mgr = EpisodicManager()
        result = mgr.store_episode(
            reward=0.05,
            workspace_items=["a"],
            decision_id="dec-1",
            activation=0.5,
        )
        # reward=0.05 <= LOW_REWARD_THRESHOLD=0.20 → stored
        assert result["stored"] is True

    def test_store_extreme_high_reward(self):
        mgr = EpisodicManager()
        result = mgr.store_episode(
            reward=0.95,
            workspace_items=["a"],
            decision_id="dec-1",
            activation=0.1,
        )
        # reward=0.95 >= HIGH_REWARD_THRESHOLD=0.80 → stored
        assert result["stored"] is True

    def test_episode_id_generated(self):
        mgr = EpisodicManager()
        result = mgr.store_episode(
            reward=0.8,
            workspace_items=["x"],
            decision_id="dec-1",
        )
        assert result["episode_id"].startswith("ep-")

    def test_stats_after_store(self):
        mgr = EpisodicManager()
        mgr.store_episode(reward=0.9, workspace_items=["a"], decision_id="dec-1")
        mgr.store_episode(reward=0.8, workspace_items=["b"], decision_id="dec-2")
        stats = mgr.stats()
        assert stats["total"] == 2
        assert stats["retained"] == 2
        assert stats["forgotten"] == 0


class TestRetrieve:
    def test_empty_store(self):
        mgr = EpisodicManager()
        result = mgr.retrieve(["a"])
        assert result["retrieved"] == 0

    def test_retrieve_similar(self):
        mgr = EpisodicManager()
        mgr.store_episode(reward=0.9, workspace_items=["a", "b"], decision_id="dec-1")
        mgr.store_episode(reward=0.8, workspace_items=["c", "d"], decision_id="dec-2")
        result = mgr.retrieve(["a", "b"])
        assert result["retrieved"] >= 1
        assert result["best_similarity"] > 0

    def test_retrieve_updates_count(self):
        mgr = EpisodicManager()
        mgr.store_episode(reward=0.9, workspace_items=["a", "b"], decision_id="dec-1")
        result = mgr.retrieve(["a", "b"])
        assert result["retrieved"] == 1
        ep = mgr.get_all_episodes()[0]
        assert ep.retrieval_count == 1


class TestStats:
    def test_empty_stats(self):
        mgr = EpisodicManager()
        stats = mgr.stats()
        assert stats["total"] == 0
        assert stats["retained"] == 0

    def test_forgotten_tracking(self):
        mgr = EpisodicManager()
        mgr.store_episode(reward=0.9, workspace_items=["a"], decision_id="d1")
        stats = mgr.stats()
        assert stats["forgotten"] == 0


class TestFIFOEviction:
    def test_max_episodes_eviction(self):
        mgr = EpisodicManager()
        # Fill to MAX_EPISODES + 1
        for i in range(MAX_EPISODES + 5):
            mgr.store_episode(
                reward=0.9,
                workspace_items=[f"item_{i}"],
                decision_id=f"dec-{i}",
                activation=1.0,
            )
        stats = mgr.stats()
        assert stats["retained"] == MAX_EPISODES
        assert stats["forgotten"] == 5
        assert stats["total"] == MAX_EPISODES + 5

    def test_oldest_episode_evicted_first(self):
        mgr = EpisodicManager()
        first_id = None
        for i in range(MAX_EPISODES + 1):
            result = mgr.store_episode(
                reward=0.9,
                workspace_items=[f"item_{i}"],
                decision_id=f"dec-{i}",
                activation=1.0,
            )
            if i == 0:
                first_id = result["episode_id"]
        # First episode should have been evicted
        all_ids = {ep.episode_id for ep in mgr.get_all_episodes()}
        assert first_id not in all_ids
