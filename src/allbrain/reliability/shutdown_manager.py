from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from allbrain.reliability.resource_tracker import ResourceTracker


@dataclass
class ShutdownManager:
    tracker: ResourceTracker = field(default_factory=ResourceTracker)
    accepting_work: bool = True

    def register(self, resource: Any) -> Any:
        return self.tracker.register(resource)

    async def shutdown(self) -> dict[str, Any]:
        self.accepting_work = False
        closed = await self.tracker.close_all()
        return {"accepting_work": self.accepting_work, "closed": closed}
