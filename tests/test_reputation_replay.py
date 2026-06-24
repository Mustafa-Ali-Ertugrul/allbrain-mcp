from __future__ import annotations

from datetime import datetime

import pytest

from allbrain.events.schemas import EventType
from allbrain.reputation.events import make_payload


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestReplay:
    def test_round_trip(self):
        from allbrain.replay import EventReplayEngine
        engine = EventReplayEngine()
        events = [
            E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_payload(agent_id="a", task_id="t1", success=True, confidence=1.0, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="x")),
            E(EventType.AGENT_REPUTATION_UPDATED.value, "2", make_payload(agent_id="b", task_id="t2", success=False, confidence=0.0, duration_ms=0, retry_count=5, reputation_score=0.0, analysis_id="y")),
        ]
        result = engine.replay(events)
        final = result["final_state"]
        assert "reputation" in final
        assert len(final["reputation"]) == 2
        assert final["reputation"]["a"]["reputation_score"] == pytest.approx(1.0)
        assert final["reputation"]["b"]["reputation_score"] == pytest.approx(0.0)

    def test_replay_equality(self):
        from allbrain.replay import EventReplayEngine
        engine = EventReplayEngine()
        events = [
            E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_payload(agent_id="x", task_id="t", success=True, confidence=0.8, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="a")),
        ]
        result1 = engine.replay(events)
        result2 = engine.replay(events)
        assert result1["final_state"]["reputation"] == result2["final_state"]["reputation"]

    def test_replay_with_no_events(self):
        from allbrain.replay import EventReplayEngine
        engine = EventReplayEngine()
        result = engine.replay([])
        assert "reputation" in result["final_state"]
        assert result["final_state"]["reputation"] == {}

    def test_replay_preserves_other_projections(self):
        from allbrain.replay import EventReplayEngine
        engine = EventReplayEngine()
        events = [
            E(EventType.TASK_CREATED.value, "0", {"task_id": "t", "goal": "x"}),
            E(EventType.AGENT_REPUTATION_UPDATED.value, "1", make_payload(agent_id="a", task_id="t", success=True, confidence=1.0, duration_ms=0, retry_count=0, reputation_score=0.0, analysis_id="x")),
        ]
        result = engine.replay(events)
        final = result["final_state"]
        assert "tasks" in final
        assert "calibration" in final
        assert "reputation" in final