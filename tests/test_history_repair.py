from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from allbrain.events import EventType
from allbrain.models.entities import Session, utc_now
from allbrain.storage import BrainRepository, create_engine_for_path, init_db, open_session
from allbrain.storage.history_repair import HistoryRepairer, _remap_payload_session_id


def test_history_payload_session_id_is_remapped_without_losing_legacy_id() -> None:
    payload = _remap_payload_session_id(
        '{"session_id": 5, "tool_name": "list_events"}', source_session_id=5, target_session_id=107
    )
    assert '"session_id": 107' in payload
    assert '"legacy_session_id": 5' in payload


def test_history_repair_merges_deduplicates_and_classifies(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source_path = tmp_path / ".allbrain-codex.db"
    source_engine = create_engine_for_path(source_path)
    init_db(source_engine)
    source_repo = BrainRepository(source_engine)
    source_session = source_repo.create_session(project, "codex")
    source_repo.append_event(
        project_path=project,
        session_id=source_session.id or 0,
        type=EventType.GOAL_SET.value,
        source="test",
        payload={"description": "merge this work"},
    )
    with open_session(source_engine) as db:
        stored = db.get(Session, source_session.id)
        assert stored is not None
        stored.last_heartbeat_at = utc_now() - timedelta(minutes=10)
        db.add(stored)
        db.commit()
    source_engine.dispose()

    target_path = tmp_path / ".allbrain.db"
    target_engine = create_engine_for_path(target_path)
    init_db(target_engine)
    repairer = HistoryRepairer(target_engine, project_path=str(project.resolve()), target_path=target_path)

    preview = repairer.inspect([source_path])
    assert preview["sources"][0]["events"] == 1
    first = repairer.apply([source_path])
    second = repairer.apply([source_path])

    assert first["merged"]["events"] == 1
    assert first["repaired"]["stale"] == 1
    assert first["baseline_snapshot_created"] is True
    assert second["merged"] == {"sessions": 0, "events": 0}
    sessions = repairer.repository.list_sessions(project_path=project)
    assert sessions[0].status == "stale"
    events = repairer.repository.list_session_events(sessions[0].id or 0)
    assert sum(event.type == EventType.GOAL_SET.value for event in events) == 1
    assert sum(event.type == EventType.SESSION_SUMMARY.value for event in events) == 1
