from __future__ import annotations

from typing import Any

from allbrain.domains.learning.calibration.estimator import (
    _stable_calibration_id,
    accuracy,
    mean_calibration_error,
    mean_confidence,
)
from allbrain.domains.learning.calibration.model import CalibrationState
from allbrain.events.schemas import EventType
from allbrain.domains.memory.foundations.ordering import canonical_event_sort


class CalibrationManager:
    """Authoritative projection over CALIBRATION_UPDATED events.

    Zorunlu: this manager does NOT re-derive calibration from beliefs or
    contradictions. It mirrors CalibrationReducer exactly — both consume
    the same event log and produce the same per-context CalibrationState.

    Convergence invariant: manager.query(events) == reducer.snapshot(ctx)
    for ALL event logs.
    """

    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        context_key: str = "default",
        analysis_id: str | None = None,
    ) -> CalibrationState:
        ordered = canonical_event_sort(events)
        all_event_ids = {str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")}

        samples: list[tuple[float, bool]] = []
        for event in ordered:
            event_type = str(getattr(event, "type", ""))
            if event_type != EventType.CALIBRATION_UPDATED.value:
                continue
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("context_key") != context_key:
                continue
            predicted = payload.get("predicted_confidence")
            outcome = payload.get("actual_outcome")
            if not isinstance(predicted, (int, float)):
                continue
            if not isinstance(outcome, bool):
                continue
            samples.append((float(predicted), bool(outcome)))

        evidence = sorted(all_event_ids)
        return CalibrationState(
            context_key=context_key,
            sample_count=len(samples),
            mean_confidence=mean_confidence(samples),
            accuracy=accuracy(samples),
            calibration_error=mean_calibration_error(samples),
            analysis_id=analysis_id or _stable_calibration_id(context_key, evidence),
        )

    def known_context_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            if str(getattr(event, "type", "")) != EventType.CALIBRATION_UPDATED.value:
                continue
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                context_key = payload.get("context_key")
                if isinstance(context_key, str) and context_key:
                    keys.add(context_key)
        return keys
