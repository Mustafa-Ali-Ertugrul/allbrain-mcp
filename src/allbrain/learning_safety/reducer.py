from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.learning_safety.events import (
    validate_exploration_triggered,
    validate_simulation_weight_capped,
    validate_learning_drift_detected,
)
from allbrain.learning_safety.model import LEARNING_SAFETY_TEMPLATE_VERSION


class LearningSafetyReducer:
    """Event-driven reducer for learning safety.

    Reconstructs safety state from events for replay compatibility.
    Tracks exploration decisions, simulation cap events, and drift detections.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._explorations: list[dict[str, Any]] = []
        self._caps: list[dict[str, Any]] = []
        self._drifts: list[dict[str, Any]] = []
        self._total_explorations: int = 0
        self._total_exploration_triggered: int = 0
        self._total_caps: int = 0
        self._total_drifts: int = 0

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

        if et == EventType.EXPLORATION_TRIGGERED.value:
            try:
                validate_exploration_triggered(payload)
            except ValueError:
                return
            self._explorations.append(payload)
            self._total_explorations += 1
            if payload.get("was_exploration"):
                self._total_exploration_triggered += 1

        elif et == EventType.SIMULATION_WEIGHT_CAPPED.value:
            try:
                validate_simulation_weight_capped(payload)
            except ValueError:
                return
            self._caps.append(payload)
            self._total_caps += 1

        elif et == EventType.LEARNING_DRIFT_DETECTED.value:
            try:
                validate_learning_drift_detected(payload)
            except ValueError:
                return
            self._drifts.append(payload)
            self._total_drifts += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "explorations": list(self._explorations),
            "caps": list(self._caps),
            "drifts": list(self._drifts),
            "total_explorations": self._total_explorations,
            "total_exploration_triggered": self._total_exploration_triggered,
            "total_caps": self._total_caps,
            "total_drifts": self._total_drifts,
            "version": LEARNING_SAFETY_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
