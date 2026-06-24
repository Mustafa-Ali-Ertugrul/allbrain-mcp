from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.self_play.events import validate_match_played
from allbrain.self_play.model import SELF_PLAY_TEMPLATE_VERSION


class SelfPlayReducer:
    """Event-driven reducer for self-play matches.

    Tracks match results per fault_type.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._matches: list[dict[str, Any]] = []
        self._total_matches: int = 0

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

        if et == EventType.MATCH_PLAYED.value:
            try:
                validate_match_played(payload)
            except ValueError:
                return
            self._matches.append(payload)
            self._total_matches += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "matches": list(self._matches),
            "total_matches": self._total_matches,
            "version": SELF_PLAY_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}