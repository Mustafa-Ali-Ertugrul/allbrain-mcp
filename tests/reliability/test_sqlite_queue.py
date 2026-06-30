from __future__ import annotations

from allbrain.agents.queue import QueueItem
from allbrain.agents.queues import RedisTaskQueue, RabbitMQTaskQueue, SQLiteTaskQueue
from allbrain.models.entities import QueueItemRecord, utc_now
from allbrain.storage import create_engine_for_path, init_db
from allbrain.storage.database import open_session
from allbrain.workflow.models import TaskNode


def make_item(node_id: str = "n1") -> QueueItem:
    return QueueItem(node=TaskNode(node_id=node_id, task_id="t1", goal="Do thing"), agent_id="builder", workflow_id="wf1")


async def test_sqlite_queue_persists_across_instances_and_acks(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "queue.db")
    init_db(engine)
    await SQLiteTaskQueue(engine).enqueue(make_item())

    restarted = SQLiteTaskQueue(engine, worker_id="worker-b")
    item = await restarted.dequeue(timeout=0)

    assert item is not None
    assert item.node.node_id == "n1"
    await restarted.ack(item)
    assert restarted.empty()
    engine.dispose()


async def test_sqlite_queue_ignores_duplicate_active_item(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "queue.db")
    init_db(engine)
    queue = SQLiteTaskQueue(engine)

    await queue.enqueue(make_item())
    await queue.enqueue(make_item())

    assert queue.qsize() == 1
    engine.dispose()


async def test_sqlite_queue_recovers_expired_leases(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "queue.db")
    init_db(engine)
    queue = SQLiteTaskQueue(engine, lease_ttl_seconds=1)
    await queue.enqueue(make_item())
    item = await queue.dequeue(timeout=0)
    assert item is not None
    with open_session(engine) as db:
        record = db.get(QueueItemRecord, item.metadata["queue_record_id"])
        assert record is not None
        record.lease_expires_at = utc_now()
        db.add(record)
        db.commit()

    assert await queue.recover_expired() == 1
    assert queue.qsize() == 1
    engine.dispose()


async def test_distributed_adapters_are_lease_aware_and_ack_items() -> None:
    for queue in [RedisTaskQueue(), RabbitMQTaskQueue()]:
        caps = queue.capabilities()
        assert "distributed_ready" in caps
        assert caps["available"] is True
        await queue.enqueue(make_item())
        item = await queue.dequeue(timeout=0)
        assert item is not None
        await queue.ack(item)
        assert queue.empty()

