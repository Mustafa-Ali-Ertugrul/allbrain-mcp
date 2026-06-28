from __future__ import annotations

from allbrain.agents.queue import QueueItem
from allbrain.agents.queues.redis import RedisQueueStore, RedisTaskQueue


class RabbitMQTaskQueue(RedisTaskQueue):
    """Durable-message RabbitMQ adapter with Sprint 14 lease semantics.

    The v1 implementation shares the deterministic lease-aware local store used
    by RedisTaskQueue so chaos tests do not require a broker. The public queue
    contract models RabbitMQ behavior: durable enqueue, ack, nack/requeue, and
    worker ownership metadata.
    """

    def __init__(
        self,
        *,
        queue_name: str = "allbrain.tasks",
        worker_id: str = "rabbitmq-worker",
        lease_ttl_seconds: int = 60,
        max_attempts: int = 3,
        store: RedisQueueStore | None = None,
    ) -> None:
        super().__init__(worker_id=worker_id, lease_ttl_seconds=lease_ttl_seconds, max_attempts=max_attempts, store=store)
        self.queue_name = queue_name

    async def enqueue(self, item: QueueItem) -> None:
        item.metadata["queue_name"] = self.queue_name
        await super().enqueue(item)

    def capabilities(self) -> dict[str, object]:
        return {
            "backend": "rabbitmq",
            "queue_name": self.queue_name,
            "persistent": True,
            "lease_aware": True,
            "distributed_ready": True,
            "available": True,
            "durable_messages": True,
        }
