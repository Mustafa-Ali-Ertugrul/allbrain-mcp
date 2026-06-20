from __future__ import annotations

import hashlib
import json
from typing import Any

from allbrain.agents.queue import QueueItem
from allbrain.models.schemas import EventRead


class IdempotencyKeyBuilder:
    def workflow_key(self, workflow_id: str) -> str:
        return _key("workflow", {"workflow_id": workflow_id})

    def task_key(self, task_id: str, node_id: str | None = None) -> str:
        return _key("task", {"task_id": task_id, "node_id": node_id or task_id})

    def queue_item_key(self, item: QueueItem) -> str:
        return _key(
            "queue_item",
            {
                "workflow_id": item.workflow_id,
                "task_id": item.node.task_id,
                "node_id": item.node.node_id,
                "agent_id": item.agent_id,
            },
        )

    def event_key(self, event: EventRead | dict[str, Any]) -> str:
        if isinstance(event, EventRead):
            payload = {"type": event.type, "payload": event.payload, "agent_id": event.agent_id, "caused_by": event.caused_by}
        else:
            payload = event
        return _key("event", payload)


def _key(prefix: str, payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"
