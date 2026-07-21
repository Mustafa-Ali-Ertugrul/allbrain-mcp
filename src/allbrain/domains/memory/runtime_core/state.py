from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RuntimeStatus(StrEnum):
    INIT = "INIT"
    PLANNING = "PLANNING"
    EVALUATION = "EVALUATION"
    DECISION = "DECISION"
    EXECUTION = "EXECUTION"
    FEEDBACK = "FEEDBACK"
    EVOLUTION = "EVOLUTION"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS = {
    RuntimeStatus.INIT: {RuntimeStatus.PLANNING, RuntimeStatus.FAILED},
    RuntimeStatus.PLANNING: {RuntimeStatus.EVALUATION, RuntimeStatus.BLOCKED, RuntimeStatus.FAILED},
    RuntimeStatus.EVALUATION: {RuntimeStatus.DECISION, RuntimeStatus.BLOCKED, RuntimeStatus.FAILED},
    RuntimeStatus.DECISION: {RuntimeStatus.EXECUTION, RuntimeStatus.BLOCKED, RuntimeStatus.FAILED},
    RuntimeStatus.EXECUTION: {RuntimeStatus.FEEDBACK, RuntimeStatus.FAILED},
    RuntimeStatus.FEEDBACK: {RuntimeStatus.EVOLUTION, RuntimeStatus.FAILED},
    RuntimeStatus.EVOLUTION: {RuntimeStatus.COMPLETED, RuntimeStatus.FAILED},
    RuntimeStatus.COMPLETED: set(),
    RuntimeStatus.BLOCKED: set(),
    RuntimeStatus.FAILED: set(),
}


@dataclass
class RuntimeStateMachine:
    run_id: str
    status: RuntimeStatus = RuntimeStatus.INIT
    history: list[dict[str, Any]] = field(default_factory=list)

    def transition(self, target: RuntimeStatus, *, reason: str = "") -> dict[str, Any]:
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"Invalid runtime transition from {self.status.value} to {target.value}")
        previous = self.status
        self.status = target
        event = {
            "run_id": self.run_id,
            "previous_status": previous.value,
            "new_status": target.value,
            "reason": reason,
        }
        self.history.append(event)
        return event
