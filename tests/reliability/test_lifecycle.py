from __future__ import annotations

from allbrain.domains.governance.reliability import ResourceTracker, ShutdownManager


class SyncResource:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class AsyncResource:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


async def test_resource_tracker_closes_sync_and_async_resources_once() -> None:
    tracker = ResourceTracker()
    sync = tracker.register(SyncResource())
    async_resource = tracker.register(AsyncResource())

    closed = await tracker.close_all()

    assert sync.closed
    assert async_resource.closed
    assert closed == ["AsyncResource", "SyncResource"]


async def test_shutdown_manager_stops_accepting_work_and_closes_resources() -> None:
    manager = ShutdownManager()
    resource = manager.register(SyncResource())

    result = await manager.shutdown()

    assert result["accepting_work"] is False
    assert resource.closed
