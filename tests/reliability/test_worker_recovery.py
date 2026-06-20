from __future__ import annotations

from allbrain.agents.queue import QueueItem
from allbrain.agents.queues import SQLiteTaskQueue
from allbrain.agents.worker import WorkerPool
from allbrain.storage import create_engine_for_path, init_db
from allbrain.workflow.models import SubtaskResult, TaskNode


def make_item() -> QueueItem:
    return QueueItem(node=TaskNode(node_id="n1", task_id="t1", goal="Do thing"), agent_id="builder", workflow_id="wf1")


async def test_worker_failure_requeues_until_retry_cap(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "queue.db")
    init_db(engine)
    queue = SQLiteTaskQueue(engine, max_attempts=2)
    calls = 0

    async def handler(item: QueueItem) -> SubtaskResult:
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    pool = WorkerPool(queue, handler, num_workers=1)
    await pool.submit(make_item())
    await pool.start()
    await pool.join()
    await pool.stop()

    assert calls == 2
    assert queue.empty()
    engine.dispose()


async def test_worker_success_acks_persistent_queue(tmp_path) -> None:
    engine = create_engine_for_path(tmp_path / "queue.db")
    init_db(engine)
    queue = SQLiteTaskQueue(engine)

    async def handler(item: QueueItem) -> SubtaskResult:
        return SubtaskResult(node_id=item.node.node_id, agent_id=item.agent_id, output="ok")

    pool = WorkerPool(queue, handler, num_workers=1)
    await pool.submit(make_item())
    await pool.start()
    await pool.join()
    await pool.stop()

    assert queue.empty()
    assert pool.stats()[0].tasks_succeeded == 1
    engine.dispose()
