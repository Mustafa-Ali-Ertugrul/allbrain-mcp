from __future__ import annotations

import os

import pytest

from allbrain.agents.queue import QueueItem
from allbrain.agents.queues import SQLiteTaskQueue
from allbrain.storage import BrainRepository, create_engine_for_url, init_db
from allbrain.workflow.models import TaskNode


@pytest.mark.asyncio
async def test_postgres_repository_and_queue_contract() -> None:
    database_url = os.environ.get("ALLBRAIN_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("ALLBRAIN_TEST_POSTGRES_URL is not configured")
    engine = create_engine_for_url(database_url)
    init_db(engine)
    repository = BrainRepository(engine)
    project = "/tmp/allbrain-postgres-contract"
    session = repository.create_session(project, "postgres-agent")

    event = repository.append_event(
        project_path=project,
        session_id=session.id or 0,
        type="file_modified",
        source="integration",
        payload={"path": "README.md"},
    )
    replayed = repository.list_events(project_path=project, limit=10)
    assert [item.id for item in replayed] == [event.id]

    queue = SQLiteTaskQueue(engine, worker_id="postgres-worker")
    item = QueueItem(
        node=TaskNode(node_id="pg-node", task_id="pg-task", goal="Exercise queue"),
        agent_id="postgres-agent",
        workflow_id="pg-workflow",
    )
    await queue.enqueue(item)
    leased = await queue.dequeue(timeout=0)
    assert leased is not None
    await queue.ack(leased)
    assert queue.empty()

    closed = repository.close_session(session.id or 0, reason="contract_complete")
    assert closed is not None and closed.status == "closed"
    repository.close()
