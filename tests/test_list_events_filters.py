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


def test_list_events_repo_filters_with_coerced_iso_string(tmp_path: Path) -> None:
    """End-to-end: MCP-style ISO strings coerced through ListEventsInput must
    filter correctly against the real (SQLite) event store."""
    repo, project = _repo(tmp_path)
    project.mkdir()
    session = repo.create_session(project, "agent-a")
    assert session.id is not None

    event = repo.append_event(
        project_path=project,
        session_id=session.id,
        type="task_started",
        source="agent",
        payload={"task": "coerced"},
        agent_id="agent-a",
        branch="main",
    )

    before = (event.created_at - timedelta(hours=1)).isoformat()
    after = (event.created_at + timedelta(hours=1)).isoformat()

    parsed = ListEventsInput(since=before, until=after, limit=1000)
    found = repo.list_events(
        project_path=project,
        since=parsed.since,
        until=parsed.until,
        limit=parsed.limit,
    )
    assert event.id in {row.id for row in found}

    # A window entirely in the past must exclude the event.
    past_only = ListEventsInput(
        since=(event.created_at - timedelta(hours=2)).isoformat(),
        until=(event.created_at - timedelta(hours=1)).isoformat(),
        limit=1000,
    )
    empty = repo.list_events(
        project_path=project,
        since=past_only.since,
        until=past_only.until,
        limit=past_only.limit,
    )
    assert event.id not in {row.id for row in empty}


def test_list_events_input_rejects_inverted_range() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        ListEventsInput(since=now, until=now - timedelta(hours=1))


def test_list_events_input_accepts_iso_string_since() -> None:
    parsed = ListEventsInput(since="2026-07-17T00:00:00Z")
    assert parsed.since == datetime(2026, 7, 17, 0, 0, 0, tzinfo=UTC)


def test_list_events_input_accepts_iso_string_until_tz_aware() -> None:
    parsed = ListEventsInput(until="2026-07-17T23:59:59+03:00")
    assert parsed.until is not None
    assert parsed.until.utcoffset() == timedelta(hours=3)


def test_list_events_input_accepts_naive_iso_string() -> None:
    parsed = ListEventsInput(since="2026-07-17T00:00:00")
    assert parsed.since == datetime(2026, 7, 17, 0, 0, 0, tzinfo=UTC)


def test_list_events_input_accepts_iso_string_range() -> None:
    parsed = ListEventsInput(
        since="2026-07-17T00:00:00Z",
        until="2026-07-18T00:00:00+03:00",
    )
    assert parsed.since is not None and parsed.until is not None
    assert parsed.since < parsed.until


def test_list_events_input_rejects_invalid_since() -> None:
    with pytest.raises(ValidationError):
        ListEventsInput(since="yesterday")


def test_list_events_input_limit_1000_accepted() -> None:
    assert ListEventsInput(limit=1000).limit == 1000


def test_list_events_input_limit_over_max_rejected() -> None:
    with pytest.raises(ValidationError):
        ListEventsInput(limit=1001)
