from __future__ import annotations

from datetime import datetime

from allbrain.capabilities.events import make_matched_payload
from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestReplay:
    def test_round_trip(self):
        evts = [
            E(EventType.CAPABILITY_MATCHED.value, "1", make_matched_payload(agent_id="a", task_type="x", match_score=0.8, match_kind="exact")),
            E(EventType.CAPABILITY_MATCHED.value, "2", make_matched_payload(agent_id="b", task_type="x", match_score=0.3, match_kind="partial")),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "capabilities" in f
        assert f["capabilities"]["a"]["match_score"] == 0.8

    def test_equality(self):
        evts = [E(EventType.CAPABILITY_MATCHED.value, "1", make_matched_payload(agent_id="x", task_type="tt", match_score=0.5, match_kind="partial"))]
        assert EventReplayEngine().replay(evts)["final_state"]["capabilities"] == EventReplayEngine().replay(evts)["final_state"]["capabilities"]

    def test_no_events(self):
        assert EventReplayEngine().replay([])["final_state"]["capabilities"] == {}