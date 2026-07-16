"""Sprint C: create_task(enqueue) → claim → complete multi-agent loop."""

from __future__ import annotations

from pathlib import Path

import pytest

from allbrain.events import EventType
from allbrain.server import BrainContext
from allbrain.server.queueing import QueueCoordinator
from allbrain.server.tools.tasks import create_task_impl
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def _shared_contexts(tmp_path: Path) -> tuple[BrainContext, BrainContext]:
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repository = BrainRepository(engine)
    project = tmp_path / "project"
    project.mkdir()
    project_path = str(project.resolve())
    session_a = repository.create_session(project, "codex", server_instance_id="worker-a")
    session_b = repository.create_session(project, "claude", server_instance_id="worker-b")
    ctx_a = BrainContext(
        repository=repository,
        project_path=project_path,
        active_session=session_a,
        agent_name="codex",
        server_instance_id="worker-a",
    )
    ctx_b = BrainContext(
        repository=repository,
        project_path=project_path,
        active_session=session_b,
        agent_name="claude",
        server_instance_id="worker-b",
    )
    return ctx_a, ctx_b


def test_create_task_enqueue_claim_complete_two_agents(tmp_path: Path) -> None:
    ctx_a, ctx_b = _shared_contexts(tmp_path)

    created_a = create_task_impl(
        ctx_a,
        goal="implement claim loop A",
        kind="implementation",
        priority=3,
        agent_id="codex",
        enqueue=True,
        task_id="task-a",
    )
    created_b = create_task_impl(
        ctx_b,
        goal="implement claim loop B",
        kind="implementation",
        priority=3,
        agent_id="claude",
        enqueue=True,
        task_id="task-b",
    )
    assert created_a.ok and created_b.ok, (created_a.error, created_b.error)
    assert created_a.data["queue"]["agent_id"] == "codex"
    assert created_b.data["queue"]["agent_id"] == "claude"
    assert created_a.data["queue"]["state"] == "queued"
    assert created_b.data["queue"]["state"] == "queued"

    coord_a = QueueCoordinator(ctx_a)
    coord_b = QueueCoordinator(ctx_b)

    # Each worker claims only its agent-scoped queue items.
    claimed_a = coord_a.claim(agent_id="codex", server_instance_id="worker-a")
    claimed_b = coord_b.claim(agent_id="claude", server_instance_id="worker-b")
    assert claimed_a is not None and claimed_b is not None
    assert claimed_a["task_id"] == "task-a"
    assert claimed_b["task_id"] == "task-b"
    assert claimed_a["lease_id"] and claimed_b["lease_id"]

    # Single-winner: no second lease while item is leased.
    assert coord_a.claim(agent_id="codex", server_instance_id="worker-a2") is None
    assert coord_b.claim(agent_id="claude", server_instance_id="worker-b2") is None

    # Lease is bound to server_instance_id: wrong worker cannot complete.
    with pytest.raises(ValueError, match="invalid or expired lease"):
        coord_b.complete(
            queue_item_id=claimed_a["queue_item_id"],
            lease_id=claimed_a["lease_id"],
            server_instance_id="worker-b",
            output="stolen",
            artifacts=[],
        )

    done_a = coord_a.complete(
        queue_item_id=claimed_a["queue_item_id"],
        lease_id=claimed_a["lease_id"],
        server_instance_id="worker-a",
        output="A done",
        artifacts=["a.py"],
    )
    done_b = coord_b.complete(
        queue_item_id=claimed_b["queue_item_id"],
        lease_id=claimed_b["lease_id"],
        server_instance_id="worker-b",
        output="B done",
        artifacts=["b.py"],
    )
    assert done_a["state"] == "completed"
    assert done_b["state"] == "completed"

    events = ctx_a.repository.list_events(project_path=ctx_a.project_path, limit=200)
    types = {event.type for event in events}
    assert EventType.TASK_CREATED.value in types
    assert EventType.QUEUE_ITEM_ENQUEUED.value in types
    assert EventType.LEASE_ACQUIRED.value in types
    assert EventType.TASK_COMPLETED.value in types


def test_create_task_without_enqueue_has_no_queue_payload(tmp_path: Path) -> None:
    ctx_a, _ = _shared_contexts(tmp_path)
    created = create_task_impl(ctx_a, goal="no queue", kind="testing")
    assert created.ok
    assert "queue" not in (created.data or {})


def test_enqueue_task_idempotent(tmp_path: Path) -> None:
    ctx_a, _ = _shared_contexts(tmp_path)
    coordinator = QueueCoordinator(ctx_a)
    first = coordinator.enqueue_task(
        task_id="t1",
        goal="once",
        agent_id="codex",
        workflow_id="t1",
    )
    second = coordinator.enqueue_task(
        task_id="t1",
        goal="once",
        agent_id="codex",
        workflow_id="t1",
    )
    assert first["queue_item_id"] == second["queue_item_id"]
