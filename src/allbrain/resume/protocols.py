from __future__ import annotations

from typing import Any, Protocol

from allbrain.models.schemas import EventRead


class SnapshotLike(Protocol):
    event_cursor: str | None
    metadata: dict[str, Any]
    state: dict[str, Any]


class EventRepository(Protocol):
    def list_events(
        self,
        *,
        project_path: str,
        limit: int = 50,
    ) -> list[EventRead]: ...

    def list_events_after(
        self,
        *,
        project_path: str,
        event_cursor: str | None,
    ) -> list[EventRead]: ...


class SnapshotStore(Protocol):
    def get_latest(self, project_id: int) -> SnapshotLike | None: ...
