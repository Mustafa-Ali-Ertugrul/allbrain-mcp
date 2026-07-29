"""Shared idempotence tracking for revision sub-reducers.

A single ``RevisionReducer`` may replay the same event log multiple times
(e.g. across resume round-trips).  All sub-reducers must agree on which
event ids have already been applied so the reducer stays convergent.
"""

from __future__ import annotations


class SeenIds:
    """Tracks already-applied event ids for idempotent replay."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def observe(self, event_id: str) -> bool:
        """Return ``True`` if *event_id* was already seen (caller should skip)."""
        if event_id and event_id in self._seen:
            return True
        if event_id:
            self._seen.add(event_id)
        return False

    def snapshot(self) -> set[str]:
        return set(self._seen)
