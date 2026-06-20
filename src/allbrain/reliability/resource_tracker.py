from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResourceTracker:
    resources: list[Any] = field(default_factory=list)
    closed: list[str] = field(default_factory=list)

    def register(self, resource: Any) -> Any:
        self.resources.append(resource)
        return resource

    async def close_all(self) -> list[str]:
        for resource in reversed(self.resources):
            name = resource.__class__.__name__
            if name in self.closed:
                continue
            close = getattr(resource, "close", None)
            dispose = getattr(resource, "dispose", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result
            elif dispose is not None:
                dispose()
            self.closed.append(name)
        return list(self.closed)
