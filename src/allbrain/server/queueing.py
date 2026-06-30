from __future__ import annotations

import json
from datetime import UTC, timedelta, timezone
from typing import Any

from sqlalchemy import update
from sqlmodel import col, select
from uuid6 import uuid7

from allbrain.events import EventType
from allbrain.models.entities import QueueItemRecord, WorkerLeaseRecord, utc_now
from allbrain.server.context import BrainContext
from allbrain.storage.database import open_session


class QueueCoordinator:
    """Atomic SQLite coordination for MCP-driven workflow execution."""

    def __init__(self, context: BrainContext, *, max_attempts: int = 3):
        self.context = context
        self.max_attempts = max_attempts

    def enqueue_pipeline_result(self, result: dict[str, Any]) -> dict[str, Any]:
        scheduler = result.get("scheduler") or {}
        assignment = scheduler.get("assignment") or {}
        decomposition = result.get("decomposition") or {}
        objective = result.get("objective") or {}
        task_id = str(scheduler.get("summary", {}).get("task_id") or decomposition.get("task_id") or result["run_id"])
        node_id = str(decomposition.get("node_id") or task_id)
        agent_id = str(assignment.get("agent_id") or objective.get("agent_id") or "unknown")
        workflow_id = str(result.get("run_id") or task_id)
        goal = objective.get("goal") or objective.get("description") or decomposition.get("goal") or task_id
        payload = {
            "node": {
                "node_id": node_id,
                "task_id": task_id,
                "goal": str(goal),
                "kind": str(objective.get("kind") or "implementation"),
                "status": "pending",
                "agent_id": agent_id,
                "priority": int(objective.get("priority", 3) or 3),
                "parent_id": None,
                "depth": 0,
                "result": None,
                "retry_count": 0,
                "max_retries": self.max_attempts,
                "metadata": {"pipeline_run_id": workflow_id},
            },
            "agent_id": agent_id,
            "workflow_id": workflow_id,
            "enqueued_at": utc_now().isoformat(),
            "parent_results": {},
            "metadata": {"pipeline_run_id": workflow_id},
        }
        key = f"pipeline:{workflow_id}:{task_id}:{agent_id}"
        with open_session(self.context.repository.engine) as db:
            existing = db.exec(select(QueueItemRecord).where(QueueItemRecord.idempotency_key == key)).first()
            if existing is not None:
                return self._record_data(existing)
            record = QueueItemRecord(
                id=str(uuid7()),
                idempotency_key=key,
                workflow_id=workflow_id,
                task_id=task_id,
                node_id=node_id,
                agent_id=agent_id,
                state="queued",
                payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
            )
            db.add(record)
            self._event(
                db,
                EventType.QUEUE_ITEM_ENQUEUED.value,
                record,
                {"queue_backend": "sqlite", "idempotency_key": key},
            )
            db.commit()
            db.refresh(record)
            return self._record_data(record)

    def claim(
        self,
        *,
        agent_id: str,
        server_instance_id: str,
        workflow_id: str | None = None,
        lease_ttl_seconds: int = 120,
    ) -> dict[str, Any] | None:
        if lease_ttl_seconds < 30 or lease_ttl_seconds > 3600:
            raise ValueError("lease_ttl_seconds must be between 30 and 3600")
        for _ in range(5):
            with open_session(self.context.repository.engine) as db:
                self._recover_expired(db)
                statement = (
                    select(QueueItemRecord)
                    .where(
                        QueueItemRecord.state == "queued",
                        QueueItemRecord.agent_id == agent_id,
                        QueueItemRecord.attempts < self.max_attempts,
                    )
                    .order_by(col(QueueItemRecord.created_at), col(QueueItemRecord.id))
                    .limit(1)
                )
                if workflow_id is not None:
                    statement = statement.where(QueueItemRecord.workflow_id == workflow_id)
                record = db.exec(statement).first()
                if record is None:
                    db.commit()
                    return None
                lease_id = str(uuid7())
                expires_at = utc_now() + timedelta(seconds=lease_ttl_seconds)
                result = db.exec(
                    update(QueueItemRecord)
                    .where(QueueItemRecord.id == record.id, QueueItemRecord.state == "queued")
                    .values(
                        state="leased",
                        attempts=record.attempts + 1,
                        lease_id=lease_id,
                        leased_by=server_instance_id,
                        lease_expires_at=expires_at,
                        updated_at=utc_now(),
                    )
                )
                if getattr(result, "rowcount", 0) != 1:
                    db.rollback()
                    continue
                db.expire(record)
                db.refresh(record)
                db.add(
                    WorkerLeaseRecord(
                        id=lease_id,
                        queue_item_id=record.id,
                        worker_id=server_instance_id,
                        expires_at=expires_at,
                    )
                )
                self._event(
                    db,
                    EventType.LEASE_ACQUIRED.value,
                    record,
                    {"lease_id": lease_id, "worker_id": server_instance_id, "queue_backend": "sqlite"},
                )
                self._event(db, EventType.QUEUE_ITEM_DEQUEUED.value, record, {"queue_backend": "sqlite"})
                db.commit()
                data = self._record_data(record)
                data["payload"] = json.loads(record.payload_json)
                return data
        return None

    def renew(
        self,
        *,
        queue_item_id: str,
        lease_id: str,
        server_instance_id: str,
        lease_ttl_seconds: int = 120,
    ) -> dict[str, Any]:
        with open_session(self.context.repository.engine) as db:
            record = self._leased_record(db, queue_item_id, lease_id, server_instance_id)
            expires_at = utc_now() + timedelta(seconds=lease_ttl_seconds)
            record.lease_expires_at = expires_at
            record.updated_at = utc_now()
            lease = db.get(WorkerLeaseRecord, lease_id)
            if lease is not None:
                lease.renewed_at = utc_now()
                lease.expires_at = expires_at
                db.add(lease)
            db.add(record)
            self._event(
                db,
                EventType.LEASE_RENEWED.value,
                record,
                {"lease_id": lease_id, "worker_id": server_instance_id, "queue_backend": "sqlite"},
            )
            db.commit()
            return self._record_data(record)

    def complete(
        self,
        *,
        queue_item_id: str,
        lease_id: str,
        server_instance_id: str,
        output: str,
        artifacts: list[str],
    ) -> dict[str, Any]:
        with open_session(self.context.repository.engine) as db:
            record = self._leased_record(db, queue_item_id, lease_id, server_instance_id)
            record.state = "completed"
            record.updated_at = utc_now()
            lease = db.get(WorkerLeaseRecord, lease_id)
            if lease is not None:
                lease.state = "released"
                lease.released_at = utc_now()
                db.add(lease)
            db.add(record)
            self._event(
                db,
                EventType.TASK_COMPLETED.value,
                record,
                {"output": output, "artifacts": artifacts, "lease_id": lease_id},
            )
            self._event(
                db,
                EventType.LEASE_RELEASED.value,
                record,
                {"lease_id": lease_id, "worker_id": server_instance_id, "queue_backend": "sqlite"},
            )
            db.commit()
            return self._record_data(record)

    def fail(
        self,
        *,
        queue_item_id: str,
        lease_id: str,
        server_instance_id: str,
        reason: str,
        requeue: bool,
    ) -> dict[str, Any]:
        with open_session(self.context.repository.engine) as db:
            record = self._leased_record(db, queue_item_id, lease_id, server_instance_id)
            will_requeue = requeue and record.attempts < self.max_attempts
            record.state = "queued" if will_requeue else "failed"
            record.lease_id = None
            record.leased_by = None
            record.lease_expires_at = None
            record.updated_at = utc_now()
            lease = db.get(WorkerLeaseRecord, lease_id)
            if lease is not None:
                lease.state = "released"
                lease.released_at = utc_now()
                db.add(lease)
            db.add(record)
            self._event(db, EventType.TASK_FAILED.value, record, {"reason": reason, "lease_id": lease_id})
            if will_requeue:
                self._event(
                    db,
                    EventType.TASK_REQUEUED.value,
                    record,
                    {"reason": reason, "queue_backend": "sqlite"},
                )
            db.commit()
            return self._record_data(record)

    def _recover_expired(self, db) -> None:
        now = utc_now()
        records = db.exec(
            select(QueueItemRecord).where(
                QueueItemRecord.state == "leased",
                col(QueueItemRecord.lease_expires_at) <= now,
            )
        ).all()
        for record in records:
            old_lease = record.lease_id
            record.state = "queued" if record.attempts < self.max_attempts else "failed"
            record.lease_id = None
            record.leased_by = None
            record.lease_expires_at = None
            record.updated_at = now
            db.add(record)
            self._event(
                db,
                EventType.LEASE_EXPIRED.value,
                record,
                {"lease_id": old_lease, "queue_backend": "sqlite"},
            )
            if record.state == "queued":
                self._event(
                    db,
                    EventType.TASK_REQUEUED.value,
                    record,
                    {"reason": "lease_expired", "queue_backend": "sqlite"},
                )

    def _leased_record(self, db, queue_item_id: str, lease_id: str, server_instance_id: str) -> QueueItemRecord:
        record = db.get(QueueItemRecord, queue_item_id)
        if record is None:
            raise ValueError("queue item not found")
        if record.state != "leased" or record.lease_id != lease_id or record.leased_by != server_instance_id:
            raise ValueError("invalid or expired lease")
        if record.lease_expires_at is not None:
            expires = (
                record.lease_expires_at
                if record.lease_expires_at.tzinfo is not None
                else record.lease_expires_at.replace(tzinfo=UTC)
            )
            if utc_now() > expires:
                raise ValueError("lease has expired")
        return record

    def _event(self, db, event_type: str, record: QueueItemRecord, extra: dict[str, Any]) -> None:
        session_id = self.context.active_session_id
        if session_id is None:
            raise ValueError("No active session is available")
        self.context.repository.append_event(
            project_path=self.context.project_path,
            session_id=session_id,
            type=event_type,
            source="queue",
            payload={
                "queue_item_id": record.id,
                "workflow_id": record.workflow_id,
                "task_id": record.task_id,
                "node_id": record.node_id,
                "agent_id": record.agent_id,
                "state": record.state,
                **extra,
            },
            agent_id=record.agent_id,
            task_hint=record.task_id,
            _session=db,
        )

    @staticmethod
    def _record_data(record: QueueItemRecord) -> dict[str, Any]:
        return {
            "queue_item_id": record.id,
            "workflow_id": record.workflow_id,
            "task_id": record.task_id,
            "node_id": record.node_id,
            "agent_id": record.agent_id,
            "state": record.state,
            "attempts": record.attempts,
            "lease_id": record.lease_id,
            "lease_expires_at": record.lease_expires_at.isoformat() if record.lease_expires_at else None,
        }
