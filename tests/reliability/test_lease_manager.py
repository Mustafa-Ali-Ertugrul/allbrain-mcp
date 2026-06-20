from __future__ import annotations

from datetime import datetime, timedelta, timezone

from allbrain.reliability import HeartbeatTracker, LeaseManager


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def test_lease_acquire_renew_release_and_expire_are_deterministic() -> None:
    clock = Clock()
    manager = LeaseManager(clock=clock, default_ttl_seconds=10)

    lease = manager.acquire("task:n1", "worker-a")
    assert lease.state == "active"
    clock.advance(5)
    renewed = manager.renew("task:n1")
    assert renewed.expires_at == clock.now + timedelta(seconds=10)
    manager.release("task:n1")
    assert manager.leases["task:n1"].state == "released"

    manager.acquire("task:n2", "worker-a")
    clock.advance(11)
    expired = manager.expire_due()
    assert [lease.resource_id for lease in expired] == ["task:n2"]


def test_heartbeat_tracker_marks_stale_workers() -> None:
    clock = Clock()
    tracker = HeartbeatTracker(clock=clock)
    tracker.start("worker-a")

    clock.advance(31)

    stale = tracker.stale_workers(stale_after_seconds=30)
    assert stale[0].worker_id == "worker-a"
    assert stale[0].status == "stale"
