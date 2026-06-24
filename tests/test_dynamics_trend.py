from __future__ import annotations

from allbrain.dynamics import classify_trend, TrendLabel
from allbrain.dynamics.model import TREND_HYSTERESIS_COUNT, TREND_OSCILLATION_VARIANCE


class TestTrendClassification:
    def test_improving_trend(self):
        scores = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75]
        state = classify_trend(agent_id="a", task_type="t", scores=scores)
        assert state.label == TrendLabel.IMPROVING

    def test_degrading_trend(self):
        scores = [0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35]
        state = classify_trend(agent_id="a", task_type="t", scores=scores)
        assert state.label == TrendLabel.DEGRADING

    def test_flat_trend(self):
        scores = [0.5] * 15
        state = classify_trend(agent_id="a", task_type="t", scores=scores)
        assert state.label == TrendLabel.STABLE

    def test_hysteresis_prevents_flip(self):
        scores = [0.5] * 7 + [0.52, 0.53]
        state = classify_trend(agent_id="a", task_type="t", scores=scores)
        assert state.label == TrendLabel.STABLE

    def test_slope_sensitivity(self):
        scores = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.9, 0.8, 0.7, 0.6]
        state = classify_trend(agent_id="a", task_type="t", scores=scores)
        assert state.slope != 0.0

    def test_multi_agent_isolation(self):
        state_a = classify_trend(agent_id="a", task_type="t", scores=[0.4]*10)
        state_b = classify_trend(agent_id="b", task_type="u", scores=[0.9]*10)
        assert state_a.agent_id == "a"
        assert state_b.agent_id == "b"

    def test_momentum_computed(self):
        scores = [0.3, 0.5, 0.4, 0.6, 0.5, 0.7, 0.6, 0.8, 0.7, 0.9]
        state = classify_trend(agent_id="a", task_type="t", scores=scores)
        assert isinstance(state.momentum, float)

    def test_consecutive_count(self):
        scores = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75]
        state = classify_trend(agent_id="a", task_type="t", scores=scores)
        assert state.consecutive_count >= 0