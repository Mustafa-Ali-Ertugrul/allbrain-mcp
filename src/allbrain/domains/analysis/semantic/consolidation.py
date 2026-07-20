from __future__ import annotations

from allbrain.domains.analysis.semantic.abstraction import (
    extract_pattern_from_episode,
    pattern_overlap,
)
from allbrain.domains.analysis.semantic.model import (
    CONFIDENCE_DECAY_RATE,
    CONSOLIDATION_MIN_EPISODES,
    CONSOLIDATION_THRESHOLD,
    MAX_CONCEPTS,
    SemanticConcept,
)


def compute_concept_confidence(
    base_confidence: float,
    retrieval_count: int,
    time_since_last_activation: int,
    decay_rate: float = CONFIDENCE_DECAY_RATE,
) -> float:
    """Confidence = base_confidence + retrieval_bonus - decay.

    retrieval_bonus: min(retrieval_count * 0.05, 0.30).
    decay: min(time_since_last_activation * decay_rate, 0.50).
    Clamped to [0, 1].
    """
    bonus = min(retrieval_count * 0.05, 0.30)
    decay = min(time_since_last_activation * decay_rate, 0.50)
    return max(0.0, min(1.0, base_confidence + bonus - decay))


def find_matching_concept(
    workspace_items: tuple[str, ...],
    concepts: list[SemanticConcept],
    threshold: float = CONSOLIDATION_THRESHOLD,
) -> SemanticConcept | None:
    """Find the best matching concept for a given episode's workspace items.

    Returns the concept with the highest pattern_overlap above threshold.
    """
    signature = extract_pattern_from_episode(workspace_items)
    best: SemanticConcept | None = None
    best_overlap = threshold
    for c in concepts:
        ov = pattern_overlap(signature, c.pattern_signature)
        if ov > best_overlap:
            best_overlap = ov
            best = c
    return best


def should_create_concept(
    matched_episodes: int,
    min_episodes: int = CONSOLIDATION_MIN_EPISODES,
) -> bool:
    """Create a new concept when enough episodes share a pattern."""
    return matched_episodes >= min_episodes


def should_forget_concept(
    concept: SemanticConcept,
    current_time: int,
    *,
    max_idle: int = 100,
    min_confidence: float = 0.10,
) -> bool:
    """Forget a concept if idle too long AND confidence is too low."""
    if concept.last_activated is None:
        return False
    idle = current_time - concept.last_activated
    return idle > max_idle and concept.confidence < min_confidence


def apply_decay_to_all(
    concepts: list[SemanticConcept],
    current_time: int,
    decay_rate: float = CONFIDENCE_DECAY_RATE,
) -> list[SemanticConcept]:
    """Apply confidence decay to all concepts that haven't been activated recently.

    Returns new concept list with decayed confidence values.
    """
    result: list[SemanticConcept] = []
    for c in concepts:
        if c.last_activated is None:
            result.append(c)
            continue
        decay = min((current_time - c.last_activated) * decay_rate, 0.50)
        new_conf = max(0.0, c.confidence - decay)
        result.append(
            SemanticConcept(
                concept_id=c.concept_id,
                pattern_signature=c.pattern_signature,
                episodes=c.episodes,
                confidence=new_conf,
                retrieval_count=c.retrieval_count,
                last_activated=c.last_activated,
            )
        )
    return result


def trim_to_capacity(
    concepts: list[SemanticConcept],
    max_concepts: int = MAX_CONCEPTS,
) -> tuple[list[SemanticConcept], list[str]]:
    """Trim concepts to max capacity, removing lowest-confidence first.

    Returns (remaining_concepts, forgotten_ids).
    """
    if len(concepts) <= max_concepts:
        return concepts, []
    sorted_c = sorted(concepts, key=lambda c: c.confidence)
    forgotten = sorted_c[: len(sorted_c) - max_concepts]
    forgotten_ids = [c.concept_id for c in forgotten]
    remaining = sorted_c[len(sorted_c) - max_concepts :]
    return remaining, forgotten_ids
