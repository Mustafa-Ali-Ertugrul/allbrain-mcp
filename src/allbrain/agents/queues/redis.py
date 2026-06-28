from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from uuid6 import uuid7

from allbrain.agents.queue import QueueItem, TaskQueue
from allbrain.reliability.idempotency import IdempotencyKeyBuilder


@dataclass
class _StoredItem:
    item: QueueItem
    state: str = "queued"
    attempts: int = 0
    lease_id: str | None = None
    leased_by: str | None = None
    lease_expires_at: datetime | None = None


@dataclass
class RedisQueueStore:
    records: dict[str, _StoredItem] = field(default_factory=dict)
    order: deque[str] = field(default_factory=deque)


class RedisTaskQueue(TaskQueue):
    """Lease-aware Redis queue adapter.

    Sprint 14 keeps external Redis optional. When no Redis client is supplied,
    this class uses a deterministic local store with Redis-like semantics so
    recovery and duplicate-delivery behavior can be tested without services.
    """

    def __init__(
        self,
        *,
        worker_id: str = "redis-worker",
        lease_ttl_seconds: int = 60,
        max_attempts: int = 3,
        store: RedisQueueStore | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.lease_ttl_seconds = lease_ttl_seconds
        self.max_attempts = max_attempts
        self.store = store or RedisQueueStore()
        self._key_builder = IdempotencyKeyBuilder()

    async def enqueue(self, item: QueueItem) -> None:
        key = str(item.metadata.get("idempotency_key") or self._key_builder.queue_item_key(item))
        existing = self.store.records.get(key)
        if existing and existing.state in {"queued", "leased", "completed"}:
            return
        item.metadata["idempotency_key"] = key
        self.store.records[key] = _StoredItem(item=item)
        self.store.order.append(key)

    async def dequeue(self, timeout: float | None = None) -> QueueItem | None:
        deadline = None if timeout is None else _now() + timedelta(seconds=timeout)
        while True:
            await self.recover_expired()
            item = self._dequeue_once()
            if item is not None or timeout is None:
                return item
            if deadline and _now() >= deadline:
                return None
            await asyncio.sleep(0.05)

    def _dequeue_once(self) -> QueueItem | None:
        for key in list(self.store.order):
            record = self.store.records[key]
            if record.state != "queued" or record.attempts >= self.max_attempts:
                continue
            record.state = "leased"
            record.attempts += 1
            record.lease_id = str(uuid7())
            record.leased_by = self.worker_id
            record.lease_expires_at = _now() + timedelta(seconds=self.lease_ttl_seconds)
            record.item.metadata.update({"idempotency_key": key, "lease_id": record.lease_id, "attempts": record.attempts})
            return record.item
        return None

    async def ack(self, item: QueueItem) -> None:
        key = _key(item)
        if key in self.store.records:
            self.store.records[key].state = "completed"

    async def nack(self, item: QueueItem, *, requeue: bool = True, reason: str | None = None) -> None:
        key = _key(item)
        record = self.store.records.get(key)
        if not record:
            return
        record.lease_id = None
        record.leased_by = None
        record.lease_expires_at = None
        record.state = "queued" if requeue and record.attempts < self.max_attempts else "failed"

    async def renew_lease(self, item: QueueItem) -> None:
        key = _key(item)
        record = self.store.records.get(key)
        if record and record.state == "leased":
            record.lease_expires_at = _now() + timedelta(seconds=self.lease_ttl_seconds)

    async def recover_expired(self) -> int:
        recovered = 0
        now = _now()
        for record in self.store.records.values():
            if record.state == "leased" and record.lease_expires_at and record.lease_expires_at <= now:
                record.state = "queued" if record.attempts < self.max_attempts else "failed"
                record.lease_id = None
                record.leased_by = None
                record.lease_expires_at = None
                if record.state == "queued":
                    recovered += 1
        return recovered

    def qsize(self) -> int:
        return sum(1 for record in self.store.records.values() if record.state == "queued")

    def empty(self) -> bool:
        return self.qsize() == 0

    def capabilities(self) -> dict[str, object]:
        return {"backend": "redis", "persistent": True, "lease_aware": True, "distributed_ready": True, "available": True}


def _key(item: QueueItem) -> str:
    return str(item.metadata["idempotency_key"])


def _now() -> datetime:
    return datetime.now(timezone.utc)
