from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from allbrain.workflow.models import SubtaskResult, TaskNode


@dataclass
class QueueItem:
    node: TaskNode
    agent_id: str
    workflow_id: str
    enqueued_at: datetime = field(default_factory=datetime.now)
    parent_results: dict[str, SubtaskResult] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node.node_id,
            "agent_id": self.agent_id,
            "workflow_id": self.workflow_id,
            "enqueued_at": self.enqueued_at.isoformat(),
            "parent_results": {nid: r.to_dict() for nid, r in self.parent_results.items()},
            "metadata": dict(self.metadata),
        }


class TaskQueue(ABC):
    """Abstract task queue interface. Implementations can be in-memory, Redis, RabbitMQ, etc."""

    @abstractmethod
    async def enqueue(self, item: QueueItem) -> None: ...

    @abstractmethod
    async def dequeue(self, timeout: float | None = None) -> QueueItem | None: ...

    @abstractmethod
    def qsize(self) -> int: ...

    @abstractmethod
    def empty(self) -> bool: ...

    def capabilities(self) -> dict[str, Any]:
        return {
            "backend": self.__class__.__name__,
            "persistent": False,
            "lease_aware": False,
            "distributed_ready": False,
        }

    async def ack(self, item: QueueItem) -> None:  # noqa: B027
        """Optional completion hook for persistent queues."""

    async def nack(self, item: QueueItem, *, requeue: bool = True, reason: str | None = None) -> None:  # noqa: B027
        """Optional failure hook for persistent queues."""

    async def renew_lease(self, item: QueueItem) -> None:  # noqa: B027
        """Optional lease renewal hook for persistent queues."""

    async def recover_expired(self) -> int:
        """Optional expired in-flight recovery hook."""
        return 0

    async def close(self) -> None:  # noqa: B027
        """Optional cleanup hook."""


class InMemoryTaskQueue(TaskQueue):
    """In-memory FIFO task queue. Production deployments can swap with Redis/RabbitMQ."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._queue: deque[QueueItem] = deque(maxlen=max_size)
        self._max_size = max_size
        self._not_empty = asyncio.Event()

    async def enqueue(self, item: QueueItem) -> None:
        if len(self._queue) >= self._max_size:
            raise RuntimeError(f"Task queue full (max_size={self._max_size})")
        self._queue.append(item)
        self._not_empty.set()

    async def dequeue(self, timeout: float | None = None) -> QueueItem | None:
        if not self._queue and timeout is None:
            return None
        try:
            if timeout is not None:
                await asyncio.wait_for(self._wait_for_item(), timeout=timeout)
            else:
                await self._wait_for_item()
        except TimeoutError:
            return None
        if not self._queue:
            return None
        item = self._queue.popleft()
        if not self._queue:
            self._not_empty.clear()
        return item

    async def _wait_for_item(self) -> None:
        if self._queue:
            return
        await self._not_empty.wait()

    def qsize(self) -> int:
        return len(self._queue)

    def empty(self) -> bool:
        return len(self._queue) == 0

    def capabilities(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "persistent": False,
            "lease_aware": False,
            "distributed_ready": False,
        }
