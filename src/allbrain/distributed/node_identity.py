from __future__ import annotations

import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from uuid6 import uuid7


@dataclass(frozen=True)
class NodeIdentity:
    node_id: str
    hostname: str
    process_id: str
    started_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, *, node_id: str | None = None, metadata: dict[str, Any] | None = None) -> "NodeIdentity":
        return cls(
            node_id=node_id or str(uuid7()),
            hostname=platform.node() or "unknown",
            process_id=str(uuid7()),
            started_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "process_id": self.process_id,
            "started_at": self.started_at.isoformat(),
            "metadata": self.metadata,
        }
