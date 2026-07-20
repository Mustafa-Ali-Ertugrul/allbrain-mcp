from __future__ import annotations

from datetime import datetime

from allbrain.attribution import (
    make_attribution_update_payload,
    make_credit_payload,
    make_importance_payload,
)
from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestAttributionReplay:
    def test_replay_key(self):
        result = EventReplayEngine().replay([])
        assert "attribution" in result["final_state"]

    def test_round_trip_credit(self):
        evts = [
            E(
                EventType.SIGNAL_CREDIT_ASSIGNED.value,
                "e1",
                make_credit_payload(decision_id="d1", signal="dynamics", contribution=0.24, confidence=0.7),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "d1" in f["attribution"]
        assert f["attribution"]["d1"]["credits"]["dynamics"]["contribution"] == 0.24

    def test_round_trip_update(self):
        evts = [
            E(
                EventType.SIGNAL_ATTRIBUTION_UPDATED.value,
                "e1",
                make_attribution_update_payload(signal="causal", ema_reward=0.72, count=5),
            ),
            E(
                EventType.SIGNAL_CREDIT_ASSIGNED.value,
                "e2",
                make_credit_payload(decision_id="d1", signal="x", contribution=0.5, confidence=0.5),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "d1" in f["attribution"]
        assert f["attribution"]["d1"]["updates"]["causal"]["ema_reward"] == 0.72

    def test_round_trip_importance(self):
        evts = [
            E(
                EventType.SIGNAL_IMPORTANCE_CHANGED.value,
                "e1",
                make_importance_payload(signal="learning", delta_importance=0.12, direction="increased"),
            ),
            E(
                EventType.SIGNAL_CREDIT_ASSIGNED.value,
                "e2",
                make_credit_payload(decision_id="d1", signal="x", contribution=0.5, confidence=0.5),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["attribution"]["d1"]["importance"]["learning"]["delta_importance"] == 0.12

    def test_determinism(self):
        evts = [
            E(
                EventType.SIGNAL_CREDIT_ASSIGNED.value,
                "e1",
                make_credit_payload(decision_id="x", signal="capability", contribution=0.32, confidence=0.7),
            ),
        ]
        r1 = EventReplayEngine().replay(evts)["final_state"]["attribution"]
        r2 = EventReplayEngine().replay(evts)["final_state"]["attribution"]
        assert r1 == r2

    def test_mixed_with_meta_policy(self):
        from allbrain.meta_policy import make_policy_eval_payload

        evts = [
            E(
                EventType.POLICY_EVALUATED.value,
                "e1",
                make_policy_eval_payload(agent_id="a", task_type="t", mode="fusion", exploration_rate=0.05),
            ),
            E(
                EventType.SIGNAL_CREDIT_ASSIGNED.value,
                "e2",
                make_credit_payload(decision_id="d1", signal="capability", contribution=0.32, confidence=0.7),
            ),
            E(
                EventType.SIGNAL_ATTRIBUTION_UPDATED.value,
                "e3",
                make_attribution_update_payload(signal="capability", ema_reward=0.5, count=3),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "meta_policy" in f
        assert "attribution" in f

    def test_empty_replay(self):
        f = EventReplayEngine().replay([])["final_state"]
        assert f["attribution"] == {}

    def test_no_duplicate_emission(self):
        evts = [
            E(
                EventType.SIGNAL_CREDIT_ASSIGNED.value,
                "dup",
                make_credit_payload(decision_id="d", signal="s", contribution=0.5, confidence=0.5),
            ),
            E(
                EventType.SIGNAL_CREDIT_ASSIGNED.value,
                "dup",
                make_credit_payload(decision_id="d", signal="s", contribution=0.9, confidence=0.5),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["attribution"]["d"]["credits"]["s"]["contribution"] == 0.5

    def test_projection_only(self):
        evts = []
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["attribution"] == {}

    def test_mixed_with_decision(self):
        from allbrain.domains.reasoning.decision import make_decision_payload

        evts = [
            E(
                EventType.DECISION_COMPUTED.value,
                "e1",
                make_decision_payload(agent_id="a", task_type="t", score=0.8, mode="fusion"),
            ),
            E(
                EventType.SIGNAL_CREDIT_ASSIGNED.value,
                "e2",
                make_credit_payload(decision_id="e1", signal="dynamics", contribution=0.24, confidence=0.7),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "decision" in f
        assert "attribution" in f
