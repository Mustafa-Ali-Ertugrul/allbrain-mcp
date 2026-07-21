from __future__ import annotations

import time

import pytest

# IMPORT ORDER MATTERS: import the chain-building modules first
# to resolve circular import (mitigation_learning -> predictive_failure -> objective_system)
from allbrain.domains.governance.mitigation_learning.model import StrategyStats
from allbrain.domains.reasoning.objective_system import ObjectiveResult, ObjectiveWeights

# Tradeoff engine imports (safe after objective_system is fully loaded)
from allbrain.domains.reasoning.tradeoff_engine import (
    ParetoAnalyzer,
    ParetoFrontier,
    Selector,
    TradeoffResult,
    UtilityFunction,
    UtilityResult,
    make_tradeoff_analyzed_payload,
    make_utility_computed_payload,
    validate_tradeoff_analyzed,
    validate_utility_computed,
)


class TestUtilityFunctionStrictInfinityMasking:
    """Tests for the -inf utility mask when safety_pass=False."""

    def test_safety_fail_returns_negative_inf(self):
        """UtilityFunction.compute must return float('-inf') when safety_pass=False."""
        result = ObjectiveResult(
            fault_type="timeout",
            safety=0.2,
            stability=0.5,
            success=0.5,
            efficiency=0.5,
            safety_pass=False,
        )
        weights = ObjectiveWeights("timeout")
        utility = UtilityFunction.compute(result, weights, "p1", "rl")

        assert utility.safety_pass is False
        assert utility.utility == float("-inf")

    def test_safety_pass_returns_finite_utility(self):
        """UtilityFunction.compute must return finite utility when safety_pass=True."""
        result = ObjectiveResult(
            fault_type="timeout",
            safety=0.8,
            stability=0.5,
            success=0.6,
            efficiency=0.5,
            safety_pass=True,
        )
        weights = ObjectiveWeights("timeout")
        utility = UtilityFunction.compute(result, weights, "p1", "rl")

        assert utility.safety_pass is True
        assert utility.utility != float("-inf")
        assert utility.utility > -1e9


class TestParetoAnalyzerSafetyFirstPruning:
    """Tests verifying safety-passed filtering before dominance check."""

    def test_unsafe_candidates_always_dominated(self):
        """Candidates with safety_pass=False must be marked dominated and excluded from frontier."""
        r = [
            UtilityResult("p1", "rl", "timeout", 0.8, 0.7, 0.5, 0.6, 0.5, True),
            UtilityResult("p2", "rl", "timeout", float("-inf"), 0.3, 0.5, 0.5, 0.5, False),
        ]
        f = ParetoAnalyzer.analyze(r)

        assert len(f.frontier) == 1
        assert f.frontier[0].policy_id == "p1"
        assert len(f.dominated) == 1
        assert f.dominated[0].policy_id == "p2"
        assert f.dominated[0].dominated is True

    def test_all_unsafe_no_frontier(self):
        """When all candidates fail safety, frontier must be empty and all dominated."""
        r = [
            UtilityResult("p1", "rl", "timeout", float("-inf"), 0.3, 0.5, 0.5, 0.5, False),
            UtilityResult("p2", "rl", "timeout", float("-inf"), 0.2, 0.5, 0.5, 0.5, False),
        ]
        f = ParetoAnalyzer.analyze(r)

        assert len(f.frontier) == 0
        assert len(f.dominated) == 2


class TestParetoDominanceMatrixAtScale:
    """Benchmark-style test for O(n^2) dominance check performance."""

    def test_pareto_analyze_500_candidates_under_threshold(self):
        """ParetoAnalyzer.analyze with 500 safe candidates should complete within time budget."""
        import random

        random.seed(42)
        candidates = [
            UtilityResult(
                policy_id=f"p{i}",
                strategy="rl",
                fault_type="timeout",
                utility=random.random(),
                safety=random.random(),
                stability=random.random(),
                success=random.random(),
                efficiency=random.random(),
                safety_pass=True,
            )
            for i in range(500)
        ]

        start = time.perf_counter()
        frontier = ParetoAnalyzer.analyze(candidates)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Time budget: 500ms for n=500 on typical CI hardware
        assert elapsed_ms < 500, f"Pareto analyze took {elapsed_ms:.1f}ms, budget 500ms"
        assert isinstance(frontier, ParetoFrontier)
        assert len(frontier.frontier) + len(frontier.dominated) == 500


class TestUtilityAggregationWeights:
    """Tests for weight normalization and float rounding edge cases."""

    def test_weights_normalize_to_one(self):
        """ObjectiveWeights should sum to 1.0 (or close due to float precision)."""
        weights = ObjectiveWeights("timeout")
        total = weights.safety + weights.stability + weights.success + weights.efficiency
        assert abs(total - 1.0) < 1e-9

    def test_utility_respects_weight_distribution(self):
        """Utility should reflect weight emphasis correctly."""
        result = ObjectiveResult(
            fault_type="timeout",
            safety=0.9,
            stability=0.1,
            success=0.1,
            efficiency=0.1,
            safety_pass=True,
        )
        weights = ObjectiveWeights("timeout", safety=0.8, stability=0.1, success=0.05, efficiency=0.05)
        u_high = UtilityFunction.compute(result, weights, "p1", "rl")

        weights_low = ObjectiveWeights("timeout", safety=0.1, stability=0.8, success=0.05, efficiency=0.05)
        u_low = UtilityFunction.compute(result, weights_low, "p1", "rl")

        assert u_high.utility > u_low.utility

    def test_utility_capped_at_one(self):
        """Utility should never exceed 1.0."""
        result = ObjectiveResult(
            fault_type="timeout",
            safety=1.0,
            stability=1.0,
            success=1.0,
            efficiency=1.0,
            safety_pass=True,
        )
        weights = ObjectiveWeights("timeout", safety=0.4, stability=0.3, success=0.2, efficiency=0.1)
        utility = UtilityFunction.compute(result, weights, "p1", "rl")
        assert utility.utility <= 1.0


class TestUtilityEventPayloadForFailedSafety:
    """Tests for utility event payload validation with safety-fail candidates."""

    def test_make_utility_computed_payload_accepts_negative_inf(self):
        """Payload creation must not raise for safety-fail candidates with -inf utility."""
        payload = make_utility_computed_payload(
            policy_id="p1",
            fault_type="timeout",
            utility=float("-inf"),
            safety_pass=False,
        )
        validate_utility_computed(payload)
        assert payload["utility"] == float("-inf")
        assert payload["safety_pass"] is False

    def test_make_utility_computed_payload_finite_utility(self):
        """Payload creation must work for normal finite utilities."""
        payload = make_utility_computed_payload(
            policy_id="p1",
            fault_type="timeout",
            utility=0.75,
            safety_pass=True,
        )
        validate_utility_computed(payload)
        assert payload["utility"] == 0.75
        assert payload["safety_pass"] is True

    def test_tradeoff_analyzed_payload_validation(self):
        """Tradeoff analyzed payload must validate correctly."""
        payload = make_tradeoff_analyzed_payload(
            fault_type="timeout",
            frontier_size=3,
            dominated_count=2,
        )
        validate_tradeoff_analyzed(payload)
        assert payload["frontier_size"] == 3
        assert payload["dominated_count"] == 2
