"""Signal sub-reducers: uncertainty, trust, calibration, drift.

Each class owns a single slice of per-context state that the monolithic
``RevisionReducer`` previously held inline.  They are deliberately tiny so
the responsibility split is obvious and unit-testable in isolation.
"""

from __future__ import annotations

from typing import Any

from allbrain.uncertainty.events import validate_payload as validate_uncertainty_payload


class UncertaintySubReducer:
    """Last-wins authoritative uncertainty value per context."""

    def __init__(self) -> None:
        self._last_uncertainty: dict[str, float] = {}

    def apply(self, payload: dict[str, Any], context_key: str) -> None:
        try:
            validate_uncertainty_payload(payload)
            self._last_uncertainty[context_key] = float(payload["uncertainty"])
        except (KeyError, TypeError, ValueError):
            return

    def get(self, context_key: str) -> float:
        return float(self._last_uncertainty.get(context_key, 0.0))


class TrustSubReducer:
    """Last-wins trust score per context (default 1.0)."""

    def __init__(self) -> None:
        self._last_trust: dict[str, float] = {}

    def apply(self, payload: dict[str, Any], context_key: str) -> None:
        trust = payload.get("trust_score")
        if isinstance(trust, (int, float)):
            self._last_trust[context_key] = max(0.0, min(1.0, float(trust)))

    def get(self, context_key: str) -> float:
        return float(self._last_trust.get(context_key, 1.0))


class CalibrationSubReducer:
    """Per-context (predicted_confidence, actual_outcome) sample list."""

    def __init__(self) -> None:
        self._calibration_samples: dict[str, list[tuple[float, bool]]] = {}

    def apply(self, payload: dict[str, Any], context_key: str) -> None:
        predicted = payload.get("predicted_confidence")
        outcome = payload.get("actual_outcome")
        if isinstance(predicted, (int, float)) and isinstance(outcome, bool):
            self._calibration_samples.setdefault(context_key, []).append((float(predicted), outcome))

    def get(self, context_key: str) -> list[tuple[float, bool]]:
        return list(self._calibration_samples.get(context_key, []))


class DriftSubReducer:
    """Per-context count of ``BELIEF_DRIFT_DETECTED`` events."""

    def __init__(self) -> None:
        self._drift_count: dict[str, int] = {}

    def apply(self, context_key: str) -> None:
        self._drift_count[context_key] = self._drift_count.get(context_key, 0) + 1

    def get(self, context_key: str) -> int:
        return int(self._drift_count.get(context_key, 0))
