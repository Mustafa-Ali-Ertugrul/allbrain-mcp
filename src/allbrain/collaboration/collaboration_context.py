from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CollaborationContext:
    collaboration_id: str
    objective: str
    team_name: str | None = None
    task_id: str | None = None
    workflow_id: str | None = None
    shared_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collaboration_id": self.collaboration_id,
            "objective": self.objective,
            "team_name": self.team_name,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "shared_state": dict(self.shared_state),
        }
