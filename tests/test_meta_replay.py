from __future__ import annotations

from datetime import datetime

from allbrain.events.schemas import EventType
from allbrain.meta_policy import (
    make_policy_eval_payload, make_policy_update_payload, make_policy_drift_payload,
    MetaPolicyManager,
)
from allbrain.replay import EventReplayEngine


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestMetaReplay:
    def test_replay_key(self):
        result = EventReplayEngine().replay([])
        assert "meta_policy" in result["final_state"]

    def test_round_trip_eval(self):
        evts = [
            E(EventType.POLICY_EVALUATED.value, "e1",
              make_policy_eval_payload(agent_id="a", task_type="t", mode="fusion", exploration_rate=0.05)),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["meta_policy"]["a"]["eval"]["mode"] == "fusion"

    def test_round_trip_update(self):
        evts = [
            E(EventType.POLICY_UPDATED.value, "e1",
              make_policy_update_payload(agent_id="b", mode="fusion", reward=0.7, ema_reward=0.6, count=5)),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["meta_policy"]["b"]["updates"]["fusion"]["reward"] == 0.7

    def test_round_trip_drift(self):
        evts = [
            E(EventType.POLICY_DIVERGENCE_DETECTED.value, "e1",
              make_policy_drift_payload(agent_id="c", kl_divergence=0.8, threshold=0.5, snapshot_id="snap-1")),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["meta_policy"]["c"]["drift"]["kl_divergence"] == 0.8

    def test_determinism(self):
        evts = [
            E(EventType.POLICY_EVALUATED.value, "e1",
              make_policy_eval_payload(agent_id="x", task_type="y", mode="legacy", exploration_rate=0.1)),
        ]
        r1 = EventReplayEngine().replay(evts)["final_state"]["meta_policy"]
        r2 = EventReplayEngine().replay(evts)["final_state"]["meta_policy"]
        assert r1 == r2

    def test_mixed_with_decision_events(self):
        from allbrain.decision import make_decision_payload
        evts = [
            E(EventType.DECISION_COMPUTED.value, "e1",
              make_decision_payload(agent_id="a", task_type="t", score=0.8, mode="fusion")),
            E(EventType.POLICY_EVALUATED.value, "e2",
              make_policy_eval_payload(agent_id="a", task_type="t", mode="fusion", exploration_rate=0.05)),
            E(EventType.POLICY_UPDATED.value, "e3",
              make_policy_update_payload(agent_id="a", mode="fusion", reward=0.7, ema_reward=0.6, count=5)),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "decision" in f
        assert "meta_policy" in f

    def test_manager_select(self):
        evts = []
        mgr = MetaPolicyManager()
        mode = mgr.select(evts, agent_id="test", task_type="test")
        assert mode in {"fusion", "causal", "dynamic", "legacy"}

    def test_manager_update_no_events(self):
        mgr = MetaPolicyManager()
        r = mgr.update([], agent_id="a", mode="fusion", decision_id="d1", task_type="t")
        assert r is None