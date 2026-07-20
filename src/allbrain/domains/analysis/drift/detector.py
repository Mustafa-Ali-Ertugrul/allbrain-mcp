from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DRIFT_THRESHOLD: float = 0.10
"""Minimum |belief_after - belief_before| to emit a BELIEF_DRIFT_DETECTED event.

Prevents event explosion when the revision layer produces many small
confidence adjustments. Set per Sprint 47 spec.
"""

DRIFT_TEMPLATE_VERSION: int = 1

REASONS: Final[frozenset[str]] = frozenset(
    {
        "new_evidence",
        "trust_shift",
        "contradiction_resolution",
        "uncertainty_change",
    }
)
"""Closed set of reasons a BELIEF_DRIFT_DETECTED event can carry.

Future reasons may be added without breaking old logs: the validator
rejects unknown reasons, so older replays stay valid against the
narrower Sprint 47 set, and new logs carrying the wider set can be
decoded by future reducers. Migration is one-way compatible: old
replays ignore new reasons, new replays encode old reasons losslessly.
"""


@dataclass(frozen=True)
class DriftSample:
    context_key: str
    belief_before: float
    belief_after: float
    magnitude: float
    reason: str

    def __post_init__(self) -> None:
        if self.reason not in REASONS:
            raise ValueError(f"unknown drift reason: {self.reason!r} (expected one of {sorted(REASONS)})")
        if not 0.0 <= float(self.belief_before) <= 1.0:
            raise ValueError(f"belief_before must be in [0, 1], got {self.belief_before}")
        if not 0.0 <= float(self.belief_after) <= 1.0:
            raise ValueError(f"belief_after must be in [0, 1], got {self.belief_after}")


def detect_drift(
    belief_before: float,
    belief_after: float,
    *,
    context_key: str,
    reason: str,
) -> DriftSample | None:
    """Return a DriftSample if |delta| >= DRIFT_THRESHOLD, else None.

    The threshold is the only place that filters drift; consumers
    (pipeline, replay) can replay the full event log without filter.
    """
    if reason not in REASONS:
        raise ValueError(f"unknown drift reason: {reason!r} (expected one of {sorted(REASONS)})")
    before = float(belief_before)
    after = float(belief_after)
    magnitude = abs(after - before)
    if magnitude < DRIFT_THRESHOLD:
        return None
    return DriftSample(
        context_key=str(context_key),
        belief_before=before,
        belief_after=after,
        magnitude=magnitude,
        reason=reason,
    )
