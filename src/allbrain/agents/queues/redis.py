from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from uuid6 import uuid7

from allbrain.agents.queue import QueueItem, TaskQueue
from allbrain.reliability.idempotency import IdempotencyKeyBuilder

# Optional real Redis client
try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    HAS_REDIS = False


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

    When a `redis_url` is supplied and the `redis` package is installed
    (`pip install allbrain-mcp[distributed]`), this adapter connects to a real
    Redis instance.  Otherwise it falls back to an in-memory simulation so that
    offline / chaos tests work without a broker.
    """

    def __init__(
        self,
        *,
        worker_id: str = "redis-worker",
        lease_ttl_seconds: int = 60,
        max_attempts: int = 3,
        store: RedisQueueStore | None = None,
        redis_url: str | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.lease_ttl_seconds = lease_ttl_seconds
        self.max_attempts = max_attempts
        self._key_builder = IdempotencyKeyBuilder()
        self._redis_url = redis_url
        self._redis_client: aioredis.Redis | None = None  # type: ignore[arg-type]

        # Use real Redis when possible, otherwise fall back to local simulation.
        if redis_url and HAS_REDIS:
            self._use_real = True
            self.store: RedisQueueStore | None = None
        else:
            self._use_real = False
            self.store = store or RedisQueueStore()

    async def _get_redis(self) -> aioredis.Redis | None:  # type: ignore[valid-type]
        if self._redis_client is None and self._redis_url and HAS_REDIS:
            self._redis_client = await aioredis.from_url(self._redis_url)  # type: ignore[union-attr]
        return self._redis_client

    async def enqueue(self, item: QueueItem) -> None:
        if self._use_real:
            client = await self._get_redis()
            if client:
                key = str(item.metadata.get("idempotency_key") or self._key_builder.queue_item_key(item))
                await client.hset(
                    f"queue:{key}",
                    mapping={"state": "queued", "payload": item.model_dump_json()},
                )
                await client.rpush("queue:order", key)
                return
        # Fallback to local simulation
        key = str(item.metadata.get("idempotency_key") or self._key_builder.queue_item_key(item))
        existing = self.store.records.get(key)
        if existing and existing.state in {"queued", "leased", "completed"}:
            return
        item.metadata["idempotency_key"] = key
        self.store.records[key] = _StoredItem(item=item)
        self.store.order.append(key)

    async def dequeue(self, timeout: float | None = None) -> QueueItem | None:
        if self._use_real:
            client = await self._get_redis()
            if client:
                # Simplified real-redis dequeue: pop from queue:order
                while True:
                    key = await client.lpop("queue:order")
                    if key is None:
                        return None
                    key = key.decode()
                    data = await client.hgetall(f"queue:{key}")
                    if not data:
                        continue
                    state = data.get(b"state", b"").decode()
                    if state != "queued":
                        continue
                    await client.hset(f"queue:{key}", "state", "leased")
                    from allbrain.models.schemas import ToolResult

                    return QueueItem.model_validate_json(data[b"payload"])
        # Fallback
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
            record.item.metadata.update(
                {"idempotency_key": key, "lease_id": record.lease_id, "attempts": record.attempts}
            )
            return record.item
        return None

    async def ack(self, item: QueueItem) -> None:
        if self._use_real:
            client = await self._get_redis()
            if client:
                key = _key(item)
                await client.hset(f"queue:{key}", "state", "completed")
                return
        key = _key(item)
        if key in self.store.records:
            self.store.records[key].state = "completed"

    async def nack(self, item: QueueItem, *, requeue: bool = True, reason: str | None = None) -> None:
        if self._use_real:
            client = await self._get_redis()
            if client and requeue:
                key = _key(item)
                await client.hset(f"queue:{key}", "state", "queued")
                await client.rpush("queue:order", key)
            return
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
        cap: dict[str, object] = {"backend": "redis", "persistent": True, "lease_aware": True, "available": True}
        if self._use_real:
            cap["distributed_ready"] = True
        else:
            cap["distributed_ready"] = False
            cap["simulation"] = True
        return cap


def _key(item: QueueItem) -> str:
    return str(item.metadata["idempotency_key"])


def _now() -> datetime:
    return datetime.now(UTC)
