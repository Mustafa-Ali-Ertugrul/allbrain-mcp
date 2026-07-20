from __future__ import annotations

import pytest

from allbrain.domains.analysis.episodic.events import (
    make_episode_created_payload,
    make_episode_forgotten_payload,
    make_episode_retrieved_payload,
    validate_episode_created,
    validate_episode_forgotten,
    validate_episode_retrieved,
)


class TestEpisodeCreatedPayload:
    def test_valid_payload(self):
        p = make_episode_created_payload(episode_id="ep-123", importance=0.75, reward=0.6)
        assert p["episode_id"] == "ep-123"
        assert p["importance"] == 0.75
        assert p["reward"] == 0.6
        assert "template_version" in p

    def test_validation_passes(self):
        p = {"episode_id": "ep-x", "importance": 0.5, "reward": 1.0}
        validate_episode_created(p)  # should not raise

    def test_missing_keys(self):
        with pytest.raises(ValueError, match="episode_created missing"):
            validate_episode_created({"importance": 0.5})

    def test_non_string_id(self):
        with pytest.raises(ValueError, match="episode_id must be str"):
            validate_episode_created({"episode_id": 123, "importance": 0.5, "reward": 0.5})

    def test_non_numeric_importance(self):
        with pytest.raises(ValueError, match="importance must be numeric"):
            validate_episode_created({"episode_id": "ep-x", "importance": "high", "reward": 0.5})

    def test_importance_as_int(self):
        p = {"episode_id": "ep-x", "importance": 1, "reward": 0.5}
        validate_episode_created(p)  # should not raise


class TestEpisodeRetrievedPayload:
    def test_valid_payload(self):
        p = make_episode_retrieved_payload(retrieved=3, best_similarity=0.82)
        assert p["retrieved"] == 3
        assert p["best_similarity"] == 0.82

    def test_validation_passes(self):
        p = {"retrieved": 5, "best_similarity": 0.9}
        validate_episode_retrieved(p)

    def test_missing_keys(self):
        with pytest.raises(ValueError, match="episode_retrieved missing"):
            validate_episode_retrieved({"retrieved": 5})

    def test_negative_retrieved(self):
        with pytest.raises(ValueError, match="retrieved must be non-negative"):
            validate_episode_retrieved({"retrieved": -1, "best_similarity": 0.5})

    def test_non_numeric_best_similarity(self):
        with pytest.raises(ValueError, match="best_similarity must be numeric"):
            validate_episode_retrieved({"retrieved": 2, "best_similarity": "high"})


class TestEpisodeForgottenPayload:
    def test_valid_payload(self):
        p = make_episode_forgotten_payload(episode_id="ep-123", reason="max_episodes_exceeded")
        assert p["episode_id"] == "ep-123"
        assert p["reason"] == "max_episodes_exceeded"

    def test_validation_passes(self):
        p = {"episode_id": "ep-x", "reason": "capacity"}
        validate_episode_forgotten(p)

    def test_missing_keys(self):
        with pytest.raises(ValueError, match="episode_forgotten missing"):
            validate_episode_forgotten({"reason": "capacity"})

    def test_non_string_id(self):
        with pytest.raises(ValueError, match="episode_id must be str"):
            validate_episode_forgotten({"episode_id": 123, "reason": "capacity"})
