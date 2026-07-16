from __future__ import annotations

import json
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from uuid6 import uuid7

from allbrain.models.entities import SnapshotRecord, utc_now
from allbrain.snapshot.engine import Snapshot
from allbrain.storage.database import open_session, open_write_session


class SnapshotRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    def save(
        self,
        *,
        project_id: int,
        event_cursor: str | None,
        state: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> Snapshot:
        record = SnapshotRecord(
            id=str(uuid7()),
            project_id=project_id,
            event_cursor=event_cursor,
            state_json=json.dumps(state, ensure_ascii=True, sort_keys=True),
            metadata_json=json.dumps(metadata or {}, ensure_ascii=True, sort_keys=True),
            created_at=utc_now(),
        )
        with open_write_session(self.engine) as db:
            db.add(record)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                existing = db.exec(
                    select(SnapshotRecord).where(
                        SnapshotRecord.project_id == project_id,
                        SnapshotRecord.event_cursor == event_cursor,
                    )
                ).first()
                if existing is None:
                    raise
                return record_to_snapshot(existing)
            db.refresh(record)
            return record_to_snapshot(record)

    def get_latest(self, project_id: int) -> Snapshot | None:
        with open_session(self.engine) as db:
            record = db.exec(
                select(SnapshotRecord)
                .where(SnapshotRecord.project_id == project_id)
                .order_by(col(SnapshotRecord.created_at).desc(), col(SnapshotRecord.id).desc())
                .limit(1)
            ).first()
            if record is None:
                return None
            return record_to_snapshot(record)


def record_to_snapshot(record: SnapshotRecord) -> Snapshot:
    return Snapshot(
        id=record.id,
        project_id=record.project_id,
        created_at=record.created_at,
        event_cursor=record.event_cursor,
        state=json.loads(record.state_json),
        metadata=json.loads(record.metadata_json),
    )
