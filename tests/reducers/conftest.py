"""Shared test helpers for reducer tests."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from allbrain.models.schemas import EventRead


def make_event(event_type: str, payload: dict | None = None, **overrides: object) -> EventRead:
    """Build an EventRead fixture for reducer tests.

    Auto-supplies all required fields with safe defaults.
    """
    return EventRead(
        id=str(uuid4()),
        project_id=1,
        session_id=1,
        agent_id="test_agent",
        type=event_type,
        source="test",
        file_path=None,
        payload=payload or {},
        task_hint=None,
        importance=1,
        created_at=datetime(2026, 1, 1),
        payload_version=1,
        **overrides,
    )
