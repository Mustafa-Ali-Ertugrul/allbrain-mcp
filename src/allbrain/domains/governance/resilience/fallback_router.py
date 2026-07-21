from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FallbackRouter:
    routes: dict[str, list[str]] = field(default_factory=dict)

    def set_route(self, primary: str, fallbacks: list[str]) -> None:
        self.routes[primary] = list(fallbacks)

    def route(self, primary: str, *, failed: set[str] | None = None) -> str | None:
        failed = failed or set()
        if primary not in failed:
            return primary
        for candidate in self.routes.get(primary, []):
            if candidate not in failed:
                return candidate
        return None
