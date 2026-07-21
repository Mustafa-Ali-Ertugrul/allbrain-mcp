from __future__ import annotations

from datetime import datetime
from math import exp
from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


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

    def _time_decay(self, a: datetime, b: datetime) -> float:
        delta_seconds = abs((b - a).total_seconds())
        return exp(-delta_seconds / 120)

    def _same_file(self, a: EventRead, b: EventRead) -> bool:
        return bool(a.file_path and b.file_path and a.file_path == b.file_path)

    def _same_task(self, a: EventRead, b: EventRead) -> bool:
        task_a = a.payload.get("task") or a.task_hint
        task_b = b.payload.get("task") or b.task_hint
        return bool(isinstance(task_a, str) and task_a and task_a == task_b)
