from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select
from uuid6 import uuid7

from allbrain.agents.queue import QueueItem, TaskQueue
from allbrain.models.entities import QueueItemRecord, WorkerLeaseRecord, utc_now
from allbrain.reliability.idempotency import IdempotencyKeyBuilder
from allbrain.workflow.models import SubtaskResult, TaskNode


class SQLiteTaskQueue(TaskQueue):
    def __init__(
        self,
        engine: Engine,
        *,
        worker_id: str = "sqlite-worker",
        lease_ttl_seconds: int = 60,
        max_attempts: int = 3,
    ) -> None:
        self.engine = engine
        self.worker_id = worker_id
        self.lease_ttl_seconds = lease_ttl_seconds
        self.max_attempts = max_attempts
        self._key_builder = IdempotencyKeyBuilder()

    async def enqueue(self, item: QueueItem) -> None:
        key = item.metadata.get("idempotency_key") or self._key_builder.queue_item_key(item)
        with open_session(self.engine) as db:
            existing = db.exec(select(QueueItemRecord).where(QueueItemRecord.idempotency_key == key)).first()
            if existing is not None and existing.state in {"queued", "leased", "completed"}:
                existing.updated_at = utc_now()
                db.add(existing)
                db.commit()
                return
            record = QueueItemRecord(
                id=str(uuid7()),
                idempotency_key=key,
                workflow_id=item.workflow_id,
                task_id=item.node.task_id,
                node_id=item.node.node_id,
                agent_id=item.agent_id,
                state="queued",
                payload_json=json.dumps(_serialize_item(item), ensure_ascii=True, sort_keys=True),
            )
            db.add(record)
            db.commit()

    async def dequeue(self, timeout: float | None = None) -> QueueItem | None:
        deadline = None if timeout is None else _now() + timedelta(seconds=timeout)
        while True:
            item = self._dequeue_once()
            if item is not None or timeout is None:
                return item
            if deadline is not None and _now() >= deadline:
                return None
            await asyncio.sleep(0.05)

    def _dequeue_once(self) -> QueueItem | None:
        now = utc_now()
        with open_session(self.engine) as db:
            expired = db.exec(
                select(QueueItemRecord).where(
                    QueueItemRecord.state == "leased",
                    col(QueueItemRecord.lease_expires_at) <= now,
                    QueueItemRecord.attempts < self.max_attempts,
                )
            ).all()
            for record in expired:
                record.state = "queued"
                record.lease_id = None
                record.leased_by = None
                record.lease_expires_at = None
                record.updated_at = now
                db.add(record)
            db.commit()

            record = db.exec(
                select(QueueItemRecord)
                .where(QueueItemRecord.state == "queued", QueueItemRecord.attempts < self.max_attempts)
                .order_by(col(QueueItemRecord.created_at), col(QueueItemRecord.id))
                .limit(1)
            ).first()
            if record is None:
                return None
            lease_id = str(uuid7())
            expires_at = now + timedelta(seconds=self.lease_ttl_seconds)
            record.state = "leased"
            record.attempts += 1
            record.lease_id = lease_id
            record.leased_by = self.worker_id
            record.lease_expires_at = expires_at
            record.updated_at = now
            db.add(record)
            db.add(
                WorkerLeaseRecord(
                    id=lease_id,
                    queue_item_id=record.id,
                    worker_id=self.worker_id,
                    expires_at=expires_at,
                )
            )
            db.commit()
            item = _deserialize_item(json.loads(record.payload_json))
            item.metadata["queue_record_id"] = record.id
            item.metadata["lease_id"] = lease_id
            item.metadata["attempts"] = record.attempts
            return item

    async def ack(self, item: QueueItem) -> None:
        record_id = item.metadata.get("queue_record_id")
        if not isinstance(record_id, str):
            return
        with open_session(self.engine) as db:
            record = db.get(QueueItemRecord, record_id)
            if record is None:
                return
            record.state = "completed"
            record.updated_at = utc_now()
            db.add(record)
            if record.lease_id:
                lease = db.get(WorkerLeaseRecord, record.lease_id)
                if lease is not None:
                    lease.state = "released"
                    lease.released_at = utc_now()
                    db.add(lease)
            db.commit()

    async def nack(self, item: QueueItem, *, requeue: bool = True, reason: str | None = None) -> None:
        record_id = item.metadata.get("queue_record_id")
        if not isinstance(record_id, str):
            return
        with open_session(self.engine) as db:
            record = db.get(QueueItemRecord, record_id)
            if record is None:
                return
            record.state = "queued" if requeue and record.attempts < self.max_attempts else "failed"
            record.lease_id = None
            record.leased_by = None
            record.lease_expires_at = None
            record.updated_at = utc_now()
            db.add(record)
            db.commit()

    async def renew_lease(self, item: QueueItem) -> None:
        record_id = item.metadata.get("queue_record_id")
        if not isinstance(record_id, str):
            return
        expires_at = utc_now() + timedelta(seconds=self.lease_ttl_seconds)
        with open_session(self.engine) as db:
            record = db.get(QueueItemRecord, record_id)
            if record is None or record.lease_id is None:
                return
            record.lease_expires_at = expires_at
            record.updated_at = utc_now()
            lease = db.get(WorkerLeaseRecord, record.lease_id)
            if lease is not None:
                lease.renewed_at = utc_now()
                lease.expires_at = expires_at
                db.add(lease)
            db.add(record)
            db.commit()

    async def recover_expired(self) -> int:
        now = utc_now()
        recovered = 0
        with open_session(self.engine) as db:
            records = db.exec(
                select(QueueItemRecord).where(
                    QueueItemRecord.state == "leased",
                    col(QueueItemRecord.lease_expires_at) <= now,
                    QueueItemRecord.attempts < self.max_attempts,
                )
            ).all()
            for record in records:
                record.state = "queued"
                record.lease_id = None
                record.leased_by = None
                record.lease_expires_at = None
                record.updated_at = now
                db.add(record)
                recovered += 1
            db.commit()
        return recovered

    def qsize(self) -> int:
        with open_session(self.engine) as db:
            return len(db.exec(select(QueueItemRecord).where(QueueItemRecord.state == "queued")).all())

    def empty(self) -> bool:
        return self.qsize() == 0

    def capabilities(self) -> dict[str, Any]:
        return {"backend": "sqlite", "persistent": True, "lease_aware": True, "distributed_ready": False}


def _serialize_item(item: QueueItem) -> dict[str, Any]:
    return {
        "node": item.node.to_dict(),
        "agent_id": item.agent_id,
        "workflow_id": item.workflow_id,
        "enqueued_at": item.enqueued_at.isoformat(),
        "parent_results": {key: value.to_dict() for key, value in item.parent_results.items()},
        "metadata": dict(item.metadata),
    }


def _deserialize_item(data: dict[str, Any]) -> QueueItem:
    return QueueItem(
        node=TaskNode.from_dict(data["node"]),
        agent_id=data["agent_id"],
        workflow_id=data["workflow_id"],
        enqueued_at=datetime.fromisoformat(data["enqueued_at"]),
        parent_results={key: SubtaskResult.from_dict(value) for key, value in data.get("parent_results", {}).items()},
        metadata=dict(data.get("metadata", {})),
    )


def _now() -> datetime:
    return datetime.now(UTC)


@contextmanager
def open_session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session
