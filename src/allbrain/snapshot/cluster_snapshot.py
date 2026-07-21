from __future__ import annotations

from typing import Any

from allbrain.domains.collaboration.distributed import WorkerRegistry
from allbrain.models.schemas import EventRead


class ClusterSnapshotBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        registry = WorkerRegistry()
        for event in events:
            if event.type == "worker_registered":
                worker_id = event.payload.get("worker_id")
                node_id = event.payload.get("node_id") or "unknown"
                if isinstance(worker_id, str):
                    registry.register(
                        worker_id,
                        node_id=str(node_id),
                        capabilities=dict(event.payload.get("capabilities") or {}),
                        metadata=dict(event.payload.get("metadata") or {}),
                    )
            elif event.type == "worker_heartbeat":
                worker_id = event.payload.get("worker_id")
                if isinstance(worker_id, str) and worker_id in registry.workers:
                    registry.heartbeat(worker_id, now=event.created_at)
        return {
            "kind": "cluster_snapshot",
            "event_cursor": events[-1].id if events else None,
            "workers": registry.discover(include_stale=True),
            "event_count": len(events),
        }
