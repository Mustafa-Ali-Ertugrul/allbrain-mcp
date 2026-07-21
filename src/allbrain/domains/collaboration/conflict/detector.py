from __future__ import annotations

from typing import Any

from allbrain.domains.collaboration.conflict.scoring import ConflictScorer
from allbrain.events import EventType
from allbrain.models.schemas import EventRead

CONFLICT_EVENT_TYPES = {
    EventType.FILE_MODIFIED.value,
    EventType.TASK_STARTED.value,
    EventType.TASK_COMPLETED.value,
    EventType.TASK_BLOCKED.value,
}


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
