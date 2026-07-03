from __future__ import annotations

import pytest

from allbrain.value_alignment import AlignmentScoreTracker, Constraint, ConstraintEngine
from allbrain.value_alignment.model import AlignmentResult, AlignmentScore


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

    # ----- live-lock protection tests -----

    def test_align_resets_on_success(self):
        ce = ConstraintEngine()
        score_pass = ce.check("timeout", {"safety": 0.8, "stability": 0.5}, 0.50)
        result = ce.align(score_pass)
        assert result.consecutive_failures == 0
        assert result.escalation_level == 0

    def test_align_counts_consecutive_failures(self):
        ce = ConstraintEngine()
        score = ce.check("memory_corruption", {"safety": 0.1, "stability": 0.5}, 0.80)
        r1 = ce.align(score)
        assert r1.consecutive_failures == 1
        assert r1.escalation_level == 0

        r2 = ce.align(score)
        assert r2.consecutive_failures == 2
        assert r2.escalation_level == 0

    def test_align_escalates_to_attention(self):
        ce = ConstraintEngine()
        score = ce.check("memory_corruption", {"safety": 0.1, "stability": 0.5}, 0.80)
        for _ in range(2):
            ce.align(score)
        r3 = ce.align(score)
        assert r3.consecutive_failures == 3
        assert r3.escalation_level == 1
        assert "attention" in r3.reason

    def test_align_escalates_to_supervisor(self):
        ce = ConstraintEngine()
        score = ce.check("memory_corruption", {"safety": 0.1, "stability": 0.5}, 0.80)
        for _ in range(4):
            ce.align(score)
        r5 = ce.align(score)
        assert r5.consecutive_failures == 5
        assert r5.escalation_level == 2
        assert r5.reason == "supervisor_required"
        assert r5.blocked

    def test_align_supervisor_forces_block(self):
        """At supervisor level, blocked=True even if score.passed would allow it."""
        ce = ConstraintEngine()
        score = ce.check("memory_corruption", {"safety": 0.1, "stability": 0.5}, 0.80)
        for _ in range(5):
            ce.align(score)
        r = ce.align(score)
        assert r.blocked

    def test_reset_interrupts_escalation(self):
        ce = ConstraintEngine()
        score_fail = ce.check("timeout", {"safety": 0.1, "stability": 0.5}, 0.80)
        for _ in range(2):
            ce.align(score_fail)
        ce.reset_failures("timeout")
        r = ce.align(score_fail)
        assert r.consecutive_failures == 1  # reset, then one new failure
        assert r.escalation_level == 0

    def test_reset_by_successful_check(self):
        ce = ConstraintEngine()
        score_fail = ce.check("timeout", {"safety": 0.1, "stability": 0.5}, 0.80)
        for _ in range(3):
            ce.align(score_fail)
        score_pass = ce.check("timeout", {"safety": 0.8, "stability": 0.5}, 0.50)
        r = ce.align(score_pass)
        assert r.consecutive_failures == 0
        assert r.escalation_level == 0


class TestAlignmentScoreTrackerLiveLock:
    def test_detect_oscillation_insufficient_history(self):
        tracker = AlignmentScoreTracker()
        assert not tracker.detect_oscillation("timeout")

    def test_detect_oscillation_no_oscillation(self):
        tracker = AlignmentScoreTracker()
        for _ in range(10):
            s = AlignmentScore("t", 0.2, {}, [], [], False)
            tracker.record(AlignmentResult(score=s, blocked=True, reason="hard_violation"))
        assert not tracker.detect_oscillation("t")

    def test_detect_oscillation_detected(self):
        tracker = AlignmentScoreTracker()
        # Create an oscillation pattern: 0.1, 0.9, 0.1, 0.9, 0.1, 0.9
        vals = [0.1, 0.9, 0.1, 0.9, 0.1, 0.9]
        for v in vals:
            s = AlignmentScore("t", v, {}, [], [], v >= 0.5)
            tracker.record(AlignmentResult(score=s, blocked=v < 0.5, reason=""))
        assert tracker.detect_oscillation("t")

    def test_detect_oscillation_isolates_fault_types(self):
        tracker = AlignmentScoreTracker()
        # Oscillation on "t1" but not "t2"
        vals = [0.1, 0.9, 0.1, 0.9, 0.1, 0.9]
        for v in vals:
            s1 = AlignmentScore("t1", v, {}, [], [], v >= 0.5)
            s2 = AlignmentScore("t2", 0.8, {}, [], [], True)
            tracker.record(AlignmentResult(score=s1, blocked=v < 0.5, reason=""))
            tracker.record(AlignmentResult(score=s2, blocked=False, reason=""))
        assert tracker.detect_oscillation("t1")
        assert not tracker.detect_oscillation("t2")
