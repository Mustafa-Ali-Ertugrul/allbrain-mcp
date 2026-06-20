from __future__ import annotations

from pathlib import Path
from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.storage.repository import event_to_read


class RuntimeEventBus:
    def __init__(self, context: Any, *, project_path: str | Path | None = None, session_id: int | None = None) -> None:
        self.context = context
        self.project_path = str(project_path or context.project_path)
        if session_id is None and context.active_session_id is None:
            raise ValueError("No active session is available")
        self.session_id = session_id or context.active_session_id or 0

    def publish(
        self,
        *,
        type: str,
        payload: dict[str, Any],
        caused_by: str | None = None,
        agent_id: str | None = None,
        importance: int | None = None,
        impact_score: float | None = None,
    ) -> EventRead:
        event = self.context.repository.append_event(
            project_path=self.project_path,
            session_id=self.session_id,
            type=type,
            source="runtime_core",
            payload=payload,
            caused_by=caused_by,
            agent_id=agent_id,
            importance=importance,
            impact_score=impact_score,
        )
        return event_to_read(event)
