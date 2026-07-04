from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.semantic.events import (
    validate_concept_created,
    validate_concept_forgotten,
    validate_concept_updated,
)
from allbrain.semantic.model import SemanticConcept


class SemanticReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._concepts: list[SemanticConcept] = []
        self._total: int = 0
        self._retained: int = 0
        self._forgotten: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.SEMANTIC_CONCEPT_CREATED.value:
            try:
                validate_concept_created(payload)
            except ValueError:
                return
            concept_id = str(payload["concept_id"])
            psig = frozenset(str(s) for s in payload["pattern_signature"])
            confidence = float(payload["confidence"])
            concept = SemanticConcept(
                concept_id=concept_id,
                pattern_signature=psig,
                episodes=(),
                confidence=confidence,
                retrieval_count=0,
                last_activated=None,
            )
            self._concepts.append(concept)
            self._total += 1
            self._retained += 1

        elif et == EventType.SEMANTIC_CONCEPT_UPDATED.value:
            try:
                validate_concept_updated(payload)
            except ValueError:
                return
            concept_id = str(payload["concept_id"])
            new_confidence = float(payload["confidence"])
            for i, c in enumerate(self._concepts):
                if c.concept_id == concept_id:
                    self._concepts[i] = SemanticConcept(
                        concept_id=c.concept_id,
                        pattern_signature=c.pattern_signature,
                        episodes=c.episodes,
                        confidence=new_confidence,
                        retrieval_count=c.retrieval_count,
                        last_activated=c.last_activated,
                    )
                    break

        elif et == EventType.SEMANTIC_CONCEPT_FORGOTTEN.value:
            try:
                validate_concept_forgotten(payload)
            except ValueError:
                return
            concept_id = str(payload["concept_id"])
            self._concepts = [c for c in self._concepts if c.concept_id != concept_id]
            self._forgotten += 1
            self._retained = len(self._concepts)

    def snapshot(self) -> dict[str, Any]:
        return {
            "concepts": list(self._concepts),
            "total": self._total,
            "retained": self._retained,
            "forgotten": self._forgotten,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
