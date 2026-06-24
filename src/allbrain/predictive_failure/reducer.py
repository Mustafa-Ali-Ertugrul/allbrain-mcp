from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.predictive_failure.events import (
    validate_signal_detected,
    validate_risk_computed,
    validate_failure_predicted,
    validate_mitigation_planned,
    validate_recovery_executed,
    validate_failure_avoided,
)
from allbrain.predictive_failure.model import PREDICTIVE_FAILURE_TEMPLATE_VERSION


class PredictiveFailureReducer:
    """Event-driven reducer for predictive failure.

    Reconstructs predictive failure state from events for replay
    compatibility. Tracks signals, risk scores, predictions,
    mitigations, actions, and avoided failures.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._signals: list[dict[str, Any]] = []
        self._risk_scores: list[dict[str, Any]] = []
        self._predictions: list[dict[str, Any]] = []
        self._mitigations: list[dict[str, Any]] = []
        self._actions: list[dict[str, Any]] = []
        self._avoided_events: list[dict[str, Any]] = []
        self._total_signals: int = 0
        self._total_high_risk: int = 0
        self._total_predictions: int = 0
        self._total_mitigations: int = 0
        self._total_avoided: int = 0
        self._total_failed_mitigations: int = 0

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

        if et == EventType.PREDICTIVE_SIGNAL_DETECTED.value:
            try:
                validate_signal_detected(payload)
            except ValueError:
                return
            self._signals.append(payload)
            self._total_signals += 1

        elif et == EventType.FAILURE_RISK_COMPUTED.value:
            try:
                validate_risk_computed(payload)
            except ValueError:
                return
            self._risk_scores.append(payload)
            risk = float(payload.get("risk_score", 0))
            if risk >= 0.70:
                self._total_high_risk += 1

        elif et == EventType.FAILURE_PREDICTED.value:
            try:
                validate_failure_predicted(payload)
            except ValueError:
                return
            self._predictions.append(payload)
            self._total_predictions += 1

        elif et == EventType.PROACTIVE_MITIGATION_PLANNED.value:
            try:
                validate_mitigation_planned(payload)
            except ValueError:
                return
            self._mitigations.append(payload)
            self._total_mitigations += 1

        elif et == EventType.PROACTIVE_RECOVERY_EXECUTED.value:
            try:
                validate_recovery_executed(payload)
            except ValueError:
                return
            self._actions.append(payload)
            success = bool(payload.get("success", False))
            if not success:
                self._total_failed_mitigations += 1

        elif et == EventType.FAILURE_AVOIDED.value:
            try:
                validate_failure_avoided(payload)
            except ValueError:
                return
            self._avoided_events.append(payload)
            self._total_avoided += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "signals": list(self._signals),
            "risk_scores": list(self._risk_scores),
            "predictions": list(self._predictions),
            "mitigations": list(self._mitigations),
            "actions": list(self._actions),
            "avoided_events": list(self._avoided_events),
            "total_signals": self._total_signals,
            "total_high_risk": self._total_high_risk,
            "total_predictions": self._total_predictions,
            "total_mitigations": self._total_mitigations,
            "total_avoided": self._total_avoided,
            "total_failed_mitigations": self._total_failed_mitigations,
            "version": PREDICTIVE_FAILURE_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
