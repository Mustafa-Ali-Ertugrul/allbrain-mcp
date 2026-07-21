from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.domains.learning.meta_optimizer.events import validate_weights_adapated
from allbrain.domains.learning.meta_optimizer.model import META_OPTIMIZER_TEMPLATE_VERSION


class MetaOptimizerReducer:
    """Event-driven reducer for meta optimizer.

    Tracks weight adaptation events per fault_type.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._adaptations: list[dict[str, Any]] = []
        self._total_adaptations: int = 0
        self._guards: int = 0

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

        if et == EventType.WEIGHTS_ADAPTED.value:
            try:
                validate_weights_adapated(payload)
            except ValueError:
                return
            self._adaptations.append(payload)
            self._total_adaptations += 1
        elif et == EventType.META_OPTIMIZER_GUARDED.value:
            self._guards += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "adaptations": list(self._adaptations),
            "total_adaptations": self._total_adaptations,
            "total_guards": self._guards,
            "version": META_OPTIMIZER_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
