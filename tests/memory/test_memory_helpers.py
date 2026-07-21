from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from allbrain.domains.memory.foundations import current_payload_version
from allbrain.domains.memory.memory.memory_helpers import (
    _agent,
    _failed_agent,
    _failure_pattern,
    _failure_reason,
    _fallback_pattern,
    _importance,
    _last_agent,
    _status,
    _task_summary,
)
from allbrain.events import EventType
from allbrain.models.schemas import EventRead


def _event(
    event_type: str,
    *,
    event_id: str = "e1",
    payload: dict | None = None,
    agent_id: str | None = None,
    created_at: datetime | None = None,
) -> EventRead:
    return EventRead(
        id=event_id,
        project_id=1,
        session_id=1,
        type=event_type,
        source="test",
        file_path=None,
        payload=payload or {},
        task_hint=None,
        agent_id=agent_id,
        importance=1,
        created_at=created_at or datetime(2026, 1, 1, 12, 0, 0),
        payload_version=current_payload_version(),
    )


class TestMemoryHelpers:
    def test_agent_from_agent_id_payload(self) -> None:
        e = _event(EventType.TASK_ASSIGNED.value, payload={"agent_id": "agent1"})
        assert _agent(e) == "agent1"

    def test_agent_from_from_agent(self) -> None:
        e = _event(EventType.HANDOFF_CREATED.value, payload={"from_agent": "agent1", "to_agent": "agent2"})
        assert _agent(e) == "agent1"

    def test_agent_from_event_field(self) -> None:
        e = _event(EventType.TASK_CREATED.value, agent_id="agent1")
        assert _agent(e) == "agent1"

    def test_agent_none(self) -> None:
        e = _event(EventType.TASK_CREATED.value)
        assert _agent(e) is None

    def test_status_success(self) -> None:
        events = [_event(EventType.TASK_COMPLETED.value)]
        assert _status(events) == "success"

    def test_status_failed(self) -> None:
        events = [_event(EventType.TASK_FAILED.value)]
        assert _status(events) == "failed"

    def test_status_blocked(self) -> None:
        events = [_event(EventType.TASK_BLOCKED.value)]
        assert _status(events) == "blocked"

    def test_status_active(self) -> None:
        events = [_event(EventType.TASK_CREATED.value)]
        assert _status(events) == "active"

    def test_importance_failed(self) -> None:
        events = [_event(EventType.TASK_FAILED.value)]
        assert _importance(events) == 0.8

    def test_importance_success(self) -> None:
        events = [_event(EventType.TASK_COMPLETED.value)]
        assert _importance(events) == 0.7

    def test_importance_active(self) -> None:
        events = [_event(EventType.TASK_CREATED.value)]
        assert _importance(events) == 0.4

    def test_last_agent(self) -> None:
        e1 = _event(EventType.TASK_ASSIGNED.value, event_id="e1", agent_id="agent1")
        e2 = _event(EventType.TASK_ASSIGNED.value, event_id="e2", agent_id="agent2")
        assert _last_agent([e1, e2]) == "agent2"

    def test_last_agent_none(self) -> None:
        assert _last_agent([]) is None

    def test_failure_reason_from_reason(self) -> None:
        e = _event(EventType.TASK_FAILED.value, payload={"reason": "timeout"})
        assert _failure_reason([e]) == "timeout"

    def test_failure_reason_from_error(self) -> None:
        e = _event(EventType.AGENT_EXECUTION_FAILED.value, payload={"error": "OOM"})
        assert _failure_reason([e]) == "OOM"

    def test_failure_reason_none(self) -> None:
        e = _event(EventType.TASK_COMPLETED.value)
        assert _failure_reason([e]) is None

    def test_failed_agent(self) -> None:
        e = _event(EventType.TASK_FAILED.value, payload={"agent_id": "agent1"})
        assert _failed_agent([e]) == "agent1"

    def test_failed_agent_none(self) -> None:
        e = _event(EventType.TASK_COMPLETED.value)
        assert _failed_agent([e]) is None

    def test_failure_pattern(self) -> None:
        e = _event(EventType.TASK_FAILED.value, event_id="e1", payload={"reason": "timeout", "agent_id": "agent1"})
        pattern = _failure_pattern("task1", [e])
        assert pattern is not None
        assert "timeout" in pattern
        assert "agent1" in pattern

    def test_failure_pattern_no_reason(self) -> None:
        e = _event(EventType.TASK_CREATED.value)
        assert _failure_pattern("task1", [e]) is None

    def test_fallback_pattern_single_assignment(self) -> None:
        e = _event(EventType.TASK_ASSIGNED.value, payload={"agent_id": "agent1"})
        assert _fallback_pattern("task1", [e]) is None

    def test_fallback_pattern_multiple(self) -> None:
        e1 = _event(EventType.TASK_ASSIGNED.value, event_id="e1", payload={"agent_id": "agent1"})
        e2 = _event(EventType.TASK_ASSIGNED.value, event_id="e2", payload={"agent_id": "agent2"})
        e3 = _event(EventType.TASK_COMPLETED.value, event_id="e3")
        pattern = _fallback_pattern("task1", [e1, e2, e3])
        assert pattern is not None
        assert "agent1 -> agent2" in pattern
