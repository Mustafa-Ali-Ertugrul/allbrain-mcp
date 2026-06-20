from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from uuid6 import uuid7


@dataclass(frozen=True)
class Delegation:
    delegation_id: str
    task_id: str
    from_agent: str
    to_agent: str
    reason: str
    status: str = "created"
    outcome: str | None = None

    def to_event_payload(self) -> dict[str, Any]:
        return self.__dict__.copy()


class DelegationService:
    def create(self, *, task_id: str, from_agent: str, to_agent: str, reason: str) -> Delegation:
        return Delegation(delegation_id=str(uuid7()), task_id=task_id, from_agent=from_agent, to_agent=to_agent, reason=reason)

    def complete_payload(self, delegation: Delegation, *, outcome: str) -> dict[str, Any]:
        payload = delegation.to_event_payload()
        payload.update({"status": "completed", "outcome": outcome})
        return payload

    def fail_payload(self, delegation: Delegation, *, outcome: str) -> dict[str, Any]:
        payload = delegation.to_event_payload()
        payload.update({"status": "failed", "outcome": outcome})
        return payload
