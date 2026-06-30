from __future__ import annotations

from datetime import datetime

from allbrain.events.schemas import EventType
from allbrain.learning import (
    make_decayed_payload,
    make_learned_payload,
    make_observed_payload,
)
from allbrain.replay import EventReplayEngine


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestLearningReplay:
    def test_learning_key_in_final_state(self):
        result = EventReplayEngine().replay([])
        assert "learning" in result["final_state"]

    def test_empty_replay(self):
        result = EventReplayEngine().replay([])["final_state"]
        assert result["learning"] == {}

    def test_observed_round_trip(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_OBSERVED.value,
                "e1",
                make_observed_payload(
                    agent_id="a", task_type="t", success=True, runtime_score=0.8, selection_score=0.7
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "learning" in f
        assert "a::t" in f["learning"]
        assert f["learning"]["a::t"]["agent_id"] == "a"
        assert f["learning"]["a::t"]["task_type"] == "t"

    def test_learned_round_trip(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(
                    agent_id="agent_x", task_type="bug_fix", old_score=0.3, new_score=0.85, delta=0.55
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["learning"]["agent_x::bug_fix"]["capability_score"] == 0.85

    def test_decayed_round_trip(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_DECAYED.value,
                "e1",
                make_decayed_payload(agent_id="agent_y", task_type="refactor", old_score=0.7, new_score=0.35),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert abs(f["learning"]["agent_y::refactor"]["capability_score"] - 0.35) < 1e-9

    def test_mixed_events_replay(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_OBSERVED.value,
                "e1",
                make_observed_payload(
                    agent_id="a", task_type="t", success=True, runtime_score=0.9, selection_score=0.8
                ),
            ),
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e2",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.5, new_score=0.92, delta=0.42),
            ),
            E(
                EventType.AGENT_CAPABILITY_OBSERVED.value,
                "e3",
                make_observed_payload(
                    agent_id="b", task_type="u", success=False, runtime_score=0.2, selection_score=0.1
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["learning"]["a::t"]["capability_score"] == 0.92
        # b::u only has OBSERVED -> observation-based score
        # Reducer builds obs = (1.0 if success else 0.0)*0.5 + runtime*0.3 + selection*0.2
        # = 0.0*0.5 + 0.2*0.3 + 0.1*0.2 = 0.06 + 0.02 = 0.08
        assert abs(f["learning"]["b::u"]["capability_score"] - 0.08) < 1e-9

    def test_deterministic_ordering(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e2",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.2, new_score=0.9, delta=0.7),
            ),
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.4, new_score=0.5, delta=0.1),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        # In deterministic mode, events are sorted by canonical_event_sort
        # e1 comes before e2 -> last LEARNED wins with score 0.9
        assert f["learning"]["a::t"]["capability_score"] == 0.9

    def test_equality(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="x", task_type="tt", old_score=0.2, new_score=0.5, delta=0.3),
            ),
        ]
        r1 = EventReplayEngine().replay(evts)["final_state"]["learning"]
        r2 = EventReplayEngine().replay(evts)["final_state"]["learning"]
        assert r1 == r2

    def test_mixed_with_existing_reducers(self):
        """Learning events alongside capability events do not interfere."""
        from allbrain.capabilities.events import make_matched_payload

        evts = [
            E(
                EventType.CAPABILITY_MATCHED.value,
                "e1",
                make_matched_payload(agent_id="a", task_type="t", match_score=0.8, match_kind="exact"),
            ),
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e2",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.3, new_score=0.7, delta=0.4),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "capabilities" in f
        assert "learning" in f
        assert f["capabilities"]["a"]["match_score"] == 0.8
        assert f["learning"]["a::t"]["capability_score"] == 0.7
