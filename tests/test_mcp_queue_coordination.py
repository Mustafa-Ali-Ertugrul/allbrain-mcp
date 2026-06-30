from __future__ import annotations

from pathlib import Path

import pytest

from allbrain.events import EventType
from allbrain.server import BrainContext
from allbrain.server.queueing import QueueCoordinator
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def make_context(tmp_path: Path, *, agent: str = "codex", instance: str = "instance-a") -> BrainContext:
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repository = BrainRepository(engine)
    project = tmp_path / "project"
    project.mkdir()
    session = repository.create_session(project, agent, server_instance_id=instance)
    return BrainContext(
        repository=repository,
        project_path=str(project.resolve()),
        active_session=session,
        agent_name=agent,
        server_instance_id=instance,
    )


def pipeline_result(agent: str = "codex") -> dict:
    return {
        "run_id": "run-1",
        "objective": {"goal": "Implement queue", "kind": "implementation", "priority": 2},
        "decomposition": {"task_id": "task-1", "goal": "Implement queue"},
        "scheduler": {
            "summary": {"task_id": "task-1"},
            "assignment": {"agent_id": agent},
        },
    }


def test_claim_is_agent_scoped_and_single_winner(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    coordinator = QueueCoordinator(context)
    queued = coordinator.enqueue_pipeline_result(pipeline_result())

    assert coordinator.claim(agent_id="claude", server_instance_id="other") is None
    claimed = coordinator.claim(agent_id="codex", server_instance_id="instance-a")
    assert claimed is not None
    assert claimed["queue_item_id"] == queued["queue_item_id"]
    assert coordinator.claim(agent_id="codex", server_instance_id="instance-b") is None

    with pytest.raises(ValueError, match="invalid or expired lease"):
        coordinator.complete(
            queue_item_id=claimed["queue_item_id"],
            lease_id=claimed["lease_id"],
            server_instance_id="instance-b",
            output="bad",
            artifacts=[],
        )

    completed = coordinator.complete(
        queue_item_id=claimed["queue_item_id"],
        lease_id=claimed["lease_id"],
        server_instance_id="instance-a",
        output="done",
        artifacts=["queue.py"],
    )
    assert completed["state"] == "completed"
    events = context.repository.list_events(project_path=context.project_path, limit=100)
    types = {event.type for event in events}
    assert EventType.QUEUE_ITEM_ENQUEUED.value in types
    assert EventType.LEASE_ACQUIRED.value in types
    assert EventType.TASK_COMPLETED.value in types


def test_failed_claim_can_be_requeued(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    coordinator = QueueCoordinator(context)
    coordinator.enqueue_pipeline_result(pipeline_result())
    claimed = coordinator.claim(agent_id="codex", server_instance_id="instance-a")
    assert claimed is not None

    failed = coordinator.fail(
        queue_item_id=claimed["queue_item_id"],
        lease_id=claimed["lease_id"],
        server_instance_id="instance-a",
        reason="retry me",
        requeue=True,
    )
    assert failed["state"] == "queued"
    reclaimed = coordinator.claim(agent_id="codex", server_instance_id="instance-a")
    assert reclaimed is not None
    assert reclaimed["attempts"] == 2
