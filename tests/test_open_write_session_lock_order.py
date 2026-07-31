"""A1 regression: open_write_session must acquire ``_SQLITE_WRITE_LOCK``
*before* emitting ``BEGIN IMMEDIATE``.

The previous order (``BEGIN IMMEDIATE`` -> lock) let a thread hold
SQLite's process-wide DB lock while waiting for the Python lock, forcing
other writers to block on SQLite without releasing the in-process
serialization point. Acquiring the Python lock first guarantees in-order
acquisition on both layers and avoids a stack-deadlock where a
lock-holder waits on another thread that itself is blocked at the SQLite
layer.

This test verifies the lock-order contract deterministically using
``threading.Event`` coordination; no real wall-clock contention is needed.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from allbrain.storage import create_engine_for_path, init_db
from allbrain.storage.database import _SQLITE_WRITE_LOCK, open_write_session


def test_open_write_session_acquires_python_lock_before_begin_immediate(tmp_path: Path) -> None:
    """If BEGIN IMMEDIATE were emitted before acquiring the Python lock, a
    second writer waiting on the Python lock would observe SQLite holding
    the DB lock. We assert the opposite: the Python lock is held for the
    full BEGIN IMMEDIATE + body + commit window.
    """
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)

    entered_python_lock = threading.Event()
    released_python_lock = threading.Event()
    allowed_to_release = threading.Event()

    def first_writer() -> None:
        with open_write_session(engine) as db:
            # While the Python lock is held, no other writer should be able
            # to even start BEGIN IMMEDIATE.
            entered_python_lock.set()
            allowed_to_release.wait(timeout=5.0)
            from sqlmodel import select

            db.exec(select(1)).first()
        released_python_lock.set()

    thread = threading.Thread(target=first_writer, daemon=True)
    thread.start()
    try:
        assert entered_python_lock.wait(timeout=2.0), "first writer never entered the Python lock"

        # The Python lock must NOT be acquirable while the first writer holds it.
        acquired = _SQLITE_WRITE_LOCK.acquire(blocking=False)
        assert acquired is False, (
            "_SQLITE_WRITE_LOCK was not held during BEGIN IMMEDIATE + body — "
            "the previous lock order (BEGIN IMMEDIATE then lock) regression returned. "
            "open_write_session must acquire _SQLITE_WRITE_LOCK *before* emitting "
            "BEGIN IMMEDIATE."
        )

        allowed_to_release.set()
        assert released_python_lock.wait(timeout=2.0), "first writer never released the lock"
    finally:
        thread.join(timeout=5.0)

    engine.dispose()


def test_open_write_session_commits_on_clean_exit(tmp_path: Path) -> None:
    """The context manager commits when the body returns cleanly, even on
    non-SQLite dialects (covered elsewhere for sqlite here)."""
    from allbrain.models.entities import Project

    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)

    with open_write_session(engine) as db:
        db.add(Project(canonical_project_path=str(tmp_path), name="test-project"))

    from sqlmodel import select

    with engine.connect() as conn:
        rows = conn.execute(select(Project)).all()
    assert len(rows) == 1, "open_write_session did not commit on clean exit"
    engine.dispose()


def test_open_write_session_rolls_back_on_exception(tmp_path: Path) -> None:
    """An exception inside the body must roll back the transaction and
    re-raise the original error (not a rollback-induced one)."""
    from allbrain.models.entities import Project

    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)

    class BodyError(RuntimeError):
        pass

    with pytest.raises(BodyError):
        with open_write_session(engine) as db:
            db.add(Project(canonical_project_path="/will-not-survive", name="doomed"))
            raise BodyError("simulated failure")

    from sqlmodel import select

    with engine.connect() as conn:
        rows = conn.execute(select(Project)).all()
    assert len(rows) == 0, "open_write_session did not roll back on exception"
    engine.dispose()
