from __future__ import annotations

from typing import Any

from allbrain.domains.learning.capabilities.events import validate_matched
from allbrain.domains.learning.capabilities.model import CapabilityState
from allbrain.domains.learning.capabilities.scorer import _stable_capability_id
from allbrain.events.schemas import EventType


class CapabilityReducer:
    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}
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

        if et == EventType.CAPABILITY_MATCHED.value:
            try:
                validate_matched(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            ctx = self._agents.setdefault(aid, {"matches": [], "task_type": ""})
            ctx["matches"].append((float(payload["match_score"]), str(payload.get("match_kind", "none"))))
            ctx["task_type"] = str(payload.get("task_type", ""))
            return

    def snapshot(self, *, agent_id: str = "default") -> CapabilityState:
        ctx = self._agents.get(agent_id, {"matches": [], "task_type": ""})
        evidence = sorted(self._seen_ids)
        matches = ctx["matches"]
        if not matches:
            return CapabilityState(
                agent_id=agent_id,
                capability_count=0,
                task_type="",
                match_score=0.0,
                match_kind="none",
                analysis_id=_stable_capability_id(agent_id, evidence),
            )
        best_score = max(s[0] for s in matches)
        best_kind = next((s[1] for s in matches if s[0] == best_score), "none")
        return CapabilityState(
            agent_id=agent_id,
            capability_count=len(matches),
            task_type=str(ctx["task_type"]),
            match_score=best_score,
            match_kind=best_kind,
            analysis_id=_stable_capability_id(agent_id, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            aid: {
                "agent_id": s.agent_id,
                "capability_count": s.capability_count,
                "task_type": s.task_type,
                "match_score": s.match_score,
                "match_kind": s.match_kind,
                "analysis_id": s.analysis_id,
                "template_version": s.template_version,
            }
            for aid, s in ((k, self.snapshot(agent_id=k)) for k in self._agents)
        }

    def known_agent_ids(self) -> set[str]:
        return set(self._agents.keys())
