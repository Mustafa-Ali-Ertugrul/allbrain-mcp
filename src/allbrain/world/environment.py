from __future__ import annotations

from datetime import datetime, timezone

from allbrain.world.models import WorldState


class EnvironmentTracker:
    def capture(self) -> WorldState:
        return WorldState(
            timestamp=datetime.now(timezone.utc),
            system_state={"memory_usage": 0.0, "cpu_usage": 0.0},
            resources={"internet": True, "disk_available": True},
        )
