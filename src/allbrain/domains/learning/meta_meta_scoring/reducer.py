from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.domains.learning.meta_meta_scoring.events import validate_evaluator_profile_updated
from allbrain.domains.learning.meta_meta_scoring.model import META_META_SCORING_TEMPLATE_VERSION


class MetaMetaScoringReducer:
    """Event-driven reducer for meta-meta scoring."""

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

        if et == EventType.EVALUATOR_PROFILE_UPDATED.value:
            try:
                validate_evaluator_profile_updated(payload)
            except ValueError:
                return
            key = f"{payload.get('evaluator_id', '')}::{payload.get('fault_type', '')}"
            self._profiles[key] = dict(payload)
            self._total_updates += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "profiles": dict(self._profiles),
            "total_updates": self._total_updates,
            "version": META_META_SCORING_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
