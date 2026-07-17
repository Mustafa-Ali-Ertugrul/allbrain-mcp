from __future__ import annotations

import json
import os
import threading
from importlib import resources
from pathlib import Path
from typing import Any

_default_registry = None
_default_registry_lock = threading.Lock()
_default_registry_source: str | None = None


class CapabilityRegistry:
    def __init__(self, capabilities: dict[str, dict[str, int]] | None = None):
        self.capabilities = capabilities or self.load_default()

    @classmethod
    def from_env(cls) -> CapabilityRegistry:
        """Return process-wide registry for the current ALLBRAIN_CAPABILITIES_PATH."""
        global _default_registry, _default_registry_source
        override = os.getenv("ALLBRAIN_CAPABILITIES_PATH")
        source = override or ""
        with _default_registry_lock:
            if _default_registry is not None and _default_registry_source == source:
                return _default_registry
            registry = cls(cls.load_path(Path(override))) if override else cls()
            _default_registry = registry
            _default_registry_source = source
            return registry

    @classmethod
    def reset_default_cache(cls) -> None:
        """Test helper: drop cached from_env() instance."""
        global _default_registry, _default_registry_source
        with _default_registry_lock:
            _default_registry = None
            _default_registry_source = None

    @staticmethod
    def load_default() -> dict[str, dict[str, int]]:
        text = resources.files("allbrain.orchestrator").joinpath("capabilities.default.json").read_text()
        return CapabilityRegistry._validate(json.loads(text))

    @staticmethod
    def load_path(path: Path) -> dict[str, dict[str, int]]:
        return CapabilityRegistry._validate(json.loads(path.read_text()))

    @staticmethod
    def _validate(raw: Any) -> dict[str, dict[str, int]]:
        if not isinstance(raw, dict):
            raise ValueError("capability registry must be an object")
        validated: dict[str, dict[str, int]] = {}
        for agent, scores in raw.items():
            if not isinstance(agent, str) or not isinstance(scores, dict):
                raise ValueError("capability registry must map agent ids to score objects")
            validated[agent] = {}
            for capability, score in scores.items():
                if not isinstance(capability, str) or not isinstance(score, int):
                    raise ValueError("capability scores must be integer values")
                validated[agent][capability] = max(0, min(10, score))
        return validated

    def agents(self) -> list[str]:
        return sorted(self.capabilities)

    def score(self, agent_id: str, kind: str) -> int:
        scores = self.capabilities.get(agent_id, {})
        return scores.get(kind, scores.get("implementation", 0))
