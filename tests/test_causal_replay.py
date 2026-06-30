from __future__ import annotations

from datetime import datetime

from allbrain.causal import make_counterfactual_payload, make_impact_payload
from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestCausalReplay:
    def test_causal_key_in_final_state(self):
        result = EventReplayEngine().replay([])
        assert "causal" in result["final_state"]

    def test_empty_replay(self):
        f = EventReplayEngine().replay([])["final_state"]
        assert f["causal"] == {}

    def test_round_trip_counterfactual(self):
        evts = [
            E(
                EventType.AGENT_COUNTERFACTUAL_RUN.value,
                "e1",
                make_counterfactual_payload(
                    agent_id="a",
                    task_type="t",
                    actual_agent="a",
                    alternative_agent="b",
                    actual_outcome=0.5,
                    alternative_outcome=0.8,
                    impact_score=0.3,
                    confidence=0.8,
                    sample_count=5,
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "a::t" in f["causal"]
        assert f["causal"]["a::t"]["counterfactuals"]["b"]["impact_score"] == 0.3

    def test_round_trip_impact(self):
        evts = [
            E(
                EventType.AGENT_CAUSAL_IMPACT_RECORDED.value,
                "e1",
                make_impact_payload(
                    agent_id="x",
                    task_type="y",
                    alternative_agent="z",
                    impact_score=-0.2,
                    confidence=0.5,
                    sample_count=5,
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["causal"]["x::y"]["impacts"]["z"]["impact_score"] == -0.2

    def test_determinism(self):
        evts = [
            E(
                EventType.AGENT_COUNTERFACTUAL_RUN.value,
                "e1",
                make_counterfactual_payload(
                    agent_id="a",
                    task_type="t",
                    actual_agent="a",
                    alternative_agent="b",
                    actual_outcome=0.5,
                    alternative_outcome=0.8,
                    impact_score=0.3,
                    confidence=0.8,
                    sample_count=5,
                ),
            ),
        ]
        r1 = EventReplayEngine().replay(evts)["final_state"]["causal"]
        r2 = EventReplayEngine().replay(evts)["final_state"]["causal"]
        assert r1 == r2

    def test_mixed_with_other_reducers(self):
        from allbrain.dynamics import make_drift_payload
        from allbrain.learning import make_learned_payload

        evts = [
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.3, new_score=0.8, delta=0.5),
            ),
            E(
                EventType.AGENT_COUNTERFACTUAL_RUN.value,
                "e2",
                make_counterfactual_payload(
                    agent_id="a",
                    task_type="t",
                    actual_agent="a",
                    alternative_agent="b",
                    actual_outcome=0.5,
                    alternative_outcome=0.8,
                    impact_score=0.3,
                    confidence=0.8,
                    sample_count=5,
                ),
            ),
            E(
                EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
                "e3",
                make_drift_payload(
                    agent_id="a", task_type="t", drift_score=0.1, drift_level="medium", ema_short=0.5, ema_long=0.4
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "learning" in f
        assert "dynamics" in f
        assert "causal" in f
