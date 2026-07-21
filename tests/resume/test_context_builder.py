"""Tests for resume/context_builder.py."""

from datetime import UTC, datetime, timezone
from pathlib import Path
from uuid import uuid4

from allbrain.domains.memory.resume.context_builder import ContextBuilder
from allbrain.models.schemas import EventRead


def _event() -> EventRead:
    from allbrain.domains.memory.foundations import current_payload_version

    return EventRead(
        id=str(uuid4()),
        project_id=1,
        session_id=1,
        agent_id="tester",
        type="test",
        source="test",
        file_path="",
        payload={},
        task_hint="",
        importance=0,
        created_at=datetime.now(UTC),
        payload_version=current_payload_version(),
    )


class TestContextBuilder:
    def test_build_with_git(self, tmp_path):
        result = ContextBuilder().build(events=[_event(), _event()], project_path=str(tmp_path), include_git=True)
        assert "events" in result and "git" in result and len(result["events"]) == 2

    def test_build_without_git(self, tmp_path):
        result = ContextBuilder().build(events=[_event()], project_path=str(tmp_path), include_git=False)
        assert "events" in result and result["git"] == {}

    def test_empty_events(self, tmp_path):
        result = ContextBuilder().build(events=[], project_path=str(tmp_path), include_git=False)
        assert result["events"] == []
