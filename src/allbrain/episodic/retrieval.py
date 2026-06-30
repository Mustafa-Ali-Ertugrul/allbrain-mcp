from __future__ import annotations

from allbrain.episodic.importance import jaccard_similarity
from allbrain.episodic.model import DEFAULT_RETRIEVAL_LIMIT, Episode


def retrieve_similar(
    workspace_items: list[str],
    episodes: list[Episode],
    *,
    limit: int = DEFAULT_RETRIEVAL_LIMIT,
) -> list[tuple[Episode, float]]:
    """Returns top-K most similar past episodes.

    Primary sort: similarity (Jaccard) descending.
    Secondary sort: importance descending (tie-breaker).
    """
    if not episodes:
        return []
    scored: list[tuple[Episode, float]] = []
    for ep in episodes:
        sim = jaccard_similarity(workspace_items, list(ep.workspace_items))
        scored.append((ep, sim))
    # Primary: similarity desc, secondary: importance desc
    scored.sort(key=lambda x: (-x[1], -x[0].importance))
    return scored[:limit]
