from __future__ import annotations

from typing import Any

from allbrain.episodic.events import (
    validate_episode_created,
    validate_episode_forgotten,
    validate_episode_retrieved,
)
from allbrain.episodic.model import Episode
from allbrain.events.schemas import EventType


class EpisodicReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._episodes: list[Episode] = []
        self._total: int = 0
        self._retained: int = 0
        self._forgotten: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.EPISODE_CREATED.value:
            try:
                validate_episode_created(payload)
            except ValueError:
                return
            ep_id = str(payload["episode_id"])
            timestamp = int(payload.get("timestamp", 0))
            reward = float(payload["reward"])
            importance = float(payload["importance"])
            ws_items = tuple(payload.get("workspace_items", []))
            decision_id = str(payload.get("decision_id", ""))
            episode = Episode(
                episode_id=ep_id,
                timestamp=timestamp,
                reward=reward,
                importance=importance,
                workspace_items=ws_items,
                decision_id=decision_id,
            )
            self._episodes.append(episode)
            self._total += 1
            self._retained += 1

        elif et == EventType.EPISODE_RETRIEVED.value:
            try:
                validate_episode_retrieved(payload)
            except ValueError:
                return
            # Retrieval events are counted but don't modify the episode list

        elif et == EventType.EPISODE_FORGOTTEN.value:
            try:
                validate_episode_forgotten(payload)
            except ValueError:
                return
            ep_id = str(payload["episode_id"])
            self._episodes = [ep for ep in self._episodes if ep.episode_id != ep_id]
            self._forgotten += 1
            self._retained = len(self._episodes)

    def snapshot(self) -> dict[str, Any]:
        return {
            "episodes": list(self._episodes),
            "total": self._total,
            "retained": self._retained,
            "forgotten": self._forgotten,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
