from __future__ import annotations

from allbrain.causal import CausalImpact, estimate_treatment_effect
from allbrain.events.schemas import EventType


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        from datetime import datetime

        self.created_at = datetime(2020, 1, 1)


def _build_events(a_scores, b_scores, task_type="bug_fix"):
    evts = []
    for i, s in enumerate(a_scores):
        evts.append(
            E(
                EventType.TASK_COMPLETED.value,
                f"a{i}",
                {"agent_id": "a", "task_type": task_type, "outcome_score": s, "runtime_score": s},
            )
        )
    for i, s in enumerate(b_scores):
        evts.append(
            E(
                EventType.TASK_COMPLETED.value,
                f"b{i}",
                {"agent_id": "b", "task_type": task_type, "outcome_score": s, "runtime_score": s},
            )
        )
    return evts


class TestEstimator:
    def test_positive_impact(self):
        evts = _build_events([0.3, 0.35, 0.4, 0.3, 0.35], [0.8, 0.85, 0.9, 0.8, 0.85])
        imp = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts)
        assert imp.impact_score > 0.1
        assert imp.confidence > 0.4

    def test_negative_impact(self):
        evts = _build_events([0.8, 0.85, 0.9, 0.8, 0.85], [0.3, 0.35, 0.4, 0.3, 0.35])
        imp = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts)
        assert imp.impact_score < -0.1

    def test_neutral_impact(self):
        evts = _build_events([0.5, 0.55, 0.5, 0.5, 0.55], [0.5, 0.52, 0.5, 0.5, 0.53])
        imp = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts)
        assert abs(imp.impact_score) < 0.1

    def test_bounded_output(self):
        evts = _build_events([0.0, 0.0, 0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0, 1.0])
        imp = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts)
        assert -1.0 <= imp.impact_score <= 1.0

    def test_low_sample_no_impact(self):
        evts = _build_events([0.5], [0.8])
        imp = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts)
        assert imp.impact_score == 0.0
        assert imp.confidence == 0.0

    def test_confidence_grows_with_samples(self):
        evts_small = _build_events([0.3] * 5, [0.8] * 5)
        evts_large = _build_events([0.3] * 20, [0.8] * 20)
        imp_small = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts_small)
        imp_large = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts_large)
        assert imp_large.confidence > imp_small.confidence

    def test_same_distribution(self):
        evts = _build_events([0.5] * 10, [0.5] * 10)
        imp = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts)
        assert abs(imp.impact_score) < 0.01

    def test_context_normalization(self):
        evts = _build_events([0.9, 0.9, 0.9, 0.9, 0.9], [0.7, 0.7, 0.7, 0.7, 0.7])
        imp = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts)
        assert imp.impact_score < 0  # B worse than A

    def test_missing_data(self):
        imp = estimate_treatment_effect(agent_a="x", agent_b="y", task_type="none", events=[])
        assert imp.impact_score == 0.0
