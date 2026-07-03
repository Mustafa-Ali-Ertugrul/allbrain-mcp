from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead

CONFLICT_EVENT_TYPES = {
    EventType.FILE_MODIFIED.value,
    EventType.TASK_STARTED.value,
    EventType.TASK_COMPLETED.value,
    EventType.TASK_BLOCKED.value,
}


class ConflictScorer:
    def score(self, a: EventRead, b: EventRead) -> dict[str, Any]:
        overlap = self._overlap(a, b)
        semantic_distance = self._semantic_distance(a, b)
        time_decay = self._time_decay(a.created_at, b.created_at)
        agent_difference = 1.0 if (a.agent_id or "unknown") != (b.agent_id or "unknown") else 0.0
        score = (0.3 * overlap) + (0.2 * semantic_distance) + (0.35 * time_decay) + (0.15 * agent_difference)
        return {
            "score": round(score, 4),
            "overlap": round(overlap, 4),
            "semantic_distance": round(semantic_distance, 4),
            "time_decay": round(time_decay, 4),
            "agent_difference": agent_difference,
        }

    def level(self, a: EventRead, b: EventRead) -> str | None:
        if self._same_file(a, b):
            return "L1"
        if self._same_task(a, b):
            return "L2"
        return None

    def _overlap(self, a: EventRead, b: EventRead) -> float:
        if self._same_file(a, b):
            return 1.0
        if self._same_task(a, b):
            return 0.85
        return 0.0

    def _semantic_distance(self, a: EventRead, b: EventRead) -> float:
        if a.type == b.type:
            return 1.0
        if self._same_task(a, b):
            return 0.8
        if {a.type, b.type} <= {
            EventType.TASK_STARTED.value,
            EventType.TASK_COMPLETED.value,
            EventType.TASK_BLOCKED.value,
        }:
            return 0.6
        return 0.0

    def _time_decay(self, a, b) -> float:
        from datetime import datetime
        from math import exp

        if isinstance(a, datetime) and isinstance(b, datetime):
            delta_seconds = abs((b - a).total_seconds())
            return exp(-delta_seconds / 120)
        return 0.0

    def _same_file(self, a: EventRead, b: EventRead) -> bool:
        return bool(a.file_path and b.file_path and a.file_path == b.file_path)

    def _same_task(self, a: EventRead, b: EventRead) -> bool:
        task_a = a.payload.get("task") or a.task_hint
        task_b = b.payload.get("task") or b.task_hint
        return bool(isinstance(task_a, str) and task_a and task_a == task_b)


class ConflictDetector:
    def __init__(self, scorer: ConflictScorer | None = None):
        self.scorer = scorer or ConflictScorer()

    def detect(self, events: list[EventRead], threshold: float = 0.7) -> list[dict[str, Any]]:
        candidates = [
            event
            for event in events
            if event.type in CONFLICT_EVENT_TYPES and (event.agent_id or "unknown") != "allbrain"
        ]
        conflicts: list[dict[str, Any]] = []
        for index, a in enumerate(candidates):
            for b in candidates[index + 1 :]:
                if (a.agent_id or "unknown") == (b.agent_id or "unknown"):
                    continue
                level = self.scorer.level(a, b)
                if level is None:
                    continue
                score = self.scorer.score(a, b)
                if score["score"] < threshold:
                    continue
                conflicts.append(
                    {
                        "level": level,
                        "file": a.file_path if level == "L1" else None,
                        "task": (a.payload.get("task") or a.task_hint) if level == "L2" else None,
                        "agents": sorted({a.agent_id or "unknown", b.agent_id or "unknown"}),
                        "score": score["score"],
                        "signals": score,
                        "evidence_event_ids": [a.id, b.id],
                    }
                )
        return conflicts


class ConflictResolver:
    def __init__(self, decision_margin: float = 0.25):
        self.decision_margin = decision_margin

    def resolve(
        self, conflicts: list[dict[str, Any]], events: list[EventRead], agent_view: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        events_by_id = {event.id: event for event in events}
        confidence_by_agent = {agent["agent_id"]: agent["confidence_score"] for agent in agent_view}
        resolved = []
        for conflict in conflicts:
            evidence = [
                events_by_id[event_id] for event_id in conflict["evidence_event_ids"] if event_id in events_by_id
            ]
            if not evidence:
                continue
            ranked = sorted(
                evidence,
                key=lambda event: (
                    confidence_by_agent.get(event.agent_id or "unknown", 0.0),
                    event.impact_score or 0.0,
                    event.id,
                ),
                reverse=True,
            )
            winner = ranked[0]
            runner_up = ranked[1] if len(ranked) > 1 else None
            winner_confidence = confidence_by_agent.get(winner.agent_id or "unknown", 0.0)
            runner_up_confidence = confidence_by_agent.get(runner_up.agent_id or "unknown", 0.0) if runner_up else 0.0
            margin = winner_confidence - runner_up_confidence
            status = "resolved" if margin >= self.decision_margin else "needs_review"
            resolved.append(
                {
                    "conflict": conflict,
                    "status": status,
                    "winner_event_id": winner.id if status == "resolved" else None,
                    "winner_agent_id": (winner.agent_id or "unknown") if status == "resolved" else None,
                    "candidate_event_id": winner.id,
                    "candidate_agent_id": winner.agent_id or "unknown",
                    "confidence_margin": round(margin, 4),
                    "strategy": "dynamic_confidence_then_impact_then_uuidv7",
                }
            )
        return resolved
