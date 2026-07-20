"""Test concurrent access patterns with SQLite WAL mode.

WAL + synchronous=NORMAL + busy_timeout=5000 enables
concurrent reads and limited concurrent writes without
"database is locked" errors.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytest

from allbrain.server.tools.events import (
    list_events_impl,
    save_event_impl,
)
from allbrain.server.tools.tasks import create_task_impl
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
    """5 threads, 20 events each = 100 events total (reduced from 20×100 to avoid 179s runtime)."""
    context = _shared_context(tmp_path)
    errors: list[str] = []

    def _write_events(thread_id: int) -> int:
        count = 0
        for i in range(20):
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

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_write_events, tid) for tid in range(5)]
        total = sum(f.result() for f in as_completed(futures))

    assert total == 100, f"expected 100 events, got {total}"
    assert not errors, f"errors: {errors[:5]}"

    listed = context.repository.list_events(project_path=context.project_path, limit=50000)
    assert len(listed) >= 100


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
            result = save_event_impl(context, type="file_modified", payload={"tid": tid, "seq": i}, source="dup_test")
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
            result = save_event_impl(context, type="file_modified", payload={"tid": tid, "seq": i}, source="order_test")
            if result.ok:
                count += 1
        return count

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_write, tid) for tid in range(10)]
        for f in as_completed(futures):
            f.result()

    events = context.repository.list_events(project_path=context.project_path, limit=50000)
    event_ids = [e.id for e in events]
    # list_events returns events ordered by stream_position
    assert event_ids == sorted(event_ids), "event IDs are not monotonically ordered"


def test_active_session_ensure_concurrent(tmp_path: Path) -> None:
    """Concurrent ensure_active_session calls must produce exactly one session.

    Only ensure_active_session is called — no explicit None sets.
    """
    from allbrain.server import BrainContext

    engine = create_engine_for_path(tmp_path / "brain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()

    context = BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        agent_name="multi",
    )
    assert context.active_session is None

    sessions: list[Any] = []

    def _ensure(tid: int) -> None:
        for _ in range(20):
            sess = context.ensure_active_session()
            sessions.append(sess)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_ensure, tid) for tid in range(10)]
        for f in as_completed(futures):
            f.result()

    # All calls returned the same session object.
    first = sessions[0]
    assert first is not None
    assert all(s is first for s in sessions), "ensure_active_session must return same singleton"
    assert context.active_session is first
    assert context.active_session_id == first.id


def test_active_session_setter_under_contention(tmp_path: Path) -> None:
    """active_session setter must be atomic under concurrent writes.

    - 2 threads set active_session to None then restore.
    - 2 threads read active_session_id concurrently.
    - Must never crash, and final session must be valid.
    """
    from allbrain.server import BrainContext

    engine = create_engine_for_path(tmp_path / "brain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()

    context = BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        agent_name="multi",
    )
    sess = context.ensure_active_session()
    assert sess is not None

    errors: list[str] = []

    def _setter(tid: int) -> None:
        for _ in range(50):
            old = context.active_session  # locked getter
            context.active_session = None  # locked setter
            context.active_session = old  # locked setter

    def _reader(tid: int) -> None:
        for _ in range(50):
            try:
                _sid = context.active_session_id  # locked getter
            except Exception as exc:
                errors.append(f"r{tid}: {exc}")

    with ThreadPoolExecutor(max_workers=4) as pool:
        setters = [pool.submit(_setter, t) for t in range(2)]
        readers = [pool.submit(_reader, t) for t in range(2)]
        for f in as_completed(setters + readers):
            f.result()

    assert not errors, f"reader errors: {errors[:5]}"
    # The session must still be valid after all contention.
    assert context.active_session is not None
    assert context.active_session_id is not None
    assert context.active_session_id == sess.id


def test_agent_name_concurrent_read_write(tmp_path: Path) -> None:
    """agent_name property must be thread-safe under concurrent R/W."""
    from allbrain.server import BrainContext

    engine = create_engine_for_path(tmp_path / "brain.db")
    init_db(engine)
    repo = BrainRepository(engine)

    context = BrainContext(repository=repo, project_path=str(tmp_path / "project"), agent_name="initial")
    assert context.agent_name == "initial"
    errors: list[str] = []

    def _writer(tid: int) -> None:
        for _ in range(50):
            context.agent_name = f"writer-{tid}"

    def _reader(tid: int) -> None:
        for _ in range(50):
            try:
                _name = context.agent_name
                assert isinstance(_name, str)
            except Exception as exc:
                errors.append(f"r{tid}: {exc}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        writers = [pool.submit(_writer, t) for t in range(3)]
        readers = [pool.submit(_reader, t) for t in range(3)]
        for f in as_completed(writers + readers):
            f.result()

    assert not errors, f"reader errors: {errors[:5]}"
    # Must be some writer's name, never None.
    final = context.agent_name
    assert final.startswith("writer-")


def test_client_info_concurrent(tmp_path: Path) -> None:
    """client_name / client_version must be thread-safe under concurrent writes."""
    from allbrain.server import BrainContext

    engine = create_engine_for_path(tmp_path / "brain.db")
    init_db(engine)
    repo = BrainRepository(engine)

    context = BrainContext(repository=repo, project_path=str(tmp_path / "project"))
    errors: list[str] = []

    def _setter(tid: int) -> None:
        for i in range(30):
            context.set_client_info(f"client-{tid}-{i}", f"v{tid}.{i}")

    def _reader(tid: int) -> None:
        for _ in range(30):
            try:
                _cn = context.client_name
                _cv = context.client_version
            except Exception as exc:
                errors.append(f"r{tid}: {exc}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        setters = [pool.submit(_setter, t) for t in range(3)]
        readers = [pool.submit(_reader, t) for t in range(3)]
        for f in as_completed(setters + readers):
            f.result()

    assert not errors, f"reader errors: {errors[:5]}"
    # Must never be None (set_client_info only writes when truthy)
    assert context.client_name is not None
    assert context.client_version is not None


def test_git_baseline_concurrent(tmp_path: Path) -> None:
    """git_baseline property must be thread-safe under concurrent R/W."""
    from allbrain.server import BrainContext

    engine = create_engine_for_path(tmp_path / "brain.db")
    init_db(engine)
    repo = BrainRepository(engine)

    context = BrainContext(repository=repo, project_path=str(tmp_path / "project"))
    assert context.git_baseline is None
    errors: list[str] = []

    def _writer(tid: int) -> None:
        for i in range(30):
            context.git_baseline = {"version": f"{tid}.{i}", "files": {f"f{tid}_{i}": "hash"}}

    def _reader(tid: int) -> None:
        for _ in range(30):
            try:
                _gb = context.git_baseline
            except Exception as exc:
                errors.append(f"r{tid}: {exc}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        writers = [pool.submit(_writer, t) for t in range(3)]
        readers = [pool.submit(_reader, t) for t in range(3)]
        for f in as_completed(writers + readers):
            f.result()

    assert not errors, f"reader errors: {errors[:5]}"
    # git_baseline must be a valid dict, not corrupted.
    final = context.git_baseline
    assert final is not None
    assert "version" in final
    assert "files" in final


def test_active_session_id_toctou(tmp_path: Path) -> None:
    """active_session_id must not return stale id after session replaced.

    Single lock acquisition in the property prevents TOCTOU.
    """
    from allbrain.server import BrainContext

    engine = create_engine_for_path(tmp_path / "brain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()

    context = BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        agent_name="toctou-test",
    )
    sess1 = context.ensure_active_session()
    assert sess1 is not None

    def _swapper() -> None:
        for _ in range(20):
            s = context.ensure_active_session()
            context.active_session = s  # self-set (no-op but exercises setter)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_swapper) for _ in range(4)]
        for f in as_completed(futures):
            f.result()

    # After all swaps, active_session_id must match the active session.
    assert context.active_session_id == context.active_session.id


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


def test_concurrent_save_event_stress(tmp_path: Path) -> None:
    """Stress test: 20 threads × 50 events = 1000 total events concurrently.

    Verifies SQLite WAL mode + busy_timeout=30000 handles high-contention
    concurrent writes without deadlock, data loss, or IntegrityError.
    """
    context = _shared_context(tmp_path)
    errors: list[str] = []

    def _write_events(thread_id: int) -> int:
        count = 0
        for i in range(50):
            result = save_event_impl(
                context,
                type="file_modified",
                payload={"thread": thread_id, "seq": i},
                source="stress_test",
            )
            if result.ok:
                count += 1
            else:
                errors.append(f"thread={thread_id} seq={i} err={result.error}")
        return count

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(_write_events, tid) for tid in range(20)]
        total = sum(f.result() for f in as_completed(futures))

    assert not errors, f"errors during concurrent stress write: {errors[:5]}"
    assert total == 1000, f"expected 1000 events saved, got {total}"

    # save_event_impl also emits an audit tool_call event per invocation (2000 total)
    saved_events = context.repository.list_events(
        project_path=context.project_path,
        type="file_modified",
        limit=50000,
    )
    assert len(saved_events) == 1000, f"expected 1000 file_modified events, got {len(saved_events)}"


def test_concurrent_multi_agent_same_db(tmp_path: Path) -> None:
    """5 concurrent agents writing to the same database.

    Verifies 5 distinct agent sessions can write concurrently to the same repository
    without cross-agent event contamination or attribution mismatch.
    """
    from allbrain.server import BrainContext

    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()

    agent_contexts = {}
    for i in range(5):
        agent_name = f"agent-{i}"
        session = repo.create_session(project_root, agent_name)
        agent_contexts[i] = BrainContext(
            repository=repo,
            project_path=str(project_root.resolve()),
            active_session=session,
            agent_name=agent_name,
        )

    errors: list[str] = []

    def _agent_worker(agent_idx: int) -> int:
        ctx = agent_contexts[agent_idx]
        count = 0
        agent_name = f"agent-{agent_idx}"
        for i in range(20):
            result = save_event_impl(
                ctx,
                type="task_created",
                payload={"agent": agent_name, "seq": i},
                source=agent_name,
                agent_id=agent_name,
            )
            if result.ok:
                count += 1
            else:
                errors.append(f"agent={agent_name} seq={i} err={result.error}")
        return count

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_agent_worker, i) for i in range(5)]
        total = sum(f.result() for f in as_completed(futures))

    assert not errors, f"errors during multi-agent concurrent writes: {errors[:5]}"
    assert total == 100, f"expected 100 total events, got {total}"

    task_events = repo.list_events(
        project_path=str(project_root.resolve()),
        type="task_created",
        limit=50000,
    )
    assert len(task_events) == 100, f"expected 100 task_created events, got {len(task_events)}"

    for i in range(5):
        agent_name = f"agent-{i}"
        agent_events = repo.list_events(
            project_path=str(project_root.resolve()),
            agent_id=agent_name,
            type="task_created",
            limit=50000,
        )
        assert len(agent_events) == 20, f"expected 20 events for {agent_name}, got {len(agent_events)}"
        for event in agent_events:
            assert event.agent_id == agent_name
            assert event.payload["agent"] == agent_name


def test_concurrent_snapshot_during_write(tmp_path: Path) -> None:
    """Snapshot creation concurrent with active event writes.

    Verifies create_snapshot_impl executes cleanly mid-stream under concurrent write
    load, producing consistent snapshots and leaving all 100 written events intact.
    """
    from allbrain.server.tools.snapshots import create_snapshot_impl

    context = _shared_context(tmp_path)
    errors: list[str] = []
    snapshots: list[Any] = []

    def _writer(tid: int) -> int:
        count = 0
        for i in range(10):
            result = save_event_impl(
                context,
                type="task_created",
                payload={"writer": tid, "seq": i},
                source="snap_writer",
            )
            if result.ok:
                count += 1
            else:
                errors.append(f"writer={tid} seq={i} err={result.error}")
        return count

    def _snapshot_runner() -> int:
        snap_count = 0
        for _ in range(5):
            res = create_snapshot_impl(context, force=True, limit=5000)
            if res.ok:
                snap_count += 1
                snapshots.append(res.data)
            else:
                errors.append(f"snapshot err={res.error}")
        return snap_count

    with ThreadPoolExecutor(max_workers=11) as pool:
        writer_futures = [pool.submit(_writer, tid) for tid in range(10)]
        snap_future = pool.submit(_snapshot_runner)

        total_written = sum(f.result() for f in as_completed(writer_futures))
        total_snaps = snap_future.result()

    assert not errors, f"errors during concurrent snapshot/write: {errors[:5]}"
    assert total_written == 100, f"expected 100 written events, got {total_written}"
    assert total_snaps > 0, "at least one snapshot must succeed"

    written_events = context.repository.list_events(
        project_path=context.project_path,
        type="task_created",
        limit=50000,
    )
    assert len(written_events) == 100, f"expected 100 task_created events, got {len(written_events)}"

    for snap_data in snapshots:
        assert snap_data is not None
        assert "event_cursor" in snap_data or "id" in snap_data or "metadata" in snap_data
