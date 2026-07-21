from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.domains.governance.policy_competition.events import validate_competition_held
from allbrain.domains.governance.policy_competition.model import POLICY_COMPETITION_TEMPLATE_VERSION


class PolicyCompetitionReducer:
    """Event-driven reducer for policy competition.

    Tracks competition rounds, winners, and confidence.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._competitions: list[dict[str, Any]] = []
        self._total_competitions: int = 0

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

        if et == EventType.COMPETITION_HELD.value:
            try:
                validate_competition_held(payload)
            except ValueError:
                return
            self._competitions.append(payload)
            self._total_competitions += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "competitions": list(self._competitions),
            "total_competitions": self._total_competitions,
            "version": POLICY_COMPETITION_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
