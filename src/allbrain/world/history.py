from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.world.manager import WorldStateBuilder
from allbrain.world.models import SimulationResult, WorldState


class WorldHistory:
    def __init__(self, context: Any) -> None:
        self.context = context

    def events(self, project_path: str | None = None, limit: int = 5000) -> list[EventRead]:
        project = project_path or self.context.project_path
        return self.context.repository.list_events(project_path=project, limit=limit)

    def latest_state(
        self, project_path: str | None = None, limit: int = 5000
    ) -> WorldState | None:
        state = WorldStateBuilder().build(self.events(project_path=project_path, limit=limit))
        latest = state.get("latest_state")
        if not latest:
            return None
        return WorldState.model_validate(latest)

    def latest_simulation(
        self, project_path: str | None = None, limit: int = 5000
    ) -> SimulationResult | None:
        state = WorldStateBuilder().build(self.events(project_path=project_path, limit=limit))
        sims = state.get("simulations") or []
        if not sims:
            return None
        return SimulationResult.model_validate(sims[-1])

    def state_dict(
        self, project_path: str | None = None, limit: int = 5000
    ) -> dict[str, Any]:
        return WorldStateBuilder().build(self.events(project_path=project_path, limit=limit))
