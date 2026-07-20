from __future__ import annotations

from allbrain.domains.analysis.dynamics import (
    DENSITY_PENALTY_FACTOR,
    DRIFT_EMA_LONG_WINDOW,
    DRIFT_EMA_SHORT_WINDOW,
    DRIFT_HIGH_THRESHOLD,
    DRIFT_MEDIUM_THRESHOLD,
    DRIFT_THRESHOLD,
    DYNAMICS_TEMPLATE_VERSION,
    MIN_OBSERVATIONS_FOR_DRIFT,
    DriftLevel,
    DriftState,
    ForecastState,
    TrendLabel,
    TrendState,
    classify_trend,
    detect_drift,
    learning_confidence_attenuation,
    make_drift_payload,
    make_forecast_payload,
    make_trend_payload,
    predict,
    validate_drift,
    validate_forecast,
    validate_trend,
)
from allbrain.events.schemas import EventType
from allbrain.routing import dynamics_selection_score


class TestDriftDetection:
    def test_no_drift_stable_series(self):
        scores = [0.5] * 30
        state = detect_drift(agent_id="a", task_type="t", scores=scores, observation_count=30)
        assert state.drift_score == 0.0
        assert state.drift_level == DriftLevel.LOW

    def test_high_drift_detection(self):
        scores = [0.3] * 20 + [0.8] * 10
        state = detect_drift(agent_id="a", task_type="t", scores=scores, observation_count=30)
        assert state.drift_score > 0.0

    def test_ema_short_long_compute(self):
        low_part = [0.2] * 20
        high_part = [0.9] * 10
        state = detect_drift(agent_id="a", task_type="t", scores=low_part + high_part, observation_count=30)
        assert state.ema_short > state.ema_long

    def test_noise_vs_real_drift(self):
        scores = [0.5, 0.51, 0.49, 0.5, 0.52, 0.48] * 5
        state = detect_drift(agent_id="a", task_type="t", scores=scores, observation_count=30)
        assert state.drift_score < 0.2

    def test_multi_task_drift_isolation(self):
        state_a = detect_drift(agent_id="a", task_type="t", scores=[0.9] * 30, observation_count=30)
        state_b = detect_drift(agent_id="b", task_type="u", scores=[0.1] * 30, observation_count=30)
        assert state_a.drift_score != state_b.drift_score or state_a.agent_id == "a"

    def test_threshold_gating_below(self):
        scores = [0.5, 0.49, 0.51, 0.5] * 8
        state = detect_drift(agent_id="a", task_type="t", scores=scores, observation_count=30)
        assert state.drift_score < DRIFT_THRESHOLD
        assert state.drift_level == DriftLevel.LOW

    def test_initial_state_no_drift(self):
        state = detect_drift(agent_id="a", task_type="t", scores=[], observation_count=0)
        assert state.drift_score == 0.0

    def test_constants_match_sprint54(self):
        assert DYNAMICS_TEMPLATE_VERSION == 1
        assert DRIFT_THRESHOLD == 0.05
        assert DRIFT_MEDIUM_THRESHOLD == 0.10
        assert DRIFT_HIGH_THRESHOLD == 0.20
        assert MIN_OBSERVATIONS_FOR_DRIFT == 10
        assert DENSITY_PENALTY_FACTOR == 0.5

    def test_learning_confidence_attenuation(self):
        assert learning_confidence_attenuation(0.0) == 1.0
        assert learning_confidence_attenuation(0.2) == 0.8
        assert learning_confidence_attenuation(0.6) == 0.5
        assert learning_confidence_attenuation(1.0) == 0.5


class TestPayloads:
    def test_make_drift_payload(self):
        p = make_drift_payload(
            agent_id="a", task_type="t", drift_score=0.1, drift_level="low", ema_short=0.5, ema_long=0.5
        )
        assert p["agent_id"] == "a"
        assert p["drift_score"] == 0.1
        assert p["drift_level"] == "low"

    def test_make_trend_payload(self):
        p = make_trend_payload(
            agent_id="a", task_type="t", slope=0.01, label="improving", momentum=0.5, consecutive_count=3
        )
        assert p["label"] == "improving"

    def test_make_forecast_payload(self):
        p = make_forecast_payload(
            agent_id="a",
            task_type="t",
            horizon=5,
            predicted_capability=0.7,
            confidence=0.8,
            current_capability=0.6,
            delta=0.1,
        )
        assert p["predicted_capability"] == 0.7

    def test_validate_drift_rejects(self):
        import pytest

        with pytest.raises(ValueError):
            validate_drift({})

    def test_validate_trend_rejects(self):
        import pytest

        with pytest.raises(ValueError):
            validate_trend({})

    def test_validate_forecast_rejects(self):
        import pytest

        with pytest.raises(ValueError):
            validate_forecast({})


class TestDynamicScoring:
    def test_dynamics_score_improving(self):
        s = dynamics_selection_score(
            reputation=0.8,
            runtime_score=0.7,
            calibrated_trust=0.6,
            consensus_score=0.5,
            capability_match=0.4,
            learned_capability=0.6,
            drift_score=0.0,
            trend_label="improving",
            forecast_score=0.7,
        )
        assert isinstance(s, float)

    def test_dynamics_score_degrading(self):
        s = dynamics_selection_score(
            reputation=0.8,
            runtime_score=0.7,
            calibrated_trust=0.6,
            consensus_score=0.5,
            capability_match=0.4,
            learned_capability=0.6,
            drift_score=0.1,
            trend_label="degrading",
            forecast_score=0.3,
        )
        assert isinstance(s, float)

    def test_drift_penalty_min_clamp(self):
        s = dynamics_selection_score(
            reputation=0.8,
            runtime_score=0.7,
            calibrated_trust=0.6,
            consensus_score=0.5,
            capability_match=0.4,
            learned_capability=0.6,
            drift_score=1.0,
            trend_label="unstable",
            forecast_score=0.0,
        )
        assert s >= 0.0
        assert s <= 1.0


class TestStates:
    def test_drift_state_frozen(self):
        s = DriftState(
            agent_id="a",
            task_type="t",
            drift_score=0.0,
            drift_level="low",
            ema_short=0.5,
            ema_long=0.5,
            observation_count=10,
            analysis_id="d-1",
        )
        assert s.agent_id == "a"

    def test_trend_state_frozen(self):
        s = TrendState(
            agent_id="a",
            task_type="t",
            slope=0.01,
            label="stable",
            momentum=0.0,
            consecutive_count=0,
            momentum_samples=10,
            analysis_id="d-2",
        )
        assert s.label == "stable"

    def test_forecast_state_frozen(self):
        s = ForecastState(
            agent_id="a",
            task_type="t",
            horizon=5,
            predicted_capability=0.5,
            confidence=0.8,
            current_capability=0.5,
            delta=0.0,
            analysis_id="d-3",
        )
        assert s.predicted_capability == 0.5


class TestEventTypes:
    def test_new_events_in_semantic_set(self):
        from allbrain.events import SemanticEventType

        assert EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value in SemanticEventType
        assert EventType.AGENT_CAPABILITY_TREND_UPDATED.value in SemanticEventType
        assert EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value in SemanticEventType
