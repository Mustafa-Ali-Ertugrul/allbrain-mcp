from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SupervisionPolicy:
    escalate_after_failures: int = 2
    require_completion_approval: bool = True
    conflict_resolution: str = "supervisor_decides"


@dataclass
class Supervisor:
    supervisor_id: str
    policy: SupervisionPolicy = field(default_factory=SupervisionPolicy)

    def assign(self, *, task_id: str, agent_id: str, role: str) -> dict[str, str]:
        return {
            "supervisor_id": self.supervisor_id,
            "action": "assign",
            "task_id": task_id,
            "agent_id": agent_id,
            "role": role,
        }

    def intervene(self, *, task_id: str, reason: str, action: str = "resolve_conflict") -> dict[str, str]:
        return {"supervisor_id": self.supervisor_id, "action": action, "task_id": task_id, "reason": reason}

    def approve_completion(self, *, task_id: str) -> dict[str, str]:
        return {"supervisor_id": self.supervisor_id, "action": "approve_completion", "task_id": task_id}
