from __future__ import annotations

from allbrain.semantic.abstraction import pattern_overlap
from allbrain.semantic.model import (
    DEFAULT_SEMANTIC_LIMIT,
    SemanticConcept,
)


def retrieve_semantic(
    workspace_items: tuple[str, ...],
    concepts: list[SemanticConcept],
    *,
    limit: int = DEFAULT_SEMANTIC_LIMIT,
) -> list[tuple[SemanticConcept, float]]:
    """Retrieve the top-K most relevant semantic concepts.

    Relevance = pattern_overlap between concept signature and workspace items.
    Primary sort: overlap descending.
    Secondary sort: confidence descending (tie-breaker).
    """
    if not concepts:
        return []
    signature = frozenset(workspace_items)
    scored: list[tuple[SemanticConcept, float]] = []
    for c in concepts:
        ov = pattern_overlap(signature, c.pattern_signature)
        if ov > 0.0:
            scored.append((c, ov))
    scored.sort(key=lambda x: (-x[1], -x[0].confidence))
    return scored[:limit]
