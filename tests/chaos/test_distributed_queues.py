from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from allbrain.agents.queue import QueueItem
from allbrain.agents.queues import RabbitMQTaskQueue, RedisQueueStore, RedisTaskQueue
from allbrain.workflow.models import TaskNode


def make_item(node_id: str = "n1") -> QueueItem:
    return QueueItem(
        node=TaskNode(node_id=node_id, task_id="t1", goal="Do thing"), agent_id="builder", workflow_id="wf1"
    )


async def test_redis_queue_duplicate_delivery_and_recovery_are_deterministic() -> None:
    store = RedisQueueStore()
    first = RedisTaskQueue(worker_id="w1", lease_ttl_seconds=1, store=store)
    second = RedisTaskQueue(worker_id="w2", lease_ttl_seconds=1, store=store)

    await first.enqueue(make_item())
    await first.enqueue(make_item())
    leased = await first.dequeue(timeout=0)
    assert leased is not None
    assert first.qsize() == 0
    key = leased.metadata["idempotency_key"]
    store.records[key].lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    assert await second.recover_expired() == 1
    recovered = await second.dequeue(timeout=0)
    assert recovered is not None
    assert recovered.metadata["attempts"] == 2


async def test_rabbitmq_queue_nack_requeues_until_ack() -> None:
    queue = RabbitMQTaskQueue(worker_id="w1")
    await queue.enqueue(make_item())
    item = await queue.dequeue(timeout=0)
    assert item is not None
    await queue.nack(item, requeue=True, reason="network_timeout")
    redelivered = await queue.dequeue(timeout=0)
    assert redelivered is not None
    await queue.ack(redelivered)
    assert queue.empty()
