from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.routing.events import validate_selected, validate_scored
from allbrain.routing.model import RoutingState
from allbrain.routing.scorer import _stable_routing_id


class RoutingReducer:
    def __init__(self) -> None:
        self._types: dict[str, dict[str, Any]] = {}
        self._seen_ids: set[str] = set()

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

        if et == EventType.AGENT_SELECTION_SCORED.value:
            try:
                validate_scored(payload)
            except ValueError:
                return
            tt = str(payload["task_type"])
            aid = str(payload["agent_id"])
            ctx = self._types.setdefault(tt, {"scored": {}, "selected": None})
            ctx["scored"][aid] = float(payload["selection_score"])
            return

        if et == EventType.AGENT_SELECTED.value:
            try:
                validate_selected(payload)
            except ValueError:
                return
            tt = str(payload["task_type"])
            ctx = self._types.setdefault(tt, {"scored": {}, "selected": None})
            ctx["selected"] = {
                "agent_id": payload["agent_id"],
                "score": float(payload["selection_score"]),
            }
            return

    def snapshot(self, *, task_type: str = "default") -> RoutingState:
        ctx = self._types.get(task_type, {"scored": {}, "selected": None})
        evidence = sorted(self._seen_ids)
        sel = ctx["selected"]
        if sel is not None:
            return RoutingState(
                task_type=task_type,
                selected_agent=sel["agent_id"],
                selection_score=float(sel["score"]),
                candidate_count=len(ctx["scored"]),
                analysis_id=_stable_routing_id(task_type, evidence),
            )
        return RoutingState(
            task_type=task_type,
            selected_agent=None,
            selection_score=0.0,
            candidate_count=len(ctx["scored"]),
            analysis_id=_stable_routing_id(task_type, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            tt: {
                "task_type": s.task_type,
                "selected_agent": s.selected_agent,
                "selection_score": s.selection_score,
                "candidate_count": s.candidate_count,
                "analysis_id": s.analysis_id,
                "template_version": s.template_version,
            }
            for tt, s in ((k, self.snapshot(task_type=k)) for k in self._types)
        }

    def known_task_types(self) -> set[str]:
        return set(self._types.keys())