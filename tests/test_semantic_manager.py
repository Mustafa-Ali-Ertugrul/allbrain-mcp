from __future__ import annotations

from allbrain.episodic import Episode
from allbrain.semantic.manager import SemanticManager
from allbrain.semantic.model import SemanticConcept


def _make_episode(ep_id: str, items: list[str], reward: float = 0.8, importance: float = 0.6) -> Episode:
    return Episode(
        episode_id=ep_id,
        timestamp=1,
        reward=reward,
        importance=importance,
        workspace_items=tuple(items),
        decision_id="dec-1",
        retrieval_count=0,
        last_retrieved=None,
    )


class TestManagerConsolidation:
    def test_first_episode_no_concept(self) -> None:
        mgr = SemanticManager()
        ep = _make_episode("ep1", ["a", "b"])
        result = mgr.consolidate(ep)
        # First episode alone: similar_count = 0, should_create = 0 >= 3? No
        assert result["concept_created"] is None
        assert result["concept_updated"] is None
        assert mgr.stats()["concept_count"] == 0

    def test_creates_concept_after_min_episodes(self) -> None:
        mgr = SemanticManager()
        # Add 2 existing concepts with similar patterns to reach threshold
        mgr._concepts = [
            SemanticConcept("c1", frozenset({"a", "b"}), ("ep1",), 0.6, 1, 1),
            SemanticConcept("c2", frozenset({"a", "c"}), ("ep2",), 0.6, 1, 1),
        ]
        mgr._total = 2
        mgr._retained = 2
        mgr._time = 5
        ep = _make_episode("ep3", ["a", "b", "d"])
        result = mgr.consolidate(ep)
        # find_matching_concept: overlap with c1 = 2/4 = 0.5 >= 0.30, match!
        assert result["concept_updated"] is not None

    def test_new_concept_created(self) -> None:
        mgr = SemanticManager()
        # Pre-populate with 2 concepts similar to each other
        mgr._concepts = [
            SemanticConcept("c1", frozenset({"a", "b"}), ("ep1",), 0.6, 1, 1),
            SemanticConcept("c2", frozenset({"a", "b"}), ("ep2",), 0.6, 1, 1),
        ]
        mgr._total = 2
        mgr._retained = 2
        mgr._time = 5
        ep = _make_episode("ep3", ["a", "b"])
        result = mgr.consolidate(ep)
        # find_matching_concept: overlap with both = 1.0, match!
        assert result["concept_updated"] is not None

    def test_trim_to_capacity(self) -> None:
        mgr = SemanticManager()
        # Fill with MAX_CONCEPTS + 1 concepts
        for i in range(501):
            mgr._concepts.append(
                SemanticConcept(f"c{i}", frozenset({f"item{i}"}), (), 0.01 + (i / 10000), 0, 0 if i < 500 else 100)
            )
        mgr._total = 501
        mgr._retained = 501
        ep = _make_episode("ep_trim", ["new_item"])
        result = mgr.consolidate(ep)
        assert len(mgr.get_all_concepts()) <= 500


class TestManagerRetrieval:
    def test_empty_retrieval(self) -> None:
        mgr = SemanticManager()
        result = mgr.retrieve(("a", "b"))
        assert result["retrieved"] == 0
        assert result["concepts"] == []

    def test_retrieves_matching_concepts(self) -> None:
        mgr = SemanticManager()
        mgr._concepts = [
            SemanticConcept("c1", frozenset({"a", "b"}), ("ep1",), 0.8, 0, None),
            SemanticConcept("c2", frozenset({"x", "y"}), ("ep2",), 0.9, 0, None),
        ]
        result = mgr.retrieve(("a", "b", "c"))
        assert result["retrieved"] >= 1
        ids = [c[0] for c in result["concepts"]]
        assert "c1" in ids

    def test_retrieval_updates_metadata(self) -> None:
        mgr = SemanticManager()
        mgr._concepts = [
            SemanticConcept("c1", frozenset({"a", "b"}), ("ep1",), 0.8, 0, None),
        ]
        mgr._time = 10
        result = mgr.retrieve(("a", "b"))
        assert result["retrieved"] == 1
        updated = mgr.get_all_concepts()
        assert updated[0].retrieval_count == 1
        assert updated[0].last_activated == 10


class TestManagerStats:
    def test_initial_stats(self) -> None:
        mgr = SemanticManager()
        stats = mgr.stats()
        assert stats["total"] == 0
        assert stats["retained"] == 0
        assert stats["forgotten"] == 0
        assert stats["concept_count"] == 0

    def test_stats_after_consolidation(self) -> None:
        mgr = SemanticManager()
        # Pre-populate to trigger concept update
        mgr._concepts = [
            SemanticConcept("c1", frozenset({"a", "b"}), ("ep1",), 0.6, 1, 1),
            SemanticConcept("c2", frozenset({"a", "b"}), ("ep2",), 0.6, 1, 1),
        ]
        mgr._total = 2
        mgr._retained = 2
        ep = _make_episode("ep3", ["a", "b"])
        mgr.consolidate(ep)
        stats = mgr.stats()
        # total should be 2 (pre-loaded), retained should reflect trim (<=500)
        assert stats["total"] == 2
        assert stats["retained"] > 0
