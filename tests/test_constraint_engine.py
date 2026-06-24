from __future__ import annotations

import pytest
from allbrain.value_alignment import ConstraintEngine, AlignmentScoreTracker, Constraint
from allbrain.value_alignment.model import AlignmentResult


class TestConstraintEngine:
    def test_all_pass(self):
        ce = ConstraintEngine()
        score = ce.check("timeout", {"safety": 0.7, "stability": 0.5}, safety_threshold=0.50)
        assert score.passed
        assert score.overall_score >= 0.9

    def test_safety_fail_hard_violation(self):
        ce = ConstraintEngine()
        score = ce.check("memory_corruption", {"safety": 0.2, "stability": 0.5}, safety_threshold=0.80)
        assert not score.passed
        assert "safety_min" in score.hard_violations

    def test_stability_fail_soft_only(self):
        ce = ConstraintEngine()
        score = ce.check("timeout", {"safety": 0.6, "stability": 0.2}, safety_threshold=0.50)
        assert score.passed
        assert len(score.soft_penalties) > 0

    def test_align_result_blocked(self):
        ce = ConstraintEngine()
        score = ce.check("memory_corruption", {"safety": 0.1, "stability": 0.1}, safety_threshold=0.80)
        result = ce.align(score)
        assert result.blocked

    def test_alignment_score_tracker(self):
        tracker = AlignmentScoreTracker()
        score = ConstraintEngine().check("timeout", {"safety": 0.8, "stability": 0.5}, 0.50)
        r = AlignmentResult(score=score, blocked=False)
        for _ in range(10):
            tracker.record(r)
        assert tracker.is_aligned("timeout")

    def test_constraint_threshold_check(self):
        c = Constraint("safety_min", "safety", 0.50, True)
        assert c.check(0.70)
        assert not c.check(0.30)