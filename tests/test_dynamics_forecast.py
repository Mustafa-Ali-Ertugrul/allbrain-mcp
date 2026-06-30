from __future__ import annotations

from allbrain.dynamics import predict
from allbrain.dynamics.model import FORECAST_CAP_PER_STEP


class TestForecast:
    def test_linear_forecast_accuracy(self):
        scores = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75]
        state = predict(agent_id="a", task_type="t", scores=scores, horizon=5)
        assert state.predicted_capability > state.current_capability

    def test_zero_delta_forecast(self):
        scores = [0.5, 0.5, 0.5, 0.5, 0.5]
        state = predict(agent_id="a", task_type="t", scores=scores, horizon=5)
        assert abs(state.predicted_capability - state.current_capability) < 1e-9

    def test_negative_trend_forecast(self):
        scores = [0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35]
        state = predict(agent_id="a", task_type="t", scores=scores, horizon=5)
        assert state.predicted_capability < state.current_capability

    def test_horizon_scaling(self):
        scores = [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75]
        s1 = predict(agent_id="a", task_type="t", scores=scores, horizon=1)
        s5 = predict(agent_id="a", task_type="t", scores=scores, horizon=5)
        assert s5.predicted_capability >= s1.predicted_capability

    def test_cap_per_step_respected(self):
        scores = [0.1, 0.9, 0.1, 0.9, 0.1]
        state = predict(agent_id="a", task_type="t", scores=scores, horizon=10)
        assert abs(state.predicted_capability - state.current_capability) <= FORECAST_CAP_PER_STEP * 10 + 0.01

    def test_low_confidence_few_observations(self):
        scores = [0.5, 0.6]
        state = predict(agent_id="a", task_type="t", scores=scores, horizon=5)
        assert state.confidence < 0.5

    def test_frozen(self):
        state = predict(agent_id="a", task_type="t", scores=[0.5] * 5, horizon=5)
        assert state.agent_id == "a"
        assert state.horizon == 5
