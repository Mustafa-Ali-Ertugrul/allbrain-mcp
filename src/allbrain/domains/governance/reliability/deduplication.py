from __future__ import annotations

from dataclasses import dataclass, field

from allbrain.domains.collaboration.agents.queue import QueueItem
from allbrain.models.schemas import EventRead
from allbrain.domains.governance.reliability.idempotency import IdempotencyKeyBuilder


@dataclass
class DuplicateDecision:
    duplicate: bool
    idempotency_key: str
    reason: str | None = None


@dataclass
class Deduplicator:
    seen_keys: set[str] = field(default_factory=set)
    key_builder: IdempotencyKeyBuilder = field(default_factory=IdempotencyKeyBuilder)

    def record(self, key: str) -> DuplicateDecision:
        if key in self.seen_keys:
            return DuplicateDecision(True, key, "duplicate_key")
        self.seen_keys.add(key)
        return DuplicateDecision(False, key)

    def task_execution(self, task_id: str, node_id: str | None = None) -> DuplicateDecision:
        return self.record(self.key_builder.task_key(task_id, node_id))

    def workflow_execution(self, workflow_id: str) -> DuplicateDecision:
        return self.record(self.key_builder.workflow_key(workflow_id))

    def queue_item(self, item: QueueItem) -> DuplicateDecision:
        return self.record(self.key_builder.queue_item_key(item))

    def event(self, event: EventRead | dict[str, object]) -> DuplicateDecision:
        return self.record(self.key_builder.event_key(event))


def decisions_from_events(events: list[EventRead]) -> dict[str, int]:
    duplicate_count = sum(1 for event in events if event.type == "duplicate_detected")
    idempotency_count = sum(1 for event in events if event.type == "idempotency_key_recorded")
    return {"duplicate_detection_count": duplicate_count, "idempotency_key_count": idempotency_count}
