from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from uuid6 import uuid7

from allbrain.reliability.worker_heartbeat import utc_clock


Clock = Callable[[], datetime]


@dataclass
class Lease:
    lease_id: str
    resource_id: str
    worker_id: str
    acquired_at: datetime
    renewed_at: datetime
    expires_at: datetime
    state: str = "active"

    def to_dict(self) -> dict[str, str]:
        return {
            "lease_id": self.lease_id,
            "resource_id": self.resource_id,
            "worker_id": self.worker_id,
            "acquired_at": self.acquired_at.isoformat(),
            "renewed_at": self.renewed_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "state": self.state,
        }


@dataclass
class LeaseManager:
    clock: Clock = utc_clock
    default_ttl_seconds: int = 60
    leases: dict[str, Lease] = field(default_factory=dict)

    def acquire(self, resource_id: str, worker_id: str, *, ttl_seconds: int | None = None) -> Lease:
        existing = self.leases.get(resource_id)
        if existing and existing.state == "active" and existing.expires_at > self.clock():
            raise RuntimeError(f"resource {resource_id} already leased")
        now = self.clock()
        lease = Lease(
            lease_id=str(uuid7()),
            resource_id=resource_id,
            worker_id=worker_id,
            acquired_at=now,
            renewed_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds or self.default_ttl_seconds),
        )
        self.leases[resource_id] = lease
        return lease

    def renew(self, resource_id: str, *, ttl_seconds: int | None = None) -> Lease:
        lease = self._active(resource_id)
        now = self.clock()
        lease.renewed_at = now
        lease.expires_at = now + timedelta(seconds=ttl_seconds or self.default_ttl_seconds)
        return lease

    def release(self, resource_id: str) -> Lease:
        lease = self._active(resource_id)
        lease.state = "released"
        return lease

    def expire_due(self) -> list[Lease]:
        now = self.clock()
        expired: list[Lease] = []
        for lease in self.leases.values():
            if lease.state == "active" and lease.expires_at <= now:
                lease.state = "expired"
                expired.append(lease)
        return expired

    def _active(self, resource_id: str) -> Lease:
        lease = self.leases.get(resource_id)
        if lease is None or lease.state != "active":
            raise RuntimeError(f"resource {resource_id} has no active lease")
        return lease
