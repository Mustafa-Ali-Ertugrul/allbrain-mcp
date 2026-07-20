from __future__ import annotations

from typing import Any

from allbrain.domains.reasoning.objective_system.events import (
    validate_objective_rebalanced,
    validate_objective_updated,
)
from allbrain.domains.reasoning.objective_system.model import OBJECTIVE_SYSTEM_TEMPLATE_VERSION
from allbrain.events.schemas import EventType


class ObjectiveSystemReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._objectives: list[dict[str, Any]] = []
        self._rebalances: list[dict[str, Any]] = []
        self._total_objectives: int = 0
        self._total_rebalances: int = 0

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
        if et == EventType.OBJECTIVE_UPDATED.value:
            try:
                validate_objective_updated(payload)
            except ValueError:
                return
            self._objectives.append(payload)
            self._total_objectives += 1
        elif et == EventType.OBJECTIVE_REBALANCED.value:
            try:
                validate_objective_rebalanced(payload)
            except ValueError:
                return
            self._rebalances.append(payload)
            self._total_rebalances += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "objectives": list(self._objectives),
            "rebalances": list(self._rebalances),
            "total_objectives": self._total_objectives,
            "total_rebalances": self._total_rebalances,
            "version": OBJECTIVE_SYSTEM_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}

