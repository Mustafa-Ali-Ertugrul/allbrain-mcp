from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.domains.governance.soft_repair.events import validate_policy_blended
from allbrain.domains.governance.soft_repair.model import SOFT_REPAIR_TEMPLATE_VERSION


class SoftRepairReducer:
    """Event-driven reducer for soft repair.

    Tracks policy blend operations.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._blends: list[dict[str, Any]] = []
        self._total_blends: int = 0

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

        if et == EventType.POLICY_BLENDED.value:
            try:
                validate_policy_blended(payload)
            except ValueError:
                return
            self._blends.append(payload)
            self._total_blends += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "blends": list(self._blends),
            "total_blends": self._total_blends,
            "version": SOFT_REPAIR_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
