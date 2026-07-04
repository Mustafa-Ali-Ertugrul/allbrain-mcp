from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

Clock = Callable[[], datetime]


def utc_clock() -> datetime:
    return datetime.now(UTC)


@dataclass
class WorkerHeartbeat:
    worker_id: str
    started_at: datetime
    last_seen_at: datetime
    status: str = "active"

    def to_dict(self) -> dict[str, str]:
        return {
            "worker_id": self.worker_id,
            "started_at": self.started_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
            "status": self.status,
        }


@dataclass
class HeartbeatTracker:
    clock: Clock = utc_clock
    heartbeats: dict[str, WorkerHeartbeat] = field(default_factory=dict)

    def start(self, worker_id: str) -> WorkerHeartbeat:
        now = self.clock()
        heartbeat = WorkerHeartbeat(worker_id=worker_id, started_at=now, last_seen_at=now)
        self.heartbeats[worker_id] = heartbeat
        return heartbeat

    def beat(self, worker_id: str) -> WorkerHeartbeat:
        heartbeat = self.heartbeats.get(worker_id) or self.start(worker_id)
        heartbeat.last_seen_at = self.clock()
        heartbeat.status = "active"
        return heartbeat

    def stale_workers(self, *, stale_after_seconds: int = 30) -> list[WorkerHeartbeat]:
        cutoff = self.clock() - timedelta(seconds=stale_after_seconds)
        stale: list[WorkerHeartbeat] = []
        for heartbeat in self.heartbeats.values():
            if heartbeat.status == "active" and heartbeat.last_seen_at <= cutoff:
                heartbeat.status = "stale"
                stale.append(heartbeat)
        return stale
