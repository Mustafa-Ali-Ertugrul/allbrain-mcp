from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Bulkhead:
    limits: dict[str, int]
    active: dict[str, int] = field(default_factory=dict)

    def acquire(self, partition: str) -> bool:
        current = self.active.get(partition, 0)
        if current >= self.limits.get(partition, 1):
            return False
        self.active[partition] = current + 1
        return True

    def release(self, partition: str) -> None:
        self.active[partition] = max(self.active.get(partition, 0) - 1, 0)

    def to_dict(self) -> dict[str, object]:
        return {"limits": dict(self.limits), "active": dict(self.active)}
