from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort
from allbrain.routing.model import RoutingState
from allbrain.routing.scorer import _stable_routing_id


class RoutingManager:
    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        task_type: str = "default",
        analysis_id: str | None = None,
    ) -> RoutingState:
        ordered = canonical_event_sort(events)
        all_eids = {str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")}

        scored: dict[str, float] = {}
        selected = None

        for event in ordered:
            et = str(getattr(event, "type", ""))
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            pk = payload.get("task_type")
            if not isinstance(pk, str) or pk != task_type:
                continue

            if et == EventType.AGENT_SELECTION_SCORED.value:
                aid = payload.get("agent_id")
                ss = payload.get("selection_score")
                if isinstance(aid, str) and isinstance(ss, (int, float)):
                    scored[str(aid)] = float(ss)
            elif et == EventType.AGENT_SELECTED.value:
                aid = payload.get("agent_id")
                ss = payload.get("selection_score")
                if isinstance(aid, str) and isinstance(ss, (int, float)):
                    selected = {"agent_id": aid, "score": float(ss)}

        evidence = sorted(all_eids)

        if selected is not None:
            return RoutingState(
                task_type=task_type,
                selected_agent=selected["agent_id"],
                selection_score=float(selected["score"]),
                candidate_count=len(scored),
                analysis_id=analysis_id or _stable_routing_id(task_type, evidence),
            )
        return RoutingState(
            task_type=task_type,
            selected_agent=None,
            selection_score=0.0,
            candidate_count=len(scored),
            analysis_id=analysis_id or _stable_routing_id(task_type, evidence),
        )

    def known_task_types(self, events: list[Any]) -> set[str]:
        types: set[str] = set()
        for event in events:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                tt = payload.get("task_type")
                if isinstance(tt, str) and tt:
                    types.add(tt)
        return types