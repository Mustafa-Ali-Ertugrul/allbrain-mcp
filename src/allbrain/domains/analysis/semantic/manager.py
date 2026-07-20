from __future__ import annotations

import uuid
from typing import Any

from allbrain.domains.analysis.episodic.model import Episode
from allbrain.domains.analysis.semantic.abstraction import (
    extract_pattern_from_episode,
    generalize_signature,
    pattern_overlap,
)
from allbrain.domains.analysis.semantic.consolidation import (
    apply_decay_to_all,
    compute_concept_confidence,
    find_matching_concept,
    should_create_concept,
    trim_to_capacity,
)
from allbrain.domains.analysis.semantic.model import (
    CONFIDENCE_DECAY_RATE,
    CONSOLIDATION_THRESHOLD,
    DEFAULT_SEMANTIC_LIMIT,
    MAX_CONCEPTS,
    SemanticConcept,
)
from allbrain.domains.analysis.semantic.retrieval import retrieve_semantic

EVICTION_REASON_CAPACITY = "max_concepts_exceeded"
EVICTION_REASON_DECAY = "confidence_below_threshold"


class SemanticManager:
    def __init__(self) -> None:
        self._concepts: list[SemanticConcept] = []
        self._total: int = 0
        self._retained: int = 0
        self._forgotten: int = 0
        self._time: int = 0

    def consolidate(
        self,
        episode: Episode,
    ) -> dict[str, Any]:
        """Consolidate an episode into semantic memory.

        Steps:
          1. Find matching concept via pattern_overlap
          2. If match found and above threshold: update concept (generalize, increase confidence)
          3. If no match and enough episodes share pattern: create new concept
          4. Apply decay to all concepts not activated this cycle
          5. Trim to MAX_CONCEPTS capacity (lowest confidence removed)
          6. Emit consolidation result
        """
        self._time += 1
        ws_signature = extract_pattern_from_episode(episode.workspace_items)
        result: dict[str, Any] = {
            "concept_created": None,
            "concept_updated": None,
            "forgotten": [],
            "decayed": [],
        }

        # Find matching concept
        match = find_matching_concept(
            episode.workspace_items,
            self._concepts,
            threshold=CONSOLIDATION_THRESHOLD,
        )

        if match is not None:
            # Update existing concept: generalize, add episode, increase confidence
            new_signature = generalize_signature(
                match, set(episode.workspace_items), min_overlap=CONSOLIDATION_THRESHOLD
            )
            new_episodes = match.episodes + (episode.episode_id,)
            new_confidence = compute_concept_confidence(
                base_confidence=match.confidence,
                retrieval_count=match.retrieval_count + 1,
                time_since_last_activation=(
                    self._time - match.last_activated if match.last_activated is not None else 0
                ),
            )
            self._replace_concept(
                match.concept_id,
                SemanticConcept(
                    concept_id=match.concept_id,
                    pattern_signature=new_signature,
                    episodes=new_episodes,
                    confidence=new_confidence,
                    retrieval_count=match.retrieval_count + 1,
                    last_activated=self._time,
                ),
            )
            result["concept_updated"] = match.concept_id

        else:
            # No match found — check if we should create a new concept
            # Count episodes with similar patterns
            similar_count = 0
            for c in self._concepts:
                ov = pattern_overlap(ws_signature, c.pattern_signature)
                if ov >= CONSOLIDATION_THRESHOLD:
                    similar_count += 1
            if should_create_concept(similar_count + 1):
                concept_id = f"sem-{uuid.uuid4().hex[:12]}"
                concept = SemanticConcept(
                    concept_id=concept_id,
                    pattern_signature=ws_signature,
                    episodes=(episode.episode_id,),
                    confidence=CONSOLIDATION_THRESHOLD,
                    retrieval_count=0,
                    last_activated=self._time,
                )
                self._concepts.append(concept)
                self._total += 1
                self._retained += 1
                result["concept_created"] = concept_id

        # Apply decay to all concepts not activated this cycle
        self._concepts = apply_decay_to_all(self._concepts, self._time, decay_rate=CONFIDENCE_DECAY_RATE)
        decayed_ids = [c.concept_id for c in self._concepts if c.last_activated is not None and c.confidence < 0.05]
        result["decayed"] = decayed_ids

        # Trim to capacity
        self._concepts, forgotten_ids = trim_to_capacity(self._concepts, max_concepts=MAX_CONCEPTS)
        if forgotten_ids:
            self._forgotten += len(forgotten_ids)
            result["forgotten"] = [{"concept_id": fid, "reason": EVICTION_REASON_CAPACITY} for fid in forgotten_ids]
        self._retained = len(self._concepts)

        return result

    def retrieve(
        self,
        workspace_items: tuple[str, ...],
        *,
        limit: int = DEFAULT_SEMANTIC_LIMIT,
    ) -> dict[str, Any]:
        """Retrieve matching semantic concepts for workspace items."""
        if not self._concepts:
            return {"retrieved": 0, "concepts": [], "best_overlap": 0.0}

        matched = retrieve_semantic(workspace_items, self._concepts, limit=limit)

        # Update retrieval metadata on matched concepts
        for concept, _ in matched:
            self._replace_concept(
                concept.concept_id,
                SemanticConcept(
                    concept_id=concept.concept_id,
                    pattern_signature=concept.pattern_signature,
                    episodes=concept.episodes,
                    confidence=concept.confidence,
                    retrieval_count=concept.retrieval_count + 1,
                    last_activated=self._time,
                ),
            )

        best_overlap = matched[0][1] if matched else 0.0
        return {
            "retrieved": len(matched),
            "concepts": [(c.concept_id, ov) for c, ov in matched],
            "best_overlap": best_overlap,
        }

    def stats(self) -> dict[str, Any]:
        return {
            "total": self._total,
            "retained": self._retained,
            "forgotten": self._forgotten,
            "concept_count": len(self._concepts),
        }

    def get_all_concepts(self) -> list[SemanticConcept]:
        return list(self._concepts)

    def _replace_concept(self, concept_id: str, new: SemanticConcept) -> None:
        for i, c in enumerate(self._concepts):
            if c.concept_id == concept_id:
                self._concepts[i] = new
                break
