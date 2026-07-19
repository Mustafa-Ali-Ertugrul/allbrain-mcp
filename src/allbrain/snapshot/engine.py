from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    project_id: int
    created_at: datetime
    event_cursor: str | None
    state: dict[str, Any]
    metadata: dict[str, Any] = {}


class SnapshotEngine:
    def __init__(self, builder, snapshot_repo):
        self.builder = builder
        self.snapshot_repo = snapshot_repo

    def build_snapshot(self, *, project_id: int, events):
        events_list = list(events)
        state, metadata = self.builder.build(events_list)
        event_cursor = events_list[-1].id if events_list else None
        return self.snapshot_repo.save(
            project_id=project_id,
            event_cursor=event_cursor,
            state=state,
            metadata=metadata,
        )
