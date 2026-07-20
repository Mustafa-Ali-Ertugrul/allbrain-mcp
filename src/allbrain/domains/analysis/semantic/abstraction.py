from __future__ import annotations

from allbrain.domains.analysis.semantic.model import (
    CONSOLIDATION_THRESHOLD,
    SemanticConcept,
)


def pattern_overlap(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity between two pattern signatures."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def generalize_signature(
    concept: SemanticConcept,
    workspace_items: set[str],
    min_overlap: float = CONSOLIDATION_THRESHOLD,
) -> frozenset[str]:
    """Generalize a concept's pattern signature by merging with new workspace_items.

    Only items present in BOTH the concept signature AND the new items survive.
    This produces a more general (narrower) signature over time.
    If overlap is below threshold, returns the concept's original signature.
    """
    overlap = pattern_overlap(concept.pattern_signature, frozenset(workspace_items))
    if overlap < min_overlap:
        return concept.pattern_signature
    merged = set(concept.pattern_signature) & workspace_items
    return frozenset(merged)


def extract_pattern_from_episode(
    workspace_items: tuple[str, ...],
) -> frozenset[str]:
    """Extract a pattern signature from an episode's workspace items.

    The pattern signature is simply the set of workspace items.
    Future refinements may weigh or filter items.
    """
    return frozenset(workspace_items)
