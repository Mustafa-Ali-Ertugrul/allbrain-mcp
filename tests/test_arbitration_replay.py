from __future__ import annotations

from datetime import datetime

from allbrain.arbitration.events import make_consensus_payload, make_vote_payload
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
        events = [
            E(
                EventType.AGENT_VOTE_CAST.value,
                "1",
                make_vote_payload(
                    agent_id="a",
                    candidate_id="c1",
                    context_key="ctx",
                    confidence=1.0,
                    reputation=1.0,
                    calibrated_trust=1.0,
                ),
            ),
            E(
                EventType.AGENT_VOTE_CAST.value,
                "2",
                make_vote_payload(
                    agent_id="b",
                    candidate_id="c1",
                    context_key="ctx",
                    confidence=0.5,
                    reputation=0.5,
                    calibrated_trust=0.5,
                ),
            ),
        ]
        result = EventReplayEngine().replay(events)
        final = result["final_state"]
        assert "arbitration" in final
        assert "ctx" in final["arbitration"]
        assert final["arbitration"]["ctx"]["vote_count"] == 2

    def test_replay_equality(self):
        events = [
            E(
                EventType.AGENT_VOTE_CAST.value,
                "1",
                make_vote_payload(
                    agent_id="x",
                    candidate_id="c",
                    context_key="ctx",
                    confidence=0.8,
                    reputation=0.7,
                    calibrated_trust=0.9,
                ),
            ),
        ]
        r1 = EventReplayEngine().replay(events)
        r2 = EventReplayEngine().replay(events)
        assert r1["final_state"]["arbitration"] == r2["final_state"]["arbitration"]

    def test_replay_with_no_events(self):
        result = EventReplayEngine().replay([])
        assert "arbitration" in result["final_state"]
        assert result["final_state"]["arbitration"] == {}
