from __future__ import annotations

from datetime import datetime

from allbrain.events.schemas import EventType
from allbrain.fusion import make_calibration_payload, make_fusion_payload
from allbrain.replay import EventReplayEngine


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestFusionReplay:
    def test_fusion_key_in_final_state(self):
        result = EventReplayEngine().replay([])
        assert "fusion" in result["final_state"]

    def test_empty_replay(self):
        f = EventReplayEngine().replay([])["final_state"]
        assert f["fusion"] == {}

    def test_round_trip_fusion(self):
        evts = [
            E(EventType.FUSION_COMPUTED.value, "e1",
              make_fusion_payload(agent_id="a", task_type="t", unified_score=0.65, capability=0.8, learning=0.7, dynamics=0.5, causal=0.6)),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "a::t" in f["fusion"]
        assert f["fusion"]["a::t"]["score"]["unified_score"] == 0.65

    def test_round_trip_calibration(self):
        evts = [
            E(EventType.SIGNAL_CALIBRATED.value, "e1",
              make_calibration_payload(agent_id="x", task_type="y", channel="capability", raw_mean=0.7, normalized_value=0.72, was_normalized=True, sample_count=5)),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["fusion"]["x::y"]["calibrations"]["capability"]["normalized_value"] == 0.72

    def test_determinism(self):
        evts = [
            E(EventType.FUSION_COMPUTED.value, "e1",
              make_fusion_payload(agent_id="a", task_type="t", unified_score=0.5, capability=0.5, learning=0.5, dynamics=0.5, causal=0.5)),
        ]
        r1 = EventReplayEngine().replay(evts)["final_state"]["fusion"]
        r2 = EventReplayEngine().replay(evts)["final_state"]["fusion"]
        assert r1 == r2

    def test_mixed_with_all_reducers(self):
        from allbrain.capabilities.events import make_matched_payload
        from allbrain.causal import make_counterfactual_payload
        from allbrain.dynamics import make_drift_payload
        from allbrain.learning import make_learned_payload
        evts = [
            E(EventType.CAPABILITY_MATCHED.value, "e1",
              make_matched_payload(agent_id="a", task_type="t", match_score=0.8, match_kind="exact")),
            E(EventType.AGENT_CAPABILITY_LEARNED.value, "e2",
              make_learned_payload(agent_id="a", task_type="t", old_score=0.3, new_score=0.8, delta=0.5)),
            E(EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value, "e3",
              make_drift_payload(agent_id="a", task_type="t", drift_score=0.1, drift_level="medium", ema_short=0.5, ema_long=0.4)),
            E(EventType.AGENT_COUNTERFACTUAL_RUN.value, "e4",
              make_counterfactual_payload(agent_id="a", task_type="t", actual_agent="a", alternative_agent="b", actual_outcome=0.5, alternative_outcome=0.8, impact_score=0.3, confidence=0.8, sample_count=5)),
            E(EventType.FUSION_COMPUTED.value, "e5",
              make_fusion_payload(agent_id="a", task_type="t", unified_score=0.6, capability=0.8, learning=0.7, dynamics=0.5, causal=0.6)),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "capabilities" in f
        assert "learning" in f
        assert "dynamics" in f
        assert "causal" in f
        assert "fusion" in f
