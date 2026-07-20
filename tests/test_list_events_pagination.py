from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from allbrain.models.schemas import (
    ListEventsInput,
    ListEventsPage,
    ListEventsSummary,
    UserInputError,
)
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def _repo(tmp_path: Path) -> tuple[BrainRepository, Path]:
    db = tmp_path / "brain.db"
    engine = create_engine_for_path(db)
    init_db(engine)
    return BrainRepository(engine), tmp_path / "project"


def _seed(repo: BrainRepository, project: Path, count: int, *, agent: str = "agent-a"):
    project.mkdir(exist_ok=True)
    session = repo.create_session(project, agent)
    assert session.id is not None
    created = []
    for i in range(count):
        ev = repo.append_event(
            project_path=project,
            session_id=session.id,
            type="task_started",
            source="agent",
            payload={"i": i},
            agent_id=agent,
            branch="main",
        )
        created.append(ev)
    return session, created


# --- Input schema ---------------------------------------------------------


def test_list_events_input_accepts_cursor_and_summary() -> None:
    parsed = ListEventsInput(cursor="019f0000-0000-7000-8000-000000000000", summary=True)
    assert parsed.cursor == "019f0000-0000-7000-8000-000000000000"
    assert parsed.summary is True


def test_list_events_input_summary_defaults_false() -> None:
    assert ListEventsInput().summary is False
    assert ListEventsInput().cursor is None


def test_list_events_input_coerces_summary_string() -> None:
    assert ListEventsInput(summary="true").summary is True
    assert ListEventsInput(summary="false").summary is False


def test_list_events_input_rejects_overlong_cursor() -> None:
    with pytest.raises(ValidationError):
        ListEventsInput(cursor="x" * 65)


# --- Repository pagination ------------------------------------------------


def test_list_events_paginated_first_page(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    _seed(repo, project, 5)
    page, has_more = repo.list_events_paginated(project_path=project, limit=2)
    assert len(page) == 2
    assert has_more is True


def test_list_events_paginated_walk_all_pages(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    _, created = _seed(repo, project, 5)
    seen: list[str] = []
    cursor = None
    for _ in range(10):  # safety bound
        page, has_more = repo.list_events_paginated(project_path=project, cursor=cursor, limit=2)
        seen.extend(e.id for e in page)
        if not has_more:
            break
        cursor = page[-1].id
    assert seen == [e.id for e in created]


def test_list_events_paginated_last_page_has_no_more(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    _seed(repo, project, 3)
    page, has_more = repo.list_events_paginated(project_path=project, limit=10)
    assert len(page) == 3
    assert has_more is False


def test_list_events_paginated_invalid_cursor_raises(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    _seed(repo, project, 2)
    with pytest.raises(UserInputError):
        repo.list_events_paginated(project_path=project, cursor="does-not-exist", limit=2)


def test_list_events_paginated_respects_agent_filter(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    _seed(repo, project, 2, agent="agent-a")
    _seed(repo, project, 3, agent="agent-b")
    page, has_more = repo.list_events_paginated(project_path=project, agent_id="agent-b", limit=10)
    assert len(page) == 3
    assert all(e.agent_id == "agent-b" for e in page)
    assert has_more is False


# --- Repository summary ---------------------------------------------------


def test_summarize_events_groups_by_type_agent_date(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    _seed(repo, project, 4, agent="agent-a")
    _seed(repo, project, 2, agent="agent-b")
    summary = repo.summarize_events(project_path=project)
    assert summary["total"] == 6
    assert summary["by_type"]["task_started"] == 6
    assert summary["by_agent"]["agent-a"] == 4
    assert summary["by_agent"]["agent-b"] == 2
    assert sum(summary["by_date"].values()) == 6
    assert summary["first_event_at"] is not None
    assert summary["last_event_at"] is not None


def test_summarize_events_empty_project(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    project.mkdir()
    summary = repo.summarize_events(project_path=project)
    assert summary["total"] == 0
    assert summary["by_type"] == {}
    assert summary["first_event_at"] is None


def test_summary_model_validates(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    _seed(repo, project, 3)
    summary = repo.summarize_events(project_path=project)
    model = ListEventsSummary.model_validate(summary)
    assert model.total == 3


def test_page_model_roundtrip(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    _seed(repo, project, 3)
    events, has_more = repo.list_events_paginated(project_path=project, limit=2)
    page = ListEventsPage(events=events, next_cursor=events[-1].id, has_more=has_more, truncated=has_more)
    dumped = page.model_dump(mode="json")
    assert dumped["has_more"] is True
    assert dumped["next_cursor"] == events[-1].id
    assert len(dumped["events"]) == 2
