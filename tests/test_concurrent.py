"""Test concurrent access patterns with SQLite WAL mode.

WAL + synchronous=NORMAL + busy_timeout=5000 enables
concurrent reads and limited concurrent writes without
"database is locked" errors.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from allbrain.server.app import (
    create_task_impl,
    list_events_impl,
    save_event_impl,
)
from allbrain.storage import BrainRepository, create_engine_for_path, init_db

from .test_server import make_context


def _shared_context(tmp_path: Path) -> "BrainContext":  # noqa: F821
    """Create a single shared context for all threads to use."""
    from allbrain.server import BrainContext

    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, "codex")
    return BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        active_session=session,
    )


def test_concurrent_save_event_no_deadlock(tmp_path: Path) -> None:
    """20 threads, 100 events each = 2000 events total."""
    context = _shared_context(tmp_path)
    errors: list[str] = []

    def _write_events(thread_id: int) -> int:
        count = 0
        for i in range(100):
            result = save_event_impl(
                context,
                type="file_modified",
                payload={"thread": thread_id, "seq": i},
                source="concurrent_test",
            )
            if result.ok:
                count += 1
            else:
                errors.append(f"thread={thread_id} seq={i} err={result.error}")
        return count

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(_write_events, tid) for tid in range(20)]
        total = sum(f.result() for f in as_completed(futures))

    assert total == 2000, f"expected 2000 events, got {total}"
    assert not errors, f"errors: {errors[:5]}"

    listed = context.repository.list_events(project_path=context.project_path, limit=50000)
    assert len(listed) >= 2000


def test_concurrent_create_task(tmp_path: Path) -> None:
    """10 threads creating tasks concurrently."""
    context = _shared_context(tmp_path)
    errors: list[str] = []

    def _make_task(tid: int) -> bool:
        result = create_task_impl(context, goal=f"task from thread {tid}")
        if not result.ok:
            errors.append(f"thread={tid} err={result.error}")
        return result.ok

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_make_task, tid) for tid in range(10)]
        results = [f.result() for f in as_completed(futures)]

    assert all(results), f"errors: {errors[:5]}"


def test_concurrent_read_during_write(tmp_path: Path) -> None:
    """1 thread writes while another reads — WAL allows reads during writes."""
    context = _shared_context(tmp_path)

    def _writer() -> int:
        count = 0
        for i in range(200):
            result = save_event_impl(context, type="file_modified", payload={"seq": i}, source="writer")
            if result.ok:
                count += 1
        return count

    def _reader() -> int:
        total = 0
        for _ in range(20):
            events = context.repository.list_events(project_path=context.project_path)
            total += len(events)
        return total

    with ThreadPoolExecutor(max_workers=2) as pool:
        w_future = pool.submit(_writer)
        r_future = pool.submit(_reader)
        written = w_future.result()
        read_total = r_future.result()

    assert written == 200
    assert read_total > 0


def test_no_duplicate_event_ids(tmp_path: Path) -> None:
    """Concurrent write should not produce duplicate UUID7 IDs."""
    context = _shared_context(tmp_path)

    def _write(tid: int) -> list[str]:
        ids: list[str] = []
        for i in range(50):
            result = save_event_impl(
                context, type="file_modified", payload={"tid": tid, "seq": i}, source="dup_test"
            )
            if result.ok:
                ids.append(result.data["id"])
        return ids

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_write, tid) for tid in range(10)]
        all_ids: list[str] = []
        for f in as_completed(futures):
            all_ids.extend(f.result())

    assert len(all_ids) == len(set(all_ids)), "duplicate event IDs detected"


def test_timestamp_ordering(tmp_path: Path) -> None:
    """Concurrently written events should maintain monotonic order by ID."""
    context = _shared_context(tmp_path)

    def _write(tid: int) -> int:
        count = 0
        for i in range(50):
            result = save_event_impl(
                context, type="file_modified", payload={"tid": tid, "seq": i}, source="order_test"
            )
            if result.ok:
                count += 1
        return count

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_write, tid) for tid in range(10)]
        for f in as_completed(futures):
            f.result()

    events = context.repository.list_events(project_path=context.project_path, limit=50000)
    event_ids = [e.id for e in events]
    # UUID7 is time-sortable; list_events returns sorted by event.id
    assert event_ids == sorted(event_ids), "event IDs are not monotonically ordered"


def test_concurrent_mixed_operations(tmp_path: Path) -> None:
    """Mix of save_event, create_task, and list_events concurrently."""
    context = _shared_context(tmp_path)

    def _save(tid: int) -> int:
        count = 0
        for _ in range(30):
            r = save_event_impl(context, type="file_modified", payload={"tid": tid}, source="mix")
            if r.ok:
                count += 1
        return count

    def _create(tid: int) -> int:
        count = 0
        for _ in range(10):
            r = create_task_impl(context, goal=f"mix task {tid}")
            if r.ok:
                count += 1
        return count

    def _list(tid: int) -> int:
        total = 0
        for _ in range(10):
            events = context.repository.list_events(project_path=context.project_path)
            total += len(events)
        return total

    with ThreadPoolExecutor(max_workers=15) as pool:
        savers = [pool.submit(_save, tid) for tid in range(5)]
        creators = [pool.submit(_create, tid) for tid in range(5)]
        listers = [pool.submit(_list, tid) for tid in range(5)]
        saved = sum(f.result() for f in as_completed(savers))
        created = sum(f.result() for f in as_completed(creators))
        list_counts = [f.result() for f in as_completed(listers)]

    assert saved == 150
    assert created == 50
    # list_events should never crash, even during concurrent writes
    assert all(c >= 0 for c in list_counts)
