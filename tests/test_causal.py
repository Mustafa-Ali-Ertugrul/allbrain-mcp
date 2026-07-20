from __future__ import annotations

from allbrain.domains.analysis.causal import (
    CAUSAL_DIVERSITY_CLUSTERS,
    CAUSAL_IMPACT_THRESHOLD,
    CAUSAL_MIN_SAMPLES,
    CAUSAL_TEMPLATE_VERSION,
    COUNTERFACTUAL_TOP_K,
    CausalImpact,
    CausalState,
    CounterfactualResult,
    ImpactDirection,
    estimate_treatment_effect,
    make_counterfactual_payload,
    make_impact_payload,
    simulate_intervention,
    top_alternatives,
    validate_counterfactual,
    validate_impact,
)
from allbrain.events.schemas import EventType
from allbrain.routing import causal_selection_score


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p
        from datetime import datetime

        self.created_at = datetime(2020, 1, 1)


def _make_events():
    """5+ samples per agent to meet CAUSAL_MIN_SAMPLES."""
    evts = []
    for i, (aid, score) in enumerate(
        [
            ("a", 0.8),
            ("a", 0.85),
            ("a", 0.9),
            ("a", 0.82),
            ("a", 0.88),
            ("b", 0.6),
            ("b", 0.55),
            ("b", 0.5),
            ("b", 0.58),
            ("b", 0.52),
        ]
    ):
        evts.append(
            E(
                EventType.TASK_COMPLETED.value,
                f"t{i}",
                {
                    "agent_id": aid,
                    "task_type": "bug_fix",
                    "outcome_score": score,
                    "runtime_score": score,
                },
            )
        )
    return evts


class TestCounterfactualSimulation:
    def test_same_agent_zero_diff(self):
        evts = _make_events()
        r = simulate_intervention(
            agent_id="a",
            task_type="bug_fix",
            actual_agent="a",
            alternative_agent="a",
            events=evts,
        )
        assert abs(r.impact_score) < 1e-9

    def test_swap_changes_outcome(self):
        evts = _make_events()
        r = simulate_intervention(
            agent_id="a",
            task_type="bug_fix",
            actual_agent="a",
            alternative_agent="b",
            events=evts,
        )
        assert r.impact_score != 0.0

    def test_multi_intervention_isolation(self):
        evts = _make_events()
        r1 = simulate_intervention(
            agent_id="a", task_type="bug_fix", actual_agent="a", alternative_agent="b", events=evts
        )
        r2 = simulate_intervention(
            agent_id="b", task_type="bug_fix", actual_agent="b", alternative_agent="a", events=evts
        )
        assert r1.impact_score != r2.impact_score

    def test_top_alternatives(self):
        evts = _make_events()
        results = top_alternatives(agent_id="a", task_type="bug_fix", events=evts)
        assert len(results) > 0
        for r in results:
            assert isinstance(r, CounterfactualResult)

    def test_no_side_effects(self):
        evts1 = _make_events()
        evts2 = _make_events()
        r1 = simulate_intervention(
            agent_id="a", task_type="bug_fix", actual_agent="a", alternative_agent="b", events=evts1
        )
        r2 = simulate_intervention(
            agent_id="a", task_type="bug_fix", actual_agent="a", alternative_agent="b", events=evts2
        )
        assert r1.impact_score == r2.impact_score

    def test_event_integrity(self):
        evts = _make_events()
        r = simulate_intervention(
            agent_id="a", task_type="bug_fix", actual_agent="a", alternative_agent="b", events=evts
        )
        assert -1.0 <= r.impact_score <= 1.0
        assert 0.0 <= r.confidence <= 1.0

    def test_impact_direction(self):
        assert ImpactDirection.POSITIVE == "positive"
        assert ImpactDirection.NEGATIVE == "negative"

    def test_constants_match_sprint55(self):
        assert CAUSAL_TEMPLATE_VERSION == 1
        assert COUNTERFACTUAL_TOP_K == 3
        assert CAUSAL_MIN_SAMPLES == 5
        assert CAUSAL_IMPACT_THRESHOLD == 0.05
        assert CAUSAL_DIVERSITY_CLUSTERS == 2

    def test_confidence_monotonic(self):
        evts = _make_events()
        r = simulate_intervention(
            agent_id="a", task_type="bug_fix", actual_agent="a", alternative_agent="b", events=evts
        )
        assert r.confidence > 0.5

    def test_bounded_output(self):
        r = simulate_intervention(agent_id="x", task_type="y", actual_agent="x", alternative_agent="z", events=[])
        assert r.impact_score == 0.0
        assert r.confidence == 0.0
        assert r.sample_count == 0

    def test_estimator(self):
        evts = _make_events()
        imp = estimate_treatment_effect(agent_a="a", agent_b="b", task_type="bug_fix", events=evts)
        assert isinstance(imp, CausalImpact)
        assert -1.0 <= imp.impact_score <= 1.0

    def test_payloads(self):
        cf = make_counterfactual_payload(
            agent_id="a",
            task_type="t",
            actual_agent="a",
            alternative_agent="b",
            actual_outcome=0.5,
            alternative_outcome=0.8,
            impact_score=0.3,
            confidence=0.8,
            sample_count=5,
        )
        assert cf["impact_score"] == 0.3
        validate_counterfactual(cf)

        imp = make_impact_payload(
            agent_id="a",
            task_type="t",
            alternative_agent="b",
            impact_score=0.3,
            confidence=0.8,
            sample_count=5,
        )
        assert imp["impact_score"] == 0.3
        validate_impact(imp)

    def test_causal_scoring(self):
        s = causal_selection_score(
            reputation=0.8,
            runtime_score=0.7,
            calibrated_trust=0.6,
            consensus_score=0.5,
            capability_match=0.4,
            learned_capability=0.6,
            drift_score=0.0,
            trend_label="improving",
            forecast_score=0.7,
            impact_score=0.3,
            causal_confidence=0.8,
        )
        assert isinstance(s, float)
        assert 0.0 <= s <= 1.0

    def test_semantic_events(self):
        from allbrain.events import SemanticEventType

        assert EventType.AGENT_COUNTERFACTUAL_RUN.value in SemanticEventType
        assert EventType.AGENT_CAUSAL_IMPACT_RECORDED.value in SemanticEventType

    def test_frozen_states(self):
        cf = CounterfactualResult(
            agent_id="a",
            task_type="t",
            actual_agent="a",
            alternative_agent="b",
            actual_outcome=0.5,
            alternative_outcome=0.8,
            impact_score=0.3,
            confidence=0.8,
            sample_count=5,
            direction="positive",
            analysis_id="x",
        )
        assert cf.agent_id == "a"
        ci = CausalImpact(
            agent_id="a",
            task_type="t",
            alternative_agent="b",
            impact_score=0.3,
            confidence=0.8,
            sample_count=5,
            analysis_id="x",
        )
        assert ci.impact_score == 0.3
