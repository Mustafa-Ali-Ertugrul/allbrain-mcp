from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import FrozenSet


DECISION_TEMPLATE_VERSION = 1


class DecisionMode(StrEnum):
    AUTO = "auto"
    FUSION = "fusion"
    CAUSAL = "causal"
    DYNAMIC = "dynamic"
    LEGACY = "legacy"
    DEBUG = "debug"


@dataclass(frozen=True)
class DecisionContract:
    """Versioned signal presence contract for resolver.

    Refinement #2: resolver uses explicit contract, not presence-based
    None checks. This ensures replay determinism — mode selection
    depends only on contract version + explicit signal keys.
    """
    version: int
    active_signals: FrozenSet[str]  # e.g., frozenset({"fusion", "causal", "dynamics"})
    debug: bool = False

    def has_signal(self, signal: str) -> bool:
        return signal in self.active_signals

    def is_debug(self) -> bool:
        return self.debug


@dataclass(frozen=True)
class DecisionContext:
    agent_id: str
    task_type: str
    contract: DecisionContract = field(default_factory=lambda: DecisionContract(version=1, active_signals=frozenset()))
    telemetry: dict[str, float] = field(default_factory=dict)
    capability: dict[str, float] = field(default_factory=dict)
    learning: dict[str, float] = field(default_factory=dict)
    dynamics: dict[str, float] = field(default_factory=dict)
    causal: dict[str, float] = field(default_factory=dict)
    fusion: dict[str, float] | None = None


@dataclass(frozen=True)
class DecisionResult:
    agent_id: str
    task_type: str
    score: float
    mode: str
    contributors: dict[str, float] = field(default_factory=dict)
    backend_trace: tuple[str, ...] = field(default_factory=tuple)
    workspace_items: tuple | None = None
    episodes: tuple | None = None
    concepts: tuple | None = None
    analysis_id: str = ""
    template_version: int = DECISION_TEMPLATE_VERSION