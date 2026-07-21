from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.domains.governance.policy_routing.events import (
    validate_family_candidate_evaluated,
    validate_policy_family_selected,
)
from allbrain.domains.governance.policy_routing.model import POLICY_ROUTING_TEMPLATE_VERSION


class PolicyRoutingReducer:
    """Event-driven reducer for policy routing.

    Tracks family selections and candidate evaluations.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._family_selections: list[dict[str, Any]] = []
        self._candidate_evaluations: list[dict[str, Any]] = []
        self._total_selections: int = 0
        self._total_evaluations: int = 0

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

        if et == EventType.POLICY_FAMILY_SELECTED.value:
            try:
                validate_policy_family_selected(payload)
            except ValueError:
                return
            self._family_selections.append(payload)
            self._total_selections += 1

        elif et == EventType.FAMILY_CANDIDATE_EVALUATED.value:
            try:
                validate_family_candidate_evaluated(payload)
            except ValueError:
                return
            self._candidate_evaluations.append(payload)
            self._total_evaluations += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "family_selections": list(self._family_selections),
            "candidate_evaluations": list(self._candidate_evaluations),
            "total_selections": self._total_selections,
            "total_evaluations": self._total_evaluations,
            "version": POLICY_ROUTING_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
