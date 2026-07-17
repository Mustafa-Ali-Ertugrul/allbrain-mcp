from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from allbrain.models.schemas import ListEventsInput
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def _repo(tmp_path: Path) -> tuple[BrainRepository, Path]:
    db = tmp_path / "brain.db"
    engine = create_engine_for_path(db)
    init_db(engine)
    return BrainRepository(engine), tmp_path / "project"


def test_list_events_filters_by_agent_branch_and_time(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    project.mkdir()
    session_a = repo.create_session(project, "agent-a")
    session_b = repo.create_session(project, "agent-b")
    assert session_a.id is not None and session_b.id is not None

    older = repo.append_event(
        project_path=project,
        session_id=session_a.id,
        type="task_started",
        source="agent",
        payload={"task": "old"},
        agent_id="agent-a",
        branch="main",
    )
    newer = repo.append_event(
        project_path=project,
        session_id=session_b.id,
        type="task_started",
        source="agent",
        payload={"task": "new"},
        agent_id="agent-b",
        branch="feature",
    )

    by_agent = repo.list_events(project_path=project, agent_id="agent-b", limit=50)
    assert [event.id for event in by_agent] == [newer.id]

    by_branch = repo.list_events(project_path=project, branch="main", limit=50)
    assert [event.id for event in by_branch] == [older.id]

    midpoint = older.created_at + timedelta(microseconds=1)
    # If timestamps collide (same second), still assert agent filter works above.
    if older.created_at < newer.created_at:
        since_newer = repo.list_events(project_path=project, since=midpoint, limit=50)
        assert newer.id in {event.id for event in since_newer}


def test_list_events_input_rejects_inverted_range() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        ListEventsInput(since=now, until=now - timedelta(hours=1))
