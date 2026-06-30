from datetime import UTC, datetime, timezone
from pathlib import Path

from allbrain.models.entities import Event
from allbrain.storage import BrainRepository, create_engine_for_path, init_db, open_session


def make_repository(tmp_path: Path) -> BrainRepository:
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    return BrainRepository(engine)


def test_get_or_create_project_uses_canonical_path(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)
    project_root = tmp_path / "project"
    project_root.mkdir()

    with open_session(repo.engine) as db:
        first = repo.get_or_create_project(db, project_root)
        second = repo.get_or_create_project(db, project_root / ".." / "project")

    assert first.id == second.id
    assert first.canonical_project_path == second.canonical_project_path


def test_append_event_requires_existing_session(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)
    project_root = tmp_path / "project"
    project_root.mkdir()

    try:
        repo.append_event(
            project_path=project_root,
            session_id=404,
            type="file_modified",
            source="agent",
            payload={},
        )
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("Expected invalid session_id to fail")


def test_events_are_listed_in_stable_order(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, "codex")

    first = repo.append_event(
        project_path=project_root,
        session_id=session.id or 0,
        type="first",
        source="agent",
        payload={"n": 1},
    )
    second = repo.append_event(
        project_path=project_root,
        session_id=session.id or 0,
        type="second",
        source="agent",
        payload={"n": 2},
    )

    events = repo.list_events(project_path=project_root)

    assert [event.id for event in events] == [first.id, second.id]
    assert first.id < second.id


def test_list_events_returns_latest_limit_in_chronological_order(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, "codex")

    for index in range(5):
        repo.append_event(
            project_path=project_root,
            session_id=session.id or 0,
            type="file_modified",
            source="agent",
            payload={"index": index},
            file_path=f"file_{index}.py",
        )

    events = repo.list_events(project_path=project_root, limit=3)

    assert [event.payload["index"] for event in events] == [2, 3, 4]


def test_quality_gate_uuidv7_ordering_uses_created_at_tie_break(tmp_path: Path) -> None:
    repo = make_repository(tmp_path)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, "codex")

    first = repo.append_event(
        project_path=project_root,
        session_id=session.id or 0,
        type="file_modified",
        source="agent",
        payload={"index": 1},
        file_path="first.py",
    )
    second = repo.append_event(
        project_path=project_root,
        session_id=session.id or 0,
        type="file_modified",
        source="agent",
        payload={"index": 2},
        file_path="second.py",
    )

    same_timestamp = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    with open_session(repo.engine) as db:
        first_row = db.get(Event, first.id)
        second_row = db.get(Event, second.id)
        assert first_row is not None
        assert second_row is not None
        first_row.created_at = same_timestamp
        second_row.created_at = same_timestamp
        db.add(first_row)
        db.add(second_row)
        db.commit()

    events = repo.list_events(project_path=project_root)

    assert first.id < second.id
    assert [event.id for event in events] == [first.id, second.id]


def test_payload_version_column_backfilled_on_old_schema(tmp_path: Path) -> None:
    from allbrain.config import canonicalize_project_path
    from allbrain.foundations.versioning import current_payload_version
    from allbrain.storage import (
        BrainRepository,
        create_engine_for_path,
        ensure_event_payload_version_column,
        open_session,
    )

    engine = create_engine_for_path(tmp_path / "legacy.db")
    canonical_path = canonicalize_project_path(tmp_path / "legacy")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE event (
                id TEXT PRIMARY KEY,
                project_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                agent_id TEXT,
                type TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'agent',
                file_path TEXT,
                payload_json TEXT NOT NULL,
                task_hint TEXT,
                importance INTEGER,
                impact_score REAL,
                caused_by TEXT,
                branch TEXT,
                created_at TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE TABLE project (id INTEGER PRIMARY KEY, canonical_project_path TEXT UNIQUE, name TEXT, "
            "created_at TIMESTAMP, updated_at TIMESTAMP)"
        )
        conn.exec_driver_sql(
            "INSERT INTO project (id, canonical_project_path, name) VALUES (1, ?, 'legacy')",
            (canonical_path,),
        )
        conn.exec_driver_sql(
            "CREATE TABLE session (id INTEGER PRIMARY KEY, project_id INTEGER, agent_name TEXT, "
            "started_at TIMESTAMP, ended_at TIMESTAMP, status TEXT)"
        )
        conn.exec_driver_sql("INSERT INTO session (id, project_id, agent_name) VALUES (1, 1, 'legacy')")
        conn.exec_driver_sql(
            "INSERT INTO event (id, project_id, session_id, type, source, payload_json, created_at) "
            "VALUES ('legacy-evt-1', 1, 1, 'legacy_event', 'legacy', '{\"old\": true}', '2024-01-01 00:00:00')"
        )

    ensure_event_payload_version_column(engine)
    ensure_event_payload_version_column(engine)

    with open_session(engine) as db:
        row = db.get(Event, "legacy-evt-1")
        assert row is not None
        assert row.payload_version == 1

    repo = BrainRepository(engine)
    events = repo.list_events(project_path=tmp_path / "legacy", session_id=1)
    assert len(events) == 1
    assert events[0].id == "legacy-evt-1"
    assert events[0].payload == {"old": True}
    assert events[0].payload_version == current_payload_version()
