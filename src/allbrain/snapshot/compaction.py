from __future__ import annotations

from allbrain.snapshot.engine import Snapshot


class SnapshotCompactor:
    def __init__(self, snapshot_repo):
        self.snapshot_repo = snapshot_repo

    def compact_latest(self, project_id: int) -> Snapshot | None:
        latest = self.snapshot_repo.get_latest(project_id)
        if latest is None:
            return None
        metadata = dict(latest.metadata)
        metadata["compacted_from_snapshot_id"] = latest.id
        return self.snapshot_repo.save(
            project_id=project_id,
            event_cursor=latest.event_cursor,
            state=latest.state,
            metadata=metadata,
        )
