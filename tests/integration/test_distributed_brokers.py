from __future__ import annotations

import os

import pytest

from allbrain.domains.collaboration.agents.queue import QueueItem
from allbrain.domains.collaboration.agents.queues import RabbitMQTaskQueue, RedisTaskQueue
from allbrain.domains.collaboration.workflow.models import TaskNode


def _item(node_id: str) -> QueueItem:
    return QueueItem(
        node=TaskNode(node_id=node_id, task_id=f"task-{node_id}", goal="Broker contract"),
        agent_id="integration-agent",
        workflow_id="integration-workflow",
    )


@pytest.mark.asyncio
async def test_real_redis_round_trip_ack_and_reconnect() -> None:
    url = os.environ.get("ALLBRAIN_TEST_REDIS_URL")
    if not url:
        pytest.skip("ALLBRAIN_TEST_REDIS_URL is not configured")
    redis = pytest.importorskip("redis.asyncio")

    client = redis.from_url(url)
    await client.flushdb()
    producer = RedisTaskQueue(redis_url=url)
    await producer.enqueue(_item("redis"))
    await producer.close()

    consumer = RedisTaskQueue(redis_url=url)
    leased = await consumer.dequeue(timeout=1)
    assert leased is not None
    key = leased.metadata["idempotency_key"]
    await consumer.ack(leased)
    assert await client.hget(f"queue:{key}", "state") == b"completed"
    assert consumer.capabilities()["distributed_ready"] is False
    assert consumer.capabilities()["experimental"] is True
    await consumer.close()
    await client.aclose()


@pytest.mark.asyncio
async def test_real_rabbitmq_round_trip_ack_and_reconnect() -> None:
    url = os.environ.get("ALLBRAIN_TEST_AMQP_URL")
    if not url:
        pytest.skip("ALLBRAIN_TEST_AMQP_URL is not configured")
    pytest.importorskip("aio_pika")
    producer = RabbitMQTaskQueue(amqp_url=url, queue_name="allbrain.contract")
    queue = await producer._ensure_amqp()
    assert queue is not None, "RabbitMQ queue not available"
    await queue.purge()
    await producer.enqueue(_item("rabbit"))
    await producer.close()

    consumer = RabbitMQTaskQueue(amqp_url=url, queue_name="allbrain.contract")
    leased = await consumer.dequeue(timeout=1)
    assert leased is not None
    await consumer.ack(leased)
    assert await consumer.dequeue(timeout=0) is None
    assert consumer.capabilities()["distributed_ready"] is False
    assert consumer.capabilities()["experimental"] is True
    await consumer.close()
