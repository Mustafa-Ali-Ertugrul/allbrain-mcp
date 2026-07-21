from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.domains.learning.learning.learner import _stable_learning_id
from allbrain.domains.learning.learning.model import LearnedCapabilityState


class CapabilityLearningManager:
    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        agent_id: str = "default",
        task_type: str = "default",
        analysis_id: str | None = None,
    ) -> LearnedCapabilityState:
        ordered = canonical_event_sort(events)
        all_eids = {str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")}

        score = 0.0
        delta = 0.0
        count = 0

        for event in ordered:
            et = str(getattr(event, "type", ""))
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            pk_aid = payload.get("agent_id")
            pk_tt = payload.get("task_type")
            if not isinstance(pk_aid, str) or pk_aid != agent_id:
                continue
            if not isinstance(pk_tt, str) or pk_tt != task_type:
                continue

            if et == EventType.AGENT_CAPABILITY_OBSERVED.value:
                count += 1
            elif et == EventType.AGENT_CAPABILITY_LEARNED.value:
                ns = payload.get("new_score")
                d = payload.get("delta")
                if isinstance(ns, (int, float)):
                    score = max(0.0, min(1.0, float(ns)))
                if isinstance(d, (int, float)):
                    delta = max(0.0, min(1.0, float(d)))
                count = max(count, 1)
            elif et == EventType.AGENT_CAPABILITY_DECAYED.value:
                ns = payload.get("new_score")
                os_ = payload.get("old_score")
                if isinstance(ns, (int, float)) and isinstance(os_, (int, float)):
                    score = max(0.0, min(1.0, float(ns)))
                    delta = float(ns) - float(os_)
                count = max(count, 1)

        evidence = sorted(all_eids)
        k = agent_id + "::" + task_type
        return LearnedCapabilityState(
            agent_id=agent_id,
            task_type=task_type,
            observation_count=count,
            capability_score=score,
            last_delta=delta,
            analysis_id=analysis_id or _stable_learning_id(k, evidence),
        )

    def known_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                aid = payload.get("agent_id")
                tt = payload.get("task_type")
                if isinstance(aid, str) and isinstance(tt, str):
                    keys.add(str(aid) + "::" + str(tt))
        return keys
