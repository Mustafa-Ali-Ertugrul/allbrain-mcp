from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.value_alignment.events import validate_alignment_failed
from allbrain.value_alignment.model import VALUE_ALIGNMENT_TEMPLATE_VERSION


class ValueAlignmentReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._failures: list[dict[str, Any]] = []
        self._total_failures: int = 0

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
        if et == EventType.ALIGNMENT_FAILED.value:
            try:
                validate_alignment_failed(payload)
            except ValueError:
                return
            self._failures.append(payload)
            self._total_failures += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "failures": list(self._failures),
            "total_failures": self._total_failures,
            "version": VALUE_ALIGNMENT_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
