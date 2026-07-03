from __future__ import annotations

import multiprocessing
from pathlib import Path

from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from allbrain.storage.database import checkpoint_sqlite


def _write_events(db_path: str, project_path: str, agent: str, count: int, result_queue) -> None:
    engine = create_engine_for_path(db_path)
    repository = BrainRepository(engine)
    try:
        session = repository.create_session(project_path, agent)
        for index in range(count):
            repository.append_event(
                project_path=project_path,
                session_id=session.id,
                type="task_created",
                source=agent,
                payload={"agent": agent, "index": index},
            )
        result_queue.put((agent, None))
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - asserted in parent process
        result_queue.put((agent, repr(exc)))
    finally:
        repository.close()


def test_three_processes_share_sqlite_without_lock_failures(tmp_path: Path) -> None:
    db_path = tmp_path / "shared.db"
    project_path = tmp_path / "project"
    project_path.mkdir()
    engine = create_engine_for_path(db_path)
    init_db(engine)
    engine.dispose()

    process_context = multiprocessing.get_context("spawn")
    results = process_context.Queue()
    processes = [
        process_context.Process(
            target=_write_events,
            args=(str(db_path), str(project_path), agent, 20, results),
        )
        for agent in ("codex", "claude-code", "opencode")
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=45)
        assert process.exitcode == 0

    errors = dict(results.get(timeout=5) for _ in processes)
    assert errors == {"codex": None, "claude-code": None, "opencode": None}

    verification_engine = create_engine_for_path(db_path)
    repository = BrainRepository(verification_engine)
    try:
        events = repository.list_events(project_path=project_path, limit=1000)
        written = [event for event in events if event.source in errors]
        assert len(written) == 60
        assert {event.source for event in written} == set(errors)
        assert [event.stream_position for event in written] == list(range(1, 61))
        checkpoint = checkpoint_sqlite(verification_engine)
        assert checkpoint is not None and checkpoint[0] == 0
    finally:
        repository.close()
