"""Concurrent integration tests for QueueCoordinator and SnapshotRepo.

Targeting concurrency gap coverage (Faz B):
1. QueueCoordinator.enqueue_task idempotency race under contention (IntegrityError catch path).
2. QueueCoordinator.claim contention across multiple worker threads (rowcount/retry path).
3. QueueCoordinator.renew and complete concurrent lease operations.
4. SnapshotRepo concurrent snapshot writes.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytest

from allbrain.server.context import BrainContext
from allbrain.server.queueing import QueueCoordinator
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from allbrain.storage.snapshot_repo import SnapshotRepo


def _make_context(tmp_path: Path, name: str = "queue-test") -> BrainContext:
    engine = create_engine_for_path(tmp_path / f"{name}.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / name
    project_root.mkdir(exist_ok=True)
    session = repo.create_session(project_root, name)
    return BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        active_session=session,
    )


def test_concurrent_enqueue_same_idempotency_key(tmp_path: Path) -> None:
    """10 threads enqueue the exact same task idempotency key simultaneously.

    Must not crash, must trigger the IntegrityError fallback, and all threads
    must return the exact same queue_item_id.
    """
    ctx = _make_context(tmp_path, "same-key")
    coordinator = QueueCoordinator(ctx)

    results: list[dict[str, Any]] = []
    errors: list[str] = []

    def _enqueue_worker(tid: int) -> dict[str, Any] | None:
        try:
            return coordinator.enqueue_task(
                task_id="task-100",
                goal="Process batch data",
                agent_id="worker-codex",
                workflow_id="wf-shared",
                node_id="node-1",
                idempotency_prefix="batch-test",
            )
        except Exception as exc:
            errors.append(f"tid={tid} err={exc}")
            return None

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_enqueue_worker, tid) for tid in range(10)]
        for f in as_completed(futures):
            res = f.result()
            if res is not None:
                results.append(res)

    assert not errors, f"Enqueue raised unexpected errors: {errors}"
    assert len(results) == 10, "All 10 workers should receive a result record"

    first_id = results[0]["queue_item_id"]
    for r in results:
        assert r["queue_item_id"] == first_id, "All concurrent enqueues must resolve to the identical record ID"


def test_concurrent_claim_exclusive_lease(tmp_path: Path) -> None:
    """10 workers compete concurrently to claim a single queued item.

    Exactly ONE worker must successfully acquire the lease. The other 9 must return None.
    """
    ctx = _make_context(tmp_path, "claim-race")
    coordinator = QueueCoordinator(ctx)

    # 1 item in queue
    item = coordinator.enqueue_task(
        task_id="unique-task-1",
        goal="Single runner task",
        agent_id="agent-pool",
        workflow_id="wf-claim",
    )
    assert item is not None

    claims: list[dict[str, Any]] = []

    def _claim_worker(worker_id: int) -> dict[str, Any] | None:
        return coordinator.claim(
            agent_id="agent-pool",
            server_instance_id=f"server-{worker_id}",
            workflow_id="wf-claim",
            lease_ttl_seconds=120,
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_claim_worker, w) for w in range(10)]
        for f in as_completed(futures):
            res = f.result()
            if res is not None:
                claims.append(res)

    assert len(claims) == 1, f"Expected exactly 1 claim, got {len(claims)}"
    assert claims[0]["queue_item_id"] == item["queue_item_id"]
    assert claims[0]["state"] == "leased"


def test_concurrent_enqueue_distinct_keys(tmp_path: Path) -> None:
    """15 threads enqueue distinct tasks concurrently.

    All 15 tasks must be created with distinct IDs.
    """
    ctx = _make_context(tmp_path, "distinct-keys")
    coordinator = QueueCoordinator(ctx)

    results: list[dict[str, Any]] = []

    def _worker(tid: int) -> dict[str, Any]:
        return coordinator.enqueue_task(
            task_id=f"task-distinct-{tid}",
            goal=f"Distinct goal {tid}",
            agent_id=f"agent-{tid % 3}",
            workflow_id="wf-bulk",
        )

    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = [pool.submit(_worker, tid) for tid in range(15)]
        for f in as_completed(futures):
            results.append(f.result())

    ids = [r["queue_item_id"] for r in results]
    assert len(ids) == 15
    assert len(set(ids)) == 15, "All task IDs must be distinct"


def test_concurrent_claim_and_complete_lifecycle(tmp_path: Path) -> None:
    """Multiple tasks queued, multiple workers claiming and completing concurrently."""
    ctx = _make_context(tmp_path, "lifecycle")
    coordinator = QueueCoordinator(ctx)

    for i in range(10):
        coordinator.enqueue_task(
            task_id=f"life-task-{i}",
            goal=f"Lifecycle goal {i}",
            agent_id="worker-swarm",
            workflow_id="wf-life",
        )

    def _worker(worker_id: int) -> int:
        count = 0
        while True:
            claimed = coordinator.claim(
                agent_id="worker-swarm",
                server_instance_id=f"worker-{worker_id}",
                workflow_id="wf-life",
                lease_ttl_seconds=60,
            )
            if claimed is None:
                break
            res = coordinator.complete(
                queue_item_id=claimed["queue_item_id"],
                lease_id=claimed["lease_id"],
                server_instance_id=f"worker-{worker_id}",
                output=f"Done by {worker_id}",
                artifacts=[],
            )
            if res["state"] == "completed":
                count += 1
        return count

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_worker, w) for w in range(5)]
        total_completed = sum(f.result() for f in as_completed(futures))

    assert total_completed == 10, f"Expected all 10 tasks to be completed, got {total_completed}"


def test_concurrent_snapshot_writes(tmp_path: Path) -> None:
    """Multiple threads attempting to write point-in-time snapshots concurrently."""
    engine = create_engine_for_path(tmp_path / "snap.db")
    init_db(engine)
    repo = SnapshotRepo(engine)

    written: list[Any] = []
    errors: list[str] = []

    def _snap_worker(tid: int) -> Any | None:
        try:
            return repo.save(
                project_id=1,
                event_cursor=f"cursor-{tid}",
                state={"worker": tid, "metrics": [1, 2, 3]},
                metadata={"source": f"thread-{tid}"},
            )
        except Exception as exc:
            errors.append(f"tid={tid} exc={exc}")
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_snap_worker, t) for t in range(8)]
        for f in as_completed(futures):
            res = f.result()
            if res is not None:
                written.append(res)

    assert not errors, f"Unexpected snapshot error: {errors}"
    assert len(written) == 8, "All 8 concurrent snapshots should succeed under SQLite WAL"
