from __future__ import annotations

from allbrain.agents.queue import QueueItem
from allbrain.agents.queues.redis import RedisQueueStore, RedisTaskQueue

# Optional real aio-pika client
try:
    import aio_pika

    HAS_AIO_PIKA = True
except ImportError:
    aio_pika = None  # type: ignore[assignment]
    HAS_AIO_PIKA = False


class RabbitMQTaskQueue(RedisTaskQueue):
    """Durable-message RabbitMQ adapter with Sprint 14 lease semantics.

    When an `amqp_url` is supplied and `aio-pika` is installed
    (`pip install allbrain-mcp[distributed]`), this adapter connects to a real
    AMQP broker.  Otherwise it falls back to the local simulation store so
    chaos tests work without a broker.
    """

    def __init__(
        self,
        *,
        queue_name: str = "allbrain.tasks",
        worker_id: str = "rabbitmq-worker",
        lease_ttl_seconds: int = 60,
        max_attempts: int = 3,
        store: RedisQueueStore | None = None,
        amqp_url: str | None = None,
    ) -> None:
        super().__init__(
            worker_id=worker_id,
            lease_ttl_seconds=lease_ttl_seconds,
            max_attempts=max_attempts,
            store=store,
            redis_url=None,  # RabbitMQ doesn't use Redis URL
        )
        self.queue_name = queue_name
        self._amqp_url = amqp_url
        self._amqp_connection = None
        self._inflight: dict[int, object] = {}

        if amqp_url and HAS_AIO_PIKA:
            self._use_real = False  # real AMQP logic uses a separate path
            self._amqp_channel = None
            self._amqp_queue = None
        else:
            self._use_real = False

    async def _ensure_amqp(self):
        if not self._amqp_url or not HAS_AIO_PIKA:
            return None
        if self._amqp_connection is None:
            self._amqp_connection = await aio_pika.connect_robust(self._amqp_url)
            self._amqp_channel = await self._amqp_connection.channel()
            self._amqp_queue = await self._amqp_channel.declare_queue(self.queue_name, durable=True)
        return self._amqp_queue

    async def enqueue(self, item: QueueItem) -> None:
        queue = await self._ensure_amqp()
        if queue:
            item.metadata["queue_name"] = self.queue_name
            await self._amqp_channel.default_exchange.publish(
                aio_pika.Message(
                    body=item.model_dump_json().encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=self.queue_name,
            )
            return
        item.metadata["queue_name"] = self.queue_name
        await super().enqueue(item)

    async def dequeue(self, timeout: float | None = None) -> QueueItem | None:
        queue = await self._ensure_amqp()
        if queue:
            msg = await queue.get(fail=False, no_ack=False)
            if msg:
                item = QueueItem.model_validate_json(msg.body)
                delivery_tag = msg.delivery_tag
                item.metadata["delivery_tag"] = delivery_tag
                self._inflight[delivery_tag] = msg
                return item
            return None
        return await super().dequeue(timeout=timeout)

    async def ack(self, item: QueueItem) -> None:
        delivery_tag = item.metadata.pop("delivery_tag", None)
        if delivery_tag is not None:
            message = self._inflight.pop(delivery_tag, None)
            if message is not None:
                await message.ack()
                return
        await super().ack(item)

    async def nack(self, item: QueueItem, *, requeue: bool = True, reason: str | None = None) -> None:
        delivery_tag = item.metadata.pop("delivery_tag", None)
        if delivery_tag is not None:
            message = self._inflight.pop(delivery_tag, None)
            if message is not None:
                await message.nack(requeue=requeue)
                return
        await super().nack(item, requeue=requeue, reason=reason)

    def capabilities(self) -> dict[str, object]:
        cap: dict[str, object] = {
            "backend": "rabbitmq",
            "queue_name": self.queue_name,
            "persistent": True,
            "lease_aware": True,
            "available": True,
        }
        if self._amqp_url and HAS_AIO_PIKA:
            cap["distributed_ready"] = False
            cap["experimental"] = True
            cap["durable_messages"] = True
        else:
            cap["distributed_ready"] = False
            cap["simulation"] = True
        return cap

    async def close(self) -> None:
        if self._amqp_connection is not None:
            await self._amqp_connection.close()
            self._amqp_connection = None
