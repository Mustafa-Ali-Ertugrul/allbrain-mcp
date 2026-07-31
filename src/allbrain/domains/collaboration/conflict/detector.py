from __future__ import annotations

from collections import defaultdict
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


def _conflict_key(event: EventRead) -> str:
    """Derive a bucketing key for conflict detection.

    L1 (file-level) conflicts are grouped by file_path.
    L2 (task-level) conflicts are grouped by task hint / task payload.
    Falls back to the event id when neither is available.
    """
    file_path = event.file_path or event.payload.get("file_path") or event.payload.get("file")
    if file_path:
        return f"file:{file_path}"
    task = event.payload.get("task") or event.task_hint
    if task:
        return f"task:{task}"
    return f"id:{event.id}"


class ConflictDetector:
    def __init__(self, scorer: ConflictScorer | None = None):
        self.scorer = scorer or ConflictScorer()

    def detect(self, events: list[EventRead], threshold: float = 0.7) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        # Bucket candidates by file/task key so we only compare events that
        # share a file or task (the only pairs that can conflict).
        buckets: dict[str, list[EventRead]] = defaultdict(list)
        for event in events:
            if event.type not in CONFLICT_EVENT_TYPES:
                continue
            if (event.agent_id or "unknown") == "allbrain":
                continue
            key = _conflict_key(event)
            buckets[key].append(event)
        for bucket in buckets.values():
            for index, a in enumerate(bucket):
                for b in bucket[index + 1 :]:
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
