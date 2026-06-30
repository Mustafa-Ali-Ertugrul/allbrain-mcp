from __future__ import annotations

from datetime import datetime

from allbrain.dynamics import make_drift_payload, make_forecast_payload, make_trend_payload
from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        self.created_at = datetime(2020, 1, 1)


class TestDynamicsReplay:
    def test_dynamics_key_in_final_state(self):
        result = EventReplayEngine().replay([])
        assert "dynamics" in result["final_state"]

    def test_empty_replay(self):
        f = EventReplayEngine().replay([])["final_state"]
        assert f["dynamics"] == {}

    def test_round_trip_drift_event(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
                "e1",
                make_drift_payload(
                    agent_id="a", task_type="t", drift_score=0.1, drift_level="medium", ema_short=0.5, ema_long=0.4
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "a::t" in f["dynamics"]
        assert f["dynamics"]["a::t"]["drift"]["drift_score"] == 0.1

    def test_round_trip_trend_event(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_TREND_UPDATED.value,
                "e1",
                make_trend_payload(
                    agent_id="a", task_type="t", slope=0.03, label="improving", momentum=0.5, consecutive_count=3
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["dynamics"]["a::t"]["trend"]["label"] == "improving"

    def test_round_trip_forecast_event(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value,
                "e1",
                make_forecast_payload(
                    agent_id="a",
                    task_type="t",
                    horizon=5,
                    predicted_capability=0.7,
                    confidence=0.8,
                    current_capability=0.6,
                    delta=0.1,
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert f["dynamics"]["a::t"]["forecast"]["predicted_capability"] == 0.7

    def test_determinism(self):
        evts = [
            E(
                EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
                "e1",
                make_drift_payload(
                    agent_id="x", task_type="y", drift_score=0.04, drift_level="low", ema_short=0.5, ema_long=0.48
                ),
            ),
        ]
        r1 = EventReplayEngine().replay(evts)["final_state"]["dynamics"]
        r2 = EventReplayEngine().replay(evts)["final_state"]["dynamics"]
        assert r1 == r2

    def test_mixed_with_learning_events(self):
        from allbrain.learning import make_learned_payload

        evts = [
            E(
                EventType.AGENT_CAPABILITY_LEARNED.value,
                "e1",
                make_learned_payload(agent_id="a", task_type="t", old_score=0.3, new_score=0.8, delta=0.5),
            ),
            E(
                EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
                "e2",
                make_drift_payload(
                    agent_id="a", task_type="t", drift_score=0.12, drift_level="medium", ema_short=0.6, ema_long=0.4
                ),
            ),
        ]
        f = EventReplayEngine().replay(evts)["final_state"]
        assert "learning" in f
        assert "dynamics" in f
        assert f["learning"]["a::t"]["capability_score"] == 0.8
        assert f["dynamics"]["a::t"]["drift"]["drift_score"] == 0.12
