"""DB-level invariant: (project_id, stream_position) is unique."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from uuid6 import uuid7

from allbrain.models.entities import Event
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from allbrain.storage.database import open_session


def _repo(tmp_path: Path) -> tuple[BrainRepository, Path]:
    engine = create_engine_for_path(tmp_path / "brain.db")
    init_db(engine)
    project = tmp_path / "proj"
    project.mkdir()
    return BrainRepository(engine), project


def test_append_event_assigns_unique_stream_positions(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    session = repo.create_session(project, "agent-a")
    e1 = repo.append_event(
        project_path=project,
        session_id=session.id or 0,
        type="tool_call",
        source="agent",
        payload={"n": 1},
    )
    e2 = repo.append_event(
        project_path=project,
        session_id=session.id or 0,
        type="tool_call",
        source="agent",
        payload={"n": 2},
    )
    assert e1.stream_position is not None
    assert e2.stream_position is not None
    assert e1.stream_position != e2.stream_position
    assert e2.stream_position == e1.stream_position + 1


def test_duplicate_project_stream_position_rejected(tmp_path: Path) -> None:
    repo, project = _repo(tmp_path)
    session = repo.create_session(project, "agent-a")
    first = repo.append_event(
        project_path=project,
        session_id=session.id or 0,
        type="tool_call",
        source="agent",
        payload={},
    )
    assert first.stream_position is not None
    position = first.stream_position
    project_id = first.project_id

    with open_session(repo.engine) as db:
        db.add(
            Event(
                id=str(uuid7()),
                project_id=project_id,
                session_id=session.id or 0,
                type="tool_call",
                source="agent",
                payload_json="{}",
                stream_position=position,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
