from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.meta_scoring.events import validate_scoring_profile_updated
from allbrain.meta_scoring.model import META_SCORING_TEMPLATE_VERSION


class MetaScoringReducer:
    """Event-driven reducer for meta scoring.

    Tracks profile updates per fault_type.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._profiles: dict[str, dict[str, Any]] = {}
        self._total_updates: int = 0

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

        if et == EventType.SCORING_PROFILE_UPDATED.value:
            try:
                validate_scoring_profile_updated(payload)
            except ValueError:
                return
            ft = str(payload.get("fault_type", ""))
            self._profiles[ft] = dict(payload)
            self._total_updates += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "profiles": dict(self._profiles),
            "total_updates": self._total_updates,
            "version": META_SCORING_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
