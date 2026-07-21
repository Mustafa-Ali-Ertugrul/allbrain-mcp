"""Tests for telemetry/manager.py - TelemetryManager."""

from datetime import UTC, datetime
from uuid import uuid4

from allbrain.domains.memory.telemetry.manager import TelemetryManager
from allbrain.events import EventType
from allbrain.models.schemas import EventRead


def _tool_event(success: bool, duration_ms: float, retry_count: float, agent_id: str = "default"):
    from allbrain.domains.memory.foundations import current_payload_version

    return EventRead(
        id=str(uuid4()),
        project_id=1,
        session_id=1,
        agent_id=agent_id,
        type=EventType.TOOL_EXECUTION_COMPLETED.value,
        source="test",
        file_path="",
        payload={
            "success": success,
            "duration_ms": duration_ms,
            "retry_count": retry_count,
            "agent_id": agent_id,
        },
        task_hint="",
        importance=0,
        created_at=datetime.now(UTC),
        payload_version=current_payload_version(),
    )


def _other_event():
    from allbrain.domains.memory.foundations import current_payload_version

    return EventRead(
        id=str(uuid4()),
        project_id=1,
        session_id=1,
        agent_id="default",
        type=EventType.TASK_CREATED.value,
        source="test",
        file_path="",
        payload={},
        task_hint="",
        importance=0,
        created_at=datetime.now(UTC),
        payload_version=current_payload_version(),
    )


class TestTelemetryManager:
    def test_query_empty(self):
        m = TelemetryManager()
        s = m.query([], agent_id="default")
        assert s.execution_count == 0
        assert s.success_rate == 0.0
        assert s.mean_duration_ms == 0.0

    def test_query_all_success(self):
        m = TelemetryManager()
        events = [_tool_event(True, 100.0, 0), _tool_event(True, 200.0, 1)]
        s = m.query(events, agent_id="default")
        assert s.execution_count == 2
        assert s.success_rate == 1.0
        assert s.mean_duration_ms == 150.0
        assert s.mean_retry_count == 0.5

    def test_query_mixed_success(self):
        m = TelemetryManager()
        events = [_tool_event(True, 100.0, 0), _tool_event(False, 50.0, 2)]
        s = m.query(events, agent_id="default")
        assert s.execution_count == 2
        assert s.success_rate == 0.5

    def test_filters_other_agent(self):
        m = TelemetryManager()
        events = [_tool_event(True, 100.0, 0, agent_id="other")]
        s = m.query(events, agent_id="default")
        assert s.execution_count == 0

    def test_filters_non_tool_events(self):
        m = TelemetryManager()
        s = m.query([_other_event()], agent_id="default")
        assert s.execution_count == 0

    def test_known_agent_ids(self):
        m = TelemetryManager()
        events = [
            _tool_event(True, 100.0, 0, agent_id="a1"),
            _tool_event(False, 50.0, 1, agent_id="a2"),
            _other_event(),
        ]
        ids = m.known_agent_ids(events)
        assert ids == {"a1", "a2"}

    def test_missing_payload_handled(self):
        m = TelemetryManager()
        ev = EventRead(
            id=str(uuid4()),
            project_id=1,
            session_id=1,
            agent_id="default",
            type=EventType.TOOL_EXECUTION_COMPLETED.value,
            source="test",
            file_path="",
            payload={},
            task_hint="",
            importance=0,
            created_at=datetime.now(UTC),
            payload_version=1,
        )
        s = m.query([ev], agent_id="default")
        assert s.execution_count == 0

    def test_analysis_id_stable(self):
        m = TelemetryManager()
        s1 = m.query([_tool_event(True, 100.0, 0)], agent_id="default", analysis_id="test-id")
        assert s1.analysis_id == "test-id"
