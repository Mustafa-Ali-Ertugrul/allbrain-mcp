from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.domains.learning.learning.events import validate_decayed, validate_learned, validate_observed
from allbrain.domains.learning.learning.learner import _stable_learning_id
from allbrain.domains.learning.learning.model import LearnedCapabilityState


class CapabilityLearningReducer:
    def __init__(self) -> None:
        self._pairs: dict[str, list[tuple[float, float]]] = {}
        self._seen_ids: set[str] = set()

    @staticmethod
    def _key(agent_id: str, task_type: str) -> str:
        return agent_id + "::" + task_type

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

        if et == EventType.AGENT_CAPABILITY_OBSERVED.value:
            try:
                validate_observed(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            obs = (
                (1.0 if payload["success"] else 0.0) * 0.5
                + float(payload["runtime_score"]) * 0.3
                + float(payload["selection_score"]) * 0.2
            )
            self._pairs.setdefault(k, []).append((max(0.0, min(1.0, obs)), 0.0))
            return

        if et == EventType.AGENT_CAPABILITY_LEARNED.value:
            try:
                validate_learned(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._pairs[k] = [
                (
                    float(payload["new_score"]),
                    float(payload["delta"]),
                )
            ]
            return

        if et == EventType.AGENT_CAPABILITY_DECAYED.value:
            try:
                validate_decayed(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            score = float(payload["new_score"])
            delta = float(payload["new_score"]) - float(payload["old_score"])
            self._pairs[k] = [(score, delta)]
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> LearnedCapabilityState:
        k = self._key(agent_id, task_type)
        rows = self._pairs.get(k, [])
        evidence = sorted(self._seen_ids)
        if not rows:
            return LearnedCapabilityState(
                agent_id=agent_id,
                task_type=task_type,
                observation_count=0,
                capability_score=0.0,
                last_delta=0.0,
                analysis_id=_stable_learning_id(k, evidence),
            )
        last_score, last_delta = rows[-1]
        return LearnedCapabilityState(
            agent_id=agent_id,
            task_type=task_type,
            observation_count=len(rows),
            capability_score=max(0.0, min(1.0, last_score)),
            last_delta=max(0.0, min(1.0, last_delta)),
            analysis_id=_stable_learning_id(k, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            k: {
                "agent_id": s.agent_id,
                "task_type": s.task_type,
                "observation_count": s.observation_count,
                "capability_score": s.capability_score,
                "last_delta": s.last_delta,
                "analysis_id": s.analysis_id,
                "template_version": s.template_version,
            }
            for k, s in (
                (
                    kk,
                    self.snapshot(
                        agent_id=kk.split("::", 1)[0],
                        task_type=kk.split("::", 1)[1],
                    ),
                )
                for kk in self._pairs
            )
        }

    def known_keys(self) -> set[str]:
        return set(self._pairs.keys())
