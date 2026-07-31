"""A2 regression: renew/complete/fail must use ``open_write_session`` (not
``open_session``) so writes serialize through ``_SQLITE_WRITE_LOCK`` and
the lease state mutation + event append commit atomically.

The old code split a read + mutate + commit across ``open_session`` so a
concurrent complete on the same queue item could land in the middle of
another's append_event window, producing wrong-state races or SQLite
"database is locked" failures.

These tests assert the new contract:
- ``renew`` validates ``lease_ttl_seconds`` (30..3600).
- Two concurrent ``complete`` calls on the same queue item serialize;
  the second one fails with "invalid or expired lease".
- ``fail(requeue=True)`` flips state to "queued", clears lease fields,
  and bumps attempts — observable as a single coherent row.
- ``complete`` against an expired lease raises "invalid or expired lease".
"""

from __future__ import annotations

import threading
from datetime import timedelta
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
        "scheduler": {"summary": {"task_id": "task-1"}, "assignment": {"agent_id": agent}},
    }


def test_queue_renew_validates_ttl(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    coordinator = QueueCoordinator(context)
    queued = coordinator.enqueue_pipeline_result(pipeline_result())
    claimed = coordinator.claim(agent_id="codex", server_instance_id="instance-a")

    assert claimed is not None
    assert claimed["queue_item_id"] == queued["queue_item_id"]

    with pytest.raises(ValueError, match="lease_ttl_seconds must be between 30 and 3600"):
        coordinator.renew(
            queue_item_id=claimed["queue_item_id"],
            lease_id=claimed["lease_id"],
            server_instance_id="instance-a",
            lease_ttl_seconds=29,
        )

    with pytest.raises(ValueError, match="lease_ttl_seconds must be between 30 and 3600"):
        coordinator.renew(
            queue_item_id=claimed["queue_item_id"],
            lease_id=claimed["lease_id"],
            server_instance_id="instance-a",
            lease_ttl_seconds=3601,
        )

    renewed = coordinator.renew(
        queue_item_id=claimed["queue_item_id"],
        lease_id=claimed["lease_id"],
        server_instance_id="instance-a",
        lease_ttl_seconds=120,
    )
    assert renewed["state"] == "leased"


def test_queue_complete_concurrent_lock_serializes(tmp_path: Path) -> None:
    """Two threads call complete on the same leased queue item. Exactly one
    must succeed; the other must raise "invalid or expired lease" — not
    SQLite "database is locked" or wrong-state corruption.
    """
    context = make_context(tmp_path)
    coordinator = QueueCoordinator(context)
    _queued = coordinator.enqueue_pipeline_result(pipeline_result())
    claimed = coordinator.claim(agent_id="codex", server_instance_id="instance-a")
    assert claimed is not None

    barrier = threading.Barrier(2)
    results: list[dict | Exception] = []

    def compete() -> None:
        try:
            barrier.wait(timeout=5.0)
            res = coordinator.complete(
                queue_item_id=claimed["queue_item_id"],
                lease_id=claimed["lease_id"],
                server_instance_id="instance-a",
                output=f"output-{threading.get_ident()}",
                artifacts=[],
            )
            results.append(res)
        except Exception as exc:  # noqa: BLE001 — we want all failures
            results.append(exc)

    t1 = threading.Thread(target=compete, daemon=True)
    t2 = threading.Thread(target=compete, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=10.0)
    t2.join(timeout=10.0)

    successes = [r for r in results if isinstance(r, dict)]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1, f"exactly one complete must succeed — got {results!r}"
    assert successes[0]["state"] == "completed"
    assert len(failures) == 1
    assert "invalid or expired lease" in str(failures[0]), (
        f"second complete must fail with lease error — got {failures[0]!r}"
    )


def test_queue_fail_requeues_atomically(tmp_path: Path) -> None:
    """fail(requeue=True) flips state to "queued", clears lease fields,
    and emits TASK_FAILED + TASK_REQUEUED events in one write transaction.
    attempts is NOT incremented by fail — it was already bumped by claim().
    """
    context = make_context(tmp_path, agent="claude", instance="instance-b")
    coordinator = QueueCoordinator(context)
    _queued = coordinator.enqueue_pipeline_result(pipeline_result(agent="claude"))
    claimed = coordinator.claim(agent_id="claude", server_instance_id="instance-b")
    assert claimed is not None
    claimed_attempts = claimed["attempts"]

    failed = coordinator.fail(
        queue_item_id=claimed["queue_item_id"],
        lease_id=claimed["lease_id"],
        server_instance_id="instance-b",
        reason="boom",
        requeue=True,
    )
    assert failed["state"] == "queued", f"expected requeued — got {failed!r}"
    assert failed["lease_id"] is None
    assert failed["lease_expires_at"] is None
    assert failed["attempts"] == claimed_attempts, "fail() must not re-increment attempts — claim already bumped it"

    # Re-fetch the row and check internal fields the public dict does not expose.
    from allbrain.models.entities import QueueItemRecord
    from allbrain.storage.database import open_session

    with open_session(context.repository.engine) as db:
        record = db.get(QueueItemRecord, claimed["queue_item_id"])
        assert record is not None
        assert record.leased_by is None, "leased_by must be cleared on requeue"

    events = context.repository.list_events(project_path=context.project_path, limit=200)
    types = {e.type for e in events}
    assert EventType.TASK_FAILED.value in types
    assert EventType.TASK_REQUEUED.value in types


def test_lease_expiry_race_complete(tmp_path: Path) -> None:
    """An explicit complete against an expired lease must raise
    "lease has expired" — it cannot silently succeed and corrupt state.
    """
    context = make_context(tmp_path)
    coordinator = QueueCoordinator(context)
    _queued = coordinator.enqueue_pipeline_result(pipeline_result())
    claimed = coordinator.claim(agent_id="codex", server_instance_id="instance-a")
    assert claimed is not None

    # Forcefully expire the lease by setting lease_expires_at to the past.
    from allbrain.models.entities import QueueItemRecord
    from allbrain.storage.database import open_write_session

    with open_write_session(context.repository.engine) as db:
        record = db.get(QueueItemRecord, claimed["queue_item_id"])
        assert record is not None
        from allbrain.models.entities import utc_now

        record.lease_expires_at = utc_now() - timedelta(seconds=1)
        db.add(record)

    with pytest.raises(ValueError, match="lease has expired"):
        coordinator.complete(
            queue_item_id=claimed["queue_item_id"],
            lease_id=claimed["lease_id"],
            server_instance_id="instance-a",
            output="late",
            artifacts=[],
        )
