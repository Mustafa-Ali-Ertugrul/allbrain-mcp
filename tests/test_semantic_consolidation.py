from __future__ import annotations

from allbrain.domains.analysis.semantic.consolidation import (
    apply_decay_to_all,
    compute_concept_confidence,
    find_matching_concept,
    should_create_concept,
    should_forget_concept,
    trim_to_capacity,
)
from allbrain.domains.analysis.semantic.model import SemanticConcept


class TestComputeConceptConfidence:
    def test_base_confidence(self) -> None:
        conf = compute_concept_confidence(0.50, retrieval_count=0, time_since_last_activation=0)
        assert conf == 0.50

    def test_retrieval_bonus(self) -> None:
        conf = compute_concept_confidence(0.50, retrieval_count=4, time_since_last_activation=0)
        # bonus = 4 * 0.05 = 0.20
        assert conf == 0.70

    def test_retrieval_bonus_capped(self) -> None:
        conf = compute_concept_confidence(0.50, retrieval_count=10, time_since_last_activation=0)
        # bonus = min(10 * 0.05, 0.30) = 0.30
        assert conf == 0.80

    def test_decay_reduces_confidence(self) -> None:
        conf = compute_concept_confidence(0.80, retrieval_count=0, time_since_last_activation=5)
        # decay = min(5 * 0.05, 0.50) = 0.25
        assert conf == 0.55

    def test_decay_capped(self) -> None:
        conf = compute_concept_confidence(0.80, retrieval_count=0, time_since_last_activation=20)
        # decay = min(20 * 0.05, 0.50) = 0.50
        assert abs(conf - 0.30) < 1e-9

    def test_clamped_to_zero(self) -> None:
        conf = compute_concept_confidence(0.10, retrieval_count=0, time_since_last_activation=100)
        assert conf == 0.0

    def test_clamped_to_one(self) -> None:
        conf = compute_concept_confidence(0.90, retrieval_count=6, time_since_last_activation=0)
        # bonus = min(6 * 0.05, 0.30) = 0.30
        assert conf == 1.0


class TestFindMatchingConcept:
    def test_exact_match_found(self) -> None:
        concepts = [
            SemanticConcept("c1", frozenset({"a", "b"}), (), 0.8, 0, None),
            SemanticConcept("c2", frozenset({"x", "y"}), (), 0.9, 0, None),
        ]
        match = find_matching_concept(("a", "b"), concepts, threshold=0.3)
        assert match is not None
        assert match.concept_id == "c1"

    def test_no_match_below_threshold(self) -> None:
        concepts = [
            SemanticConcept("c1", frozenset({"a", "b", "c", "d"}), (), 0.8, 0, None),
        ]
        match = find_matching_concept(("x", "y"), concepts, threshold=0.5)
        assert match is None

    def test_empty_concepts(self) -> None:
        match = find_matching_concept(("a", "b"), [], threshold=0.3)
        assert match is None

    def test_best_overlap_selected(self) -> None:
        concepts = [
            SemanticConcept("c1", frozenset({"a"}), (), 0.5, 0, None),
            SemanticConcept("c2", frozenset({"a", "b"}), (), 0.5, 0, None),
        ]
        match = find_matching_concept(("a", "b", "c"), concepts, threshold=0.3)
        assert match is not None
        assert match.concept_id == "c2"


class TestShouldCreateConcept:
    def test_sufficient_episodes(self) -> None:
        assert should_create_concept(3, min_episodes=3) is True

    def test_insufficient_episodes(self) -> None:
        assert should_create_concept(2, min_episodes=3) is False

    def test_zero_episodes(self) -> None:
        assert should_create_concept(0, min_episodes=3) is False


class TestShouldForgetConcept:
    def test_recent_activation_not_forgotten(self) -> None:
        concept = SemanticConcept("c1", frozenset(), (), 0.5, 0, last_activated=95)
        assert should_forget_concept(concept, current_time=100, max_idle=10, min_confidence=0.10) is False

    def test_idle_and_low_confidence_forgotten(self) -> None:
        concept = SemanticConcept("c1", frozenset(), (), 0.05, 0, last_activated=50)
        assert should_forget_concept(concept, current_time=200, max_idle=100, min_confidence=0.10) is True

    def test_never_activated_not_forgotten(self) -> None:
        concept = SemanticConcept("c1", frozenset(), (), 0.05, 0, last_activated=None)
        assert should_forget_concept(concept, current_time=200, max_idle=100) is False

    def test_idle_but_high_confidence_not_forgotten(self) -> None:
        concept = SemanticConcept("c1", frozenset(), (), 0.50, 0, last_activated=0)
        assert should_forget_concept(concept, current_time=200, max_idle=100, min_confidence=0.10) is False


class TestApplyDecay:
    def test_all_concepts_decayed(self) -> None:
        concepts = [
            SemanticConcept("c1", frozenset(), (), 0.80, 0, last_activated=0),
            SemanticConcept("c2", frozenset(), (), 0.50, 0, last_activated=5),
        ]
        decayed = apply_decay_to_all(concepts, current_time=10, decay_rate=0.05)
        assert len(decayed) == 2
        # c1: 0.80 - min(10 * 0.05, 0.50) = 0.30
        assert abs(decayed[0].confidence - 0.30) < 1e-9
        # c2: 0.50 - min(5 * 0.05, 0.50) = 0.25
        assert abs(decayed[1].confidence - 0.25) < 1e-9

    def test_never_activated_not_decayed(self) -> None:
        concepts = [
            SemanticConcept("c1", frozenset(), (), 0.80, 0, last_activated=None),
        ]
        decayed = apply_decay_to_all(concepts, current_time=100)
        assert decayed[0].confidence == 0.80

    def test_decay_clamped(self) -> None:
        concepts = [
            SemanticConcept("c1", frozenset(), (), 0.10, 0, last_activated=0),
        ]
        decayed = apply_decay_to_all(concepts, current_time=100, decay_rate=0.05)
        # decay = min(100 * 0.05, 0.50) = 0.50
        # confidence = 0.10 - 0.50 = 0.0 (clamped in compute)
        assert decayed[0].confidence == 0.0


class TestTrimToCapacity:
    def test_under_capacity_no_change(self) -> None:
        concepts = [SemanticConcept(f"c{i}", frozenset(), (), float(i) * 0.1, 0, None) for i in range(3)]
        remaining, forgotten = trim_to_capacity(concepts, max_concepts=5)
        assert len(remaining) == 3
        assert forgotten == []

    def test_over_capacity_lowest_removed(self) -> None:
        concepts = [
            SemanticConcept("c_low", frozenset(), (), 0.10, 0, None),
            SemanticConcept("c_high", frozenset(), (), 0.90, 0, None),
            SemanticConcept("c_mid", frozenset(), (), 0.50, 0, None),
        ]
        remaining, forgotten = trim_to_capacity(concepts, max_concepts=2)
        assert len(remaining) == 2
        assert "c_low" in forgotten
        assert "c_high" in [c.concept_id for c in remaining]
        assert "c_mid" in [c.concept_id for c in remaining]

    def test_at_capacity_no_change(self) -> None:
        concepts = [SemanticConcept(f"c{i}", frozenset(), (), 0.5, 0, None) for i in range(3)]
        remaining, forgotten = trim_to_capacity(concepts, max_concepts=3)
        assert len(remaining) == 3
        assert forgotten == []
