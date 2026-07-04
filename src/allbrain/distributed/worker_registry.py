from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class WorkerRegistration:
    worker_id: str
    node_id: str
    capabilities: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=utc_now)
    last_heartbeat_at: datetime = field(default_factory=utc_now)
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "node_id": self.node_id,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat_at": self.last_heartbeat_at.isoformat(),
            "status": self.status,
        }


@dataclass
class WorkerRegistry:
    workers: dict[str, WorkerRegistration] = field(default_factory=dict)

    def register(
        self,
        worker_id: str,
        *,
        node_id: str,
        capabilities: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkerRegistration:
        registration = WorkerRegistration(
            worker_id=worker_id,
            node_id=node_id,
            capabilities=capabilities or {},
            metadata=metadata or {},
        )
        self.workers[worker_id] = registration
        return registration

    def heartbeat(self, worker_id: str, *, now: datetime | None = None) -> WorkerRegistration:
        worker = self.workers[worker_id]
        worker.last_heartbeat_at = now or utc_now()
        worker.status = "active"
        return worker

    def mark_stale(self, *, stale_after_seconds: int = 30, now: datetime | None = None) -> list[WorkerRegistration]:
        current = now or utc_now()
        cutoff = current - timedelta(seconds=stale_after_seconds)
        stale: list[WorkerRegistration] = []
        for worker in self.workers.values():
            if worker.status == "active" and worker.last_heartbeat_at <= cutoff:
                worker.status = "stale"
                stale.append(worker)
        return stale

    def discover(self, *, capability: str | None = None, include_stale: bool = False) -> list[dict[str, Any]]:
        workers = self.workers.values()
        if not include_stale:
            workers = [worker for worker in workers if worker.status == "active"]
        if capability is not None:
            workers = [worker for worker in workers if capability in worker.capabilities.get("skills", [])]
        return [worker.to_dict() for worker in sorted(workers, key=lambda item: item.worker_id)]
