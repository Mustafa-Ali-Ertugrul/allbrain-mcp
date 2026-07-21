from __future__ import annotations

from typing import Any

from allbrain.domains.learning.capabilities.model import CapabilityState
from allbrain.domains.learning.capabilities.scorer import _stable_capability_id
from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort


class CapabilityManager:
    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        agent_id: str = "default",
        analysis_id: str | None = None,
    ) -> CapabilityState:
        ordered = canonical_event_sort(events)
        all_eids = {str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")}

        matches: list[tuple[float, str]] = []
        task_type = ""

        for event in ordered:
            et = str(getattr(event, "type", ""))
            if et != EventType.CAPABILITY_MATCHED.value:
                continue
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("agent_id") != agent_id:
                continue
            ms = payload.get("match_score")
            mk = payload.get("match_kind", "none")
            if isinstance(ms, (int, float)):
                matches.append((float(ms), str(mk)))
                tt = payload.get("task_type")
                if isinstance(tt, str):
                    task_type = str(tt)

        evidence = sorted(all_eids)

        if not matches:
            return CapabilityState(
                agent_id=agent_id,
                capability_count=0,
                task_type=task_type,
                match_score=0.0,
                match_kind="none",
                analysis_id=analysis_id or _stable_capability_id(agent_id, evidence),
            )
        best_score = max(s[0] for s in matches)
        best_kind = next((s[1] for s in matches if s[0] == best_score), "none")
        return CapabilityState(
            agent_id=agent_id,
            capability_count=len(matches),
            task_type=task_type,
            match_score=best_score,
            match_kind=best_kind,
            analysis_id=analysis_id or _stable_capability_id(agent_id, evidence),
        )

    def known_agent_ids(self, events: list[Any]) -> set[str]:
        ids: set[str] = set()
        for event in events:
            if str(getattr(event, "type", "")) != EventType.CAPABILITY_MATCHED.value:
                continue
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                aid = payload.get("agent_id")
                if isinstance(aid, str) and aid:
                    ids.add(aid)
        return ids
