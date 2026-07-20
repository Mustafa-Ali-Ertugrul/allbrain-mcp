from __future__ import annotations

from typing import Any

from allbrain.domains.reasoning.tradeoff_engine.events import validate_tradeoff_analyzed, validate_utility_computed
from allbrain.domains.reasoning.tradeoff_engine.model import TRADEOFF_ENGINE_TEMPLATE_VERSION
from allbrain.events.schemas import EventType


class TradeoffReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._tradeoffs: list[dict[str, Any]] = []
        self._utilities: list[dict[str, Any]] = []
        self._total_tradeoffs: int = 0
        self._total_utilities: int = 0

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
        if et == EventType.TRADEOFF_ANALYZED.value:
            try:
                validate_tradeoff_analyzed(payload)
            except ValueError:
                return
            self._tradeoffs.append(payload)
            self._total_tradeoffs += 1
        elif et == EventType.UTILITY_COMPUTED.value:
            try:
                validate_utility_computed(payload)
            except ValueError:
                return
            self._utilities.append(payload)
            self._total_utilities += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "tradeoffs": list(self._tradeoffs),
            "utilities": list(self._utilities),
            "total_tradeoffs": self._total_tradeoffs,
            "total_utilities": self._total_utilities,
            "version": TRADEOFF_ENGINE_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}

