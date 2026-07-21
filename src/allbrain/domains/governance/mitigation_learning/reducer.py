from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.domains.governance.mitigation_learning.events import (
    validate_mitigation_evaluated,
    validate_outcome_measured,
    validate_policy_improved,
    validate_strategy_updated,
)
from allbrain.domains.governance.mitigation_learning.model import MITIGATION_LEARNING_TEMPLATE_VERSION


class MitigationLearningReducer:
    """Event-driven reducer for mitigation learning.

    Reconstructs learning state from events for replay compatibility.
    Tracks outcomes, evaluations, strategy updates, and policy versions.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._outcomes: list[dict[str, Any]] = []
        self._evaluations: list[dict[str, Any]] = []
        self._strategy_updates: list[dict[str, Any]] = []
        self._policy_versions: list[dict[str, Any]] = []
        self._total_outcomes: int = 0
        self._total_evaluations: int = 0
        self._total_strategy_updates: int = 0
        self._total_policy_versions: int = 0

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

        if et == EventType.OUTCOME_MEASURED.value:
            try:
                validate_outcome_measured(payload)
            except ValueError:
                return
            self._outcomes.append(payload)
            self._total_outcomes += 1

        elif et == EventType.MITIGATION_EVALUATED.value:
            try:
                validate_mitigation_evaluated(payload)
            except ValueError:
                return
            self._evaluations.append(payload)
            self._total_evaluations += 1

        elif et == EventType.STRATEGY_UPDATED.value:
            try:
                validate_strategy_updated(payload)
            except ValueError:
                return
            self._strategy_updates.append(payload)
            self._total_strategy_updates += 1

        elif et == EventType.POLICY_IMPROVED.value:
            try:
                validate_policy_improved(payload)
            except ValueError:
                return
            self._policy_versions.append(payload)
            self._total_policy_versions += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "outcomes": list(self._outcomes),
            "evaluations": list(self._evaluations),
            "strategy_updates": list(self._strategy_updates),
            "policy_versions": list(self._policy_versions),
            "total_outcomes": self._total_outcomes,
            "total_evaluations": self._total_evaluations,
            "total_strategy_updates": self._total_strategy_updates,
            "total_policy_versions": self._total_policy_versions,
            "version": MITIGATION_LEARNING_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
