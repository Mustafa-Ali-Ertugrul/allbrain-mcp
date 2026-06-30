from __future__ import annotations

from datetime import datetime

from allbrain.decision import make_decision_payload, validate_decision
from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestDecisionEvents:
    def test_decision_key_in_final_state(self):
        result = EventReplayEngine().replay([])
        assert "decision" in result["final_state"]

    def test_empty_replay(self):
        f = EventReplayEngine().replay([])["final_state"]
        assert f["decision"] == {}

    def test_round_trip_decision(self):
        evts = [
            E(EventType.DECISION_COMPUTED.value, "e1",
              make_decision_payload(agent_id="a", task_type="t", score=0.84, mode="fusion", contributors={"capability": 0.2, "learning": 0.2}, backend_trace=("fusion", "calibrated"))),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "a::t" in f["decision"]
        assert f["decision"]["a::t"]["score"]["score"] == 0.84

    def test_determinism(self):
        evts = [
            E(EventType.DECISION_COMPUTED.value, "e1",
              make_decision_payload(agent_id="a", task_type="t", score=0.5, mode="legacy")),
        ]
        r1 = EventReplayEngine().replay(evts)["final_state"]["decision"]
        r2 = EventReplayEngine().replay(evts)["final_state"]["decision"]
        assert r1 == r2
