from __future__ import annotations

from datetime import datetime

from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine
from allbrain.telemetry.events import make_completed_payload


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestReplay:
    def test_round_trip(self):
        events = [
            E(
                EventType.TOOL_EXECUTION_COMPLETED.value,
                "1",
                make_completed_payload(
                    agent_id="a", task_id="t1", tool_name="x", duration_ms=100, success=True, retry_count=0
                ),
            ),
            E(
                EventType.TOOL_EXECUTION_COMPLETED.value,
                "2",
                make_completed_payload(
                    agent_id="a", task_id="t2", tool_name="x", duration_ms=300, success=False, retry_count=1
                ),
            ),
        ]
        result = EventReplayEngine().replay(events)
        final = result["final_state"]
        assert "telemetry" in final
        assert "a" in final["telemetry"]
        assert final["telemetry"]["a"]["execution_count"] == 2

    def test_equality(self):
        events = [
            E(
                EventType.TOOL_EXECUTION_COMPLETED.value,
                "1",
                make_completed_payload(
                    agent_id="x", task_id="t", tool_name="tool", duration_ms=100, success=True, retry_count=0
                ),
            ),
        ]
        r1 = EventReplayEngine().replay(events)
        r2 = EventReplayEngine().replay(events)
        assert r1["final_state"]["telemetry"] == r2["final_state"]["telemetry"]

    def test_no_events(self):
        result = EventReplayEngine().replay([])
        assert result["final_state"]["telemetry"] == {}
