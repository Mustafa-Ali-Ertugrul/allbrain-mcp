from __future__ import annotations

import pytest

from allbrain.episodic.importance import compute_importance, compute_novelty, jaccard_similarity
from allbrain.episodic.model import Episode


class TestJaccardSimilarity:
    def test_exact_match(self):
        a = ["a", "b", "c"]
        b = ["a", "b", "c"]
        assert jaccard_similarity(a, b) == 1.0

    def test_no_overlap(self):
        a = ["a", "b"]
        b = ["c", "d"]
        assert jaccard_similarity(a, b) == 0.0

    def test_partial_overlap(self):
        a = ["a", "b", "c"]
        b = ["a", "d", "e"]
        assert jaccard_similarity(a, b) == pytest.approx(1.0 / 5.0)

    def test_both_empty(self):
        assert jaccard_similarity([], []) == 1.0

    def test_one_empty(self):
        assert jaccard_similarity(["a"], []) == 0.0
        assert jaccard_similarity([], ["a"]) == 0.0

    def test_superset(self):
        a = ["a", "b", "c"]
        b = ["a", "b"]
        assert jaccard_similarity(a, b) == pytest.approx(2.0 / 3.0)


class TestComputeImportance:
    def test_basic_formula(self):
        imp = compute_importance(reward=0.8, workspace_activation=0.5, novelty=0.6)
        assert imp == pytest.approx(0.8 * 0.5 * 0.6)

    def test_zero_reward(self):
        imp = compute_importance(reward=0.0, workspace_activation=0.5, novelty=0.6)
        assert imp == 0.0

    def test_zero_activation(self):
        imp = compute_importance(reward=0.8, workspace_activation=0.0, novelty=0.6)
        assert imp == 0.0

    def test_zero_novelty(self):
        imp = compute_importance(reward=0.8, workspace_activation=0.5, novelty=0.0)
        assert imp == 0.0

    def test_max_importance(self):
        imp = compute_importance(reward=1.0, workspace_activation=1.0, novelty=1.0)
        assert imp == 1.0

    def test_mid_range(self):
        imp = compute_importance(reward=0.5, workspace_activation=0.5, novelty=0.5)
        assert imp == pytest.approx(0.125)

    def test_floats_only(self):
        imp = compute_importance(reward=0.7, workspace_activation=0.3, novelty=0.9)
        assert imp == pytest.approx(0.7 * 0.3 * 0.9)

    def test_novelty_no_recent(self):
        n = compute_novelty(["a", "b"], [])
        assert n == 1.0


class TestComputeNovelty:
    def test_completely_novel(self):
        recent = [
            Episode("ep1", 1, 0.5, 0.5, ("c", "d"), "d1"),
        ]
        n = compute_novelty(["a", "b"], recent)
        # Jaccard(["a","b"], ["c","d"]) = 0.0 → novelty = 1 - 0 = 1.0
        assert n == 1.0

    def test_exact_match(self):
        recent = [
            Episode("ep1", 1, 0.5, 0.5, ("a", "b"), "d1"),
        ]
        n = compute_novelty(["a", "b"], recent)
        # Jaccard = 1.0 → novelty = 0.0
        assert n == 0.0

    def test_partial_novelty(self):
        recent = [
            Episode("ep1", 1, 0.5, 0.5, ("a", "c"), "d1"),
        ]
        n = compute_novelty(["a", "b"], recent)
        # Jaccard(["a","b"], ["a","c"]) = 1/3 ≈ 0.333 → novelty = 1 - 0.333 = 0.667
        assert n == pytest.approx(1.0 - 1.0 / 3.0, abs=1e-4)

    def test_sample_window(self):
        episodes = [
            Episode("ep1", 1, 0.5, 0.5, ("a",), "d1"),
            Episode("ep2", 2, 0.5, 0.5, ("b",), "d2"),
            Episode("ep3", 3, 0.5, 0.5, ("a", "b"), "d3"),
        ]
        n = compute_novelty(["a", "b"], episodes, sample_window=2)
        # Last 2: ep2 (("b",), sim=0.5), ep3 (("a","b"), sim=1.0)
        # max_sim = 1.0 → novelty = 0.0
        assert n == 0.0
