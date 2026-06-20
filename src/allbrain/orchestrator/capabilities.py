from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any


class CapabilityRegistry:
    def __init__(self, capabilities: dict[str, dict[str, int]] | None = None):
        self.capabilities = capabilities or self.load_default()

    @classmethod
    def from_env(cls) -> "CapabilityRegistry":
        override = os.getenv("ALLBRAIN_CAPABILITIES_PATH")
        if override:
            return cls(cls.load_path(Path(override)))
        return cls()

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
