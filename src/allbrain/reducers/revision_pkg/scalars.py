"""Scalar sub-reducer for single-value agent/session signals.

Captures the latest ``reputation_score`` / ``score`` / ``runtime_score`` /
``selection_score`` / ``match_score`` / ``new_score`` events into dedicated
float fields.  Extracted from the monolithic ``RevisionReducer``.
"""

from __future__ import annotations

from typing import Any

_DEFAULTS: dict[str, float] = {
    "_last_agent_reputation": 1.0,
    "_last_consensus_score": 1.0,
    "_last_runtime_score": 1.0,
    "_last_selected_agent_score": 1.0,
    "_last_capability_score": 1.0,
    "_last_learned_capability": 1.0,
}


class ScalarSubReducer:
    """Owns the six scalar agent/session signals."""

    def __init__(self) -> None:
        self._last_agent_reputation: float = 1.0
        self._last_consensus_score: float = 1.0
        self._last_runtime_score: float = 1.0
        self._last_selected_agent_score: float = 1.0
        self._last_capability_score: float = 1.0
        self._last_learned_capability: float = 1.0

    def apply(self, payload: dict[str, Any], source: str, target: str) -> None:
        value = payload.get(source)
        if isinstance(value, (int, float)):
            setattr(self, target, max(0.0, min(1.0, float(value))))

    @property
    def agent_reputation(self) -> float:
        return self._last_agent_reputation

    @property
    def consensus_score(self) -> float:
        return self._last_consensus_score

    @property
    def runtime_score(self) -> float:
        return self._last_runtime_score

    @property
    def selected_agent_score(self) -> float:
        return self._last_selected_agent_score

    @property
    def capability_score(self) -> float:
        return self._last_capability_score

    @property
    def learned_capability(self) -> float:
        return self._last_learned_capability
