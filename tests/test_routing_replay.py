from __future__ import annotations

from datetime import datetime

from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine
from allbrain.routing.events import make_scored_payload, make_selected_payload


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestReplay:
    def test_round_trip(self):
        evts = [
            E(
                EventType.AGENT_SELECTION_SCORED.value,
                "1",
                make_scored_payload(
                    agent_id="a",
                    task_type="x",
                    selection_score=0.9,
                    reputation=0.8,
                    runtime_score=0.7,
                    calibrated_trust=0.6,
                ),
            ),
            E(
                EventType.AGENT_SELECTION_SCORED.value,
                "2",
                make_scored_payload(
                    agent_id="b",
                    task_type="x",
                    selection_score=0.5,
                    reputation=0.4,
                    runtime_score=0.3,
                    calibrated_trust=0.2,
                ),
            ),
            E(
                EventType.AGENT_SELECTED.value,
                "3",
                make_selected_payload(task_id="t", task_type="x", agent_id="a", selection_score=0.9),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "routing" in f
        assert f["routing"]["x"]["selected_agent"] == "a"

    def test_equality(self):
        evts = [
            E(
                EventType.AGENT_SELECTION_SCORED.value,
                "1",
                make_scored_payload(
                    agent_id="x",
                    task_type="tt",
                    selection_score=0.8,
                    reputation=0.7,
                    runtime_score=0.6,
                    calibrated_trust=0.5,
                ),
            )
        ]
        r1 = EventReplayEngine().replay(evts)
        r2 = EventReplayEngine().replay(evts)
        assert r1["final_state"]["routing"] == r2["final_state"]["routing"]

    def test_no_events(self):
        assert EventReplayEngine().replay([])["final_state"]["routing"] == {}
