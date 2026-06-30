from __future__ import annotations

from allbrain.episodic.model import NOVELTY_SAMPLE_WINDOW, Episode


def compute_importance(
    *,
    reward: float,
    workspace_activation: float,
    novelty: float,
) -> float:
    """importance = reward × workspace_activation × novelty

    Softened triple product: each term is in (0, 1) range.
    If any term is 0, importance = 0 (zero importance → won't be stored).
    """
    return float(reward) * float(workspace_activation) * float(novelty)


def compute_novelty(
    workspace_items: list[str],
    recent_episodes: list[Episode],
    *,
    sample_window: int = NOVELTY_SAMPLE_WINDOW,
) -> float:
    """novelty = 1 - max_similarity_to_recent

    Similarity = Jaccard(workspace_items, episode.workspace_items).
    If no recent episodes, novelty = 1.0 (fully novel).
    """
    if not recent_episodes:
        return 1.0
    max_sim = 0.0
    for ep in recent_episodes[-sample_window:]:
        sim = jaccard_similarity(workspace_items, list(ep.workspace_items))
        max_sim = max(max_sim, sim)
    return max(0.0, 1.0 - max_sim)


def jaccard_similarity(a: list[str], b: list[str]) -> float:
    """Jaccard similarity between two lists of item IDs."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
