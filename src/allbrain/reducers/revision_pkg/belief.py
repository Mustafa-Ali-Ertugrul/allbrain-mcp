"""Belief / contradiction sub-reducer.

Owns the per-context checkpoint bucket (``BELIEF_REVISED``) and the trailing
contradiction counter.  Extracted from the monolithic ``RevisionReducer`` so
each concern lives in its own unit while ``RevisionReducer`` remains the
single convergence point.
"""

from __future__ import annotations

from typing import Any

from allbrain.revision.events import validate_payload
from allbrain.revision.policies import REVISION_TEMPLATE_VERSION


class BeliefRevisionSubReducer:
    """Tracks belief checkpoints and trailing contradiction counts per context."""

    def __init__(self) -> None:
        self._contexts: dict[str, dict[str, Any]] = {}
        self._trailing: dict[str, int] = {}

    @staticmethod
    def context_key(payload: dict[str, Any]) -> str:
        value = payload.get("context_key", "default")
        return value if isinstance(value, str) and value else "default"

    def apply_belief_revised(self, payload: dict[str, Any]) -> None:
        try:
            validate_payload(payload)
        except ValueError:
            return
        context_key = self.context_key(payload)
        self._contexts[context_key] = {
            "old_confidence": float(payload["old_confidence"]),
            "new_confidence": float(payload["new_confidence"]),
            "reason": str(payload["reason"]),
            "evidence_count": int(payload["evidence_count"]),
            "template_version": int(payload.get("template_version", REVISION_TEMPLATE_VERSION)),
        }
        self._trailing[context_key] = 0

    def increment_trailing_for_all(self) -> None:
        for ctx in self._contexts:
            self._trailing[ctx] = self._trailing.get(ctx, 0) + 1

    def get_bucket(self, context_key: str) -> dict[str, Any] | None:
        return self._contexts.get(context_key)

    def get_trailing(self, context_key: str) -> int:
        return int(self._trailing.get(context_key, 0))

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())
