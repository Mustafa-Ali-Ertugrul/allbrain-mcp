from __future__ import annotations

import copy
import uuid
from typing import Any

from allbrain.domains.governance.resilience.model import MetricsSnapshot


class StateSnapshotManager:
    """Manages state checkpoints for safe rollback.

    Each snapshot stores component state along with metadata
    (timestamp, event_id, pipeline_stage) for debugging and replay.
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, MetricsSnapshot] = {}

    def create(
        self,
        component: str,
        state: dict[str, Any],
        *,
        time: int = 0,
        event_id: str = "",
        pipeline_stage: str = "",
    ) -> MetricsSnapshot:
        """Take a snapshot of a component's state at a point in time."""
        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
        snapshot = MetricsSnapshot(
            snapshot_id=snapshot_id,
            component=component,
            state=dict(state),
            created_at=time,
            event_id=event_id,
            pipeline_stage=pipeline_stage,
        )
        self._snapshots[snapshot_id] = snapshot
        return snapshot

    def restore(self, snapshot_id: str) -> dict[str, Any] | None:
        """Restore state from a snapshot. Returns None if not found."""
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            return None
        return copy.deepcopy(snap.state)

    def delete(self, snapshot_id: str) -> bool:
        """Remove a snapshot after successful recovery."""
        if snapshot_id in self._snapshots:
            del self._snapshots[snapshot_id]
            return True
        return False

    def get(self, snapshot_id: str) -> MetricsSnapshot | None:
        return self._snapshots.get(snapshot_id)

    def list_snapshots(self, component: str | None = None) -> list[MetricsSnapshot]:
        if component is None:
            return list(self._snapshots.values())
        return [s for s in self._snapshots.values() if s.component == component]

    def clear(self) -> None:
        self._snapshots.clear()

    @property
    def count(self) -> int:
        return len(self._snapshots)
