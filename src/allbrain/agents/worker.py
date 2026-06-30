from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from allbrain.agents.queue import QueueItem, TaskQueue
from allbrain.workflow.models import SubtaskResult

logger = logging.getLogger(__name__)


@dataclass
class WorkerStats:
    worker_id: int
    tasks_processed: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    is_running: bool = False


class WorkerPool:
    """Async worker pool that pulls from a TaskQueue and dispatches to a handler."""

    def __init__(
        self,
        queue: TaskQueue,
        handler: Callable[[QueueItem], Awaitable[SubtaskResult]],
        num_workers: int = 4,
        name: str = "worker",
    ) -> None:
        if num_workers < 1:
            raise ValueError("num_workers must be >= 1")
        self.queue = queue
        self.handler = handler
        self.num_workers = num_workers
        self.name = name
        self._tasks: list[asyncio.Task[None]] = []
        self._stop_event = asyncio.Event()
        self._in_flight = 0
        self._in_flight_lock = asyncio.Lock()
        self._idle_event = asyncio.Event()
        self._idle_event.set()
        self._stats: list[WorkerStats] = [WorkerStats(worker_id=i) for i in range(num_workers)]

    async def start(self) -> None:
        if self._tasks:
            return
        self._stop_event.clear()
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker_loop(i), name=f"{self.name}-{i}")
            self._tasks.append(task)

    async def stop(self, *, timeout: float = 5.0) -> None:
        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=timeout)
        self._tasks.clear()
        await self.queue.close()

    async def submit(self, item: QueueItem) -> None:
        self._idle_event.clear()
        await self.queue.enqueue(item)

    async def join(self) -> None:
        """Wait for all submitted items to be processed and workers to be idle."""
        while True:
            async with self._in_flight_lock:
                in_flight = self._in_flight
            if in_flight == 0 and self.queue.empty():
                return
            try:
                await asyncio.wait_for(self._idle_event.wait(), timeout=0.5)
            except TimeoutError:
                pass

    def stats(self) -> list[WorkerStats]:
        return list(self._stats)

    async def _worker_loop(self, worker_id: int) -> None:
        stats = self._stats[worker_id]
        stats.is_running = True
        try:
            while not self._stop_event.is_set():
                try:
                    item = await self.queue.dequeue(timeout=0.5)
                except asyncio.CancelledError:
                    break
                if item is None:
                    continue
                async with self._in_flight_lock:
                    self._in_flight += 1
                    self._idle_event.clear()
                try:
                    result = await self.handler(item)
                    await self.queue.ack(item)
                    stats.tasks_processed += 1
                    if result.output or not result.metadata.get("error"):
                        stats.tasks_succeeded += 1
                    else:
                        stats.tasks_failed += 1
                except asyncio.CancelledError:
                    await self.queue.nack(item, requeue=True, reason="worker_cancelled")
                    break
                except Exception as exc:  # noqa: BLE001
                    await self.queue.nack(item, requeue=True, reason=str(exc))
                    stats.tasks_processed += 1
                    stats.tasks_failed += 1
                    logger.exception(
                        "Worker %s failed to process item %s: %s",
                        worker_id,
                        item.node.node_id,
                        exc,
                    )
                finally:
                    async with self._in_flight_lock:
                        self._in_flight -= 1
                        if self._in_flight == 0 and self.queue.empty():
                            self._idle_event.set()
        finally:
            stats.is_running = False
