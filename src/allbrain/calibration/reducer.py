from __future__ import annotations

from typing import Any

from allbrain.calibration.estimator import (
    _stable_calibration_id,
    accuracy,
    mean_calibration_error,
    mean_confidence,
)
from allbrain.calibration.events import validate_payload
from allbrain.calibration.model import CalibrationState
from allbrain.events.schemas import EventType


class CalibrationReducer:
    """Replays CALIBRATION_UPDATED events into a per-context CalibrationState.

    Contract:
      - CALIBRATION_UPDATED is the ONLY event type that contributes to the
        per-context sample list. The reducer does NOT re-derive calibration
        from beliefs/contradictions — calibration is a measurement of how
        accurate prior predictions were, not a derivative of current state.
      - All other event types: no-op (unknown-event tolerance).
      - snapshot() returns a CalibrationState with sample_count, mean_confidence,
        accuracy, calibration_error, and a stable analysis_id. The same
        formula the manager uses.

    Convergence invariant: CalibrationManager.query(events, ctx) ==
    CalibrationReducer.snapshot(ctx) for ALL event logs.
    """

    def __init__(self) -> None:
        self._contexts: dict[str, list[tuple[float, bool]]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.CALIBRATION_UPDATED.value:
            return

        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        try:
            validate_payload(payload)
        except ValueError:
            return

        context_key = payload.get("context_key", "default")
        if not isinstance(context_key, str) or not context_key:
            context_key = "default"

        predicted = float(payload["predicted_confidence"])
        outcome = bool(payload["actual_outcome"])
        self._contexts.setdefault(context_key, []).append((predicted, outcome))

    def snapshot(self, *, context_key: str = "default") -> CalibrationState:
        samples = list(self._contexts.get(context_key, []))
        evidence = sorted(self._seen_ids)
        return CalibrationState(
            context_key=context_key,
            sample_count=len(samples),
            mean_confidence=mean_confidence(samples),
            accuracy=accuracy(samples),
            calibration_error=mean_calibration_error(samples),
            analysis_id=_stable_calibration_id(context_key, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: {
                "context_key": state.context_key,
                "sample_count": state.sample_count,
                "mean_confidence": state.mean_confidence,
                "accuracy": state.accuracy,
                "calibration_error": state.calibration_error,
                "analysis_id": state.analysis_id,
                "template_version": state.template_version,
            }
            for context_key, state in ((k, self.snapshot(context_key=k)) for k in self._contexts)
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())
