from __future__ import annotations

from allbrain.semantic.abstraction import (
    extract_pattern_from_episode,
    generalize_signature,
    pattern_overlap,
)
from allbrain.semantic.model import SemanticConcept


class TestPatternOverlap:
    def test_exact_match(self) -> None:
        a = frozenset({"x", "y", "z"})
        b = frozenset({"x", "y", "z"})
        assert pattern_overlap(a, b) == 1.0

    def test_no_overlap(self) -> None:
        a = frozenset({"x", "y"})
        b = frozenset({"a", "b"})
        assert pattern_overlap(a, b) == 0.0

    def test_partial_overlap(self) -> None:
        a = frozenset({"x", "y", "z"})
        b = frozenset({"x", "y"})
        assert pattern_overlap(a, b) == 2.0 / 3.0

    def test_both_empty(self) -> None:
        assert pattern_overlap(frozenset(), frozenset()) == 1.0

    def test_one_empty(self) -> None:
        assert pattern_overlap(frozenset({"a"}), frozenset()) == 0.0


class TestGeneralizeSignature:
    def test_high_overlap_intersection(self) -> None:
        concept = SemanticConcept(
            concept_id="c1",
            pattern_signature=frozenset({"a", "b", "c"}),
            episodes=("ep1",),
            confidence=0.8,
            retrieval_count=0,
            last_activated=None,
        )
        new_items = {"a", "b", "d"}
        result = generalize_signature(concept, new_items, min_overlap=0.3)
        # Items in BOTH: a, b
        assert result == frozenset({"a", "b"})

    def test_below_threshold_returns_original(self) -> None:
        concept = SemanticConcept(
            concept_id="c1",
            pattern_signature=frozenset({"a", "b", "c", "d", "e"}),
            episodes=("ep1",),
            confidence=0.8,
            retrieval_count=0,
            last_activated=None,
        )
        new_items = {"x", "y"}
        result = generalize_signature(concept, new_items, min_overlap=0.5)
        # Overlap = 0/7 = 0.0 < 0.5, so original returned
        assert result == frozenset({"a", "b", "c", "d", "e"})

    def test_exact_overlap_threshold(self) -> None:
        concept = SemanticConcept(
            concept_id="c1",
            pattern_signature=frozenset({"a", "b"}),
            episodes=("ep1",),
            confidence=0.8,
            retrieval_count=0,
            last_activated=None,
        )
        new_items = {"a", "b"}
        result = generalize_signature(concept, new_items, min_overlap=0.5)
        assert result == frozenset({"a", "b"})


class TestExtractPattern:
    def test_from_workspace_items(self) -> None:
        items = ("item1", "item2", "item3")
        result = extract_pattern_from_episode(items)
        assert result == frozenset({"item1", "item2", "item3"})

    def test_empty_items(self) -> None:
        assert extract_pattern_from_episode(()) == frozenset()

    def test_duplicates_collapsed(self) -> None:
        items = ("a", "a", "b")
        result = extract_pattern_from_episode(items)
        assert result == frozenset({"a", "b"})
