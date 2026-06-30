from __future__ import annotations

import uuid
from typing import Any

from allbrain.episodic.consolidation import should_store_episode
from allbrain.episodic.importance import compute_importance, compute_novelty
from allbrain.episodic.model import (
    DEFAULT_RETRIEVAL_LIMIT,
    MAX_EPISODES,
    NOVELTY_SAMPLE_WINDOW,
    Episode,
)
from allbrain.episodic.retrieval import retrieve_similar

EVICTION_REASON_CAPACITY = "max_episodes_exceeded"


class EpisodicManager:
    def __init__(self) -> None:
        self._episodes: list[Episode] = []
        self._total: int = 0
        self._retained: int = 0
        self._forgotten: int = 0
        self._time: int = 0

    def store_episode(
        self,
        *,
        reward: float,
        workspace_items: list[str],
        decision_id: str,
        activation: float = 0.5,
    ) -> dict[str, Any]:
        """Attempt to store an episode.

        Steps:
          1. compute_novelty (from recent similar episodes)
          2. compute_importance (reward × activation × novelty)
          3. should_store_episode (importance threshold + extreme rewards)
          4. If stored: append, track counts, emit EPISODE_CREATED
          5. If over MAX_EPISODES: FIFO eviction
          6. Return store result
        """
        self._time += 1

        recent = list(self._episodes)
        novelty = compute_novelty(
            workspace_items,
            recent,
            sample_window=NOVELTY_SAMPLE_WINDOW,
        )

        importance = compute_importance(
            reward=reward,
            workspace_activation=activation,
            novelty=novelty,
        )

        if not should_store_episode(reward=reward, importance=importance):
            return {
                "stored": False,
                "importance": importance,
                "novelty": novelty,
                "reason": "below_threshold",
            }

        episode_id = f"ep-{uuid.uuid4().hex[:12]}"

        episode = Episode(
            episode_id=episode_id,
            timestamp=self._time,
            reward=reward,
            importance=importance,
            workspace_items=tuple(workspace_items),
            decision_id=decision_id,
            retrieval_count=0,
            last_retrieved=None,
        )
        self._episodes.append(episode)
        self._total += 1
        self._retained = len(self._episodes)

        forgotten: list[dict[str, Any]] = []
        while len(self._episodes) > MAX_EPISODES:
            removed = self._episodes.pop(0)
            self._forgotten += 1
            self._retained = len(self._episodes)
            forgotten.append({
                "episode_id": removed.episode_id,
                "reason": EVICTION_REASON_CAPACITY,
            })

        return {
            "stored": True,
            "episode_id": episode_id,
            "importance": importance,
            "novelty": novelty,
            "forgotten": forgotten,
        }

    def retrieve(
        self,
        workspace_items: list[str],
        *,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
    ) -> dict[str, Any]:
        """Retrieve similar episodes from memory.

        Returns top-K by similarity (Jaccard) sorted by importance as tie-breaker.
        Also updates retrieval_count and last_retrieved on matched episodes.
        """
        if not self._episodes:
            return {"retrieved": 0, "episodes": [], "best_similarity": 0.0}

        matched = retrieve_similar(workspace_items, self._episodes, limit=limit)

        # Update retrieval metadata on matched episodes (create new Episode objects)
        updated: list[Episode] = []
        for ep, sim in matched:
            updated.append(Episode(
                episode_id=ep.episode_id,
                timestamp=ep.timestamp,
                reward=ep.reward,
                importance=ep.importance,
                workspace_items=ep.workspace_items,
                decision_id=ep.decision_id,
                retrieval_count=ep.retrieval_count + 1,
                last_retrieved=self._time,
            ))
            # Replace in main list
            for i, old_ep in enumerate(self._episodes):
                if old_ep.episode_id == ep.episode_id:
                    self._episodes[i] = Episode(
                        episode_id=old_ep.episode_id,
                        timestamp=old_ep.timestamp,
                        reward=old_ep.reward,
                        importance=old_ep.importance,
                        workspace_items=old_ep.workspace_items,
                        decision_id=old_ep.decision_id,
                        retrieval_count=old_ep.retrieval_count + 1,
                        last_retrieved=self._time,
                    )
                    break

        best_sim = matched[0][1] if matched else 0.0
        return {
            "retrieved": len(matched),
            "episodes": [(ep.episode_id, sim) for ep, sim in matched],
            "best_similarity": best_sim,
        }

    def forget_old(self) -> dict[str, Any]:
        """FIFO trim to MAX_EPISODES.

        Note (Sprint 63): This will be replaced with importance-based forgetting.
        """
        forgotten: list[str] = []
        while len(self._episodes) > MAX_EPISODES:
            removed = self._episodes.pop(0)
            forgotten.append(removed.episode_id)
            self._forgotten += 1
        self._retained = len(self._episodes)
        return {"forgotten": forgotten}

    def stats(self) -> dict[str, Any]:
        return {
            "total": self._total,
            "retained": self._retained,
            "forgotten": self._forgotten,
            "episode_count": len(self._episodes),
        }

    def get_all_episodes(self) -> list[Episode]:
        return list(self._episodes)
