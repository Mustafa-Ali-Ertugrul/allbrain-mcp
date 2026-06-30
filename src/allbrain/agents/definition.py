from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AgentProvider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    ALIBABA = "alibaba"
    OPENCODE = "opencode"
    CODEX = "codex"
    CURSOR = "cursor"
    CUSTOM = "custom"
    MOCK = "mock"


@dataclass(frozen=True)
class AgentCapability:
    domain: str
    skills: frozenset[str] = field(default_factory=frozenset)
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "skills": sorted(self.skills),
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCapability:
        return cls(
            domain=str(data["domain"]),
            skills=frozenset(data.get("skills", [])),
            weight=float(data.get("weight", 1.0)),
        )


@dataclass(frozen=True)
class AgentCost:
    avg_cost_per_call: float = 0.0
    avg_input_token_cost: float = 0.0
    avg_output_token_cost: float = 0.0
    currency: str = "USD"

    def to_dict(self) -> dict[str, Any]:
        return {
            "avg_cost_per_call": self.avg_cost_per_call,
            "avg_input_token_cost": self.avg_input_token_cost,
            "avg_output_token_cost": self.avg_output_token_cost,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCost:
        return cls(
            avg_cost_per_call=float(data.get("avg_cost_per_call", 0.0)),
            avg_input_token_cost=float(data.get("avg_input_token_cost", 0.0)),
            avg_output_token_cost=float(data.get("avg_output_token_cost", 0.0)),
            currency=str(data.get("currency", "USD")),
        )


@dataclass(frozen=True)
class LatencyProfile:
    p50_ms: int = 0
    p95_ms: int = 0
    p99_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LatencyProfile:
        return cls(
            p50_ms=int(data.get("p50_ms", 0)),
            p95_ms=int(data.get("p95_ms", 0)),
            p99_ms=int(data.get("p99_ms", 0)),
        )


@dataclass(frozen=True)
class SafetyLimits:
    max_cost_per_call: float = 1.0
    max_cost_per_workflow: float = 10.0
    max_input_tokens: int = 100_000
    max_output_tokens: int = 16_000
    max_calls_per_minute: int = 60
    allowed_domains: frozenset[str] = field(default_factory=frozenset)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_cost_per_call": self.max_cost_per_call,
            "max_cost_per_workflow": self.max_cost_per_workflow,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_calls_per_minute": self.max_calls_per_minute,
            "allowed_domains": sorted(self.allowed_domains),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SafetyLimits:
        return cls(
            max_cost_per_call=float(data.get("max_cost_per_call", 1.0)),
            max_cost_per_workflow=float(data.get("max_cost_per_workflow", 10.0)),
            max_input_tokens=int(data.get("max_input_tokens", 100_000)),
            max_output_tokens=int(data.get("max_output_tokens", 16_000)),
            max_calls_per_minute=int(data.get("max_calls_per_minute", 60)),
            allowed_domains=frozenset(data.get("allowed_domains", [])),
        )


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    version: str
    provider: AgentProvider
    capabilities: tuple[AgentCapability, ...] = field(default_factory=tuple)
    cost: AgentCost = field(default_factory=AgentCost)
    latency_profile: LatencyProfile = field(default_factory=LatencyProfile)
    max_context_tokens: int = 100_000
    adapter_class_name: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    safety_limits: SafetyLimits = field(default_factory=SafetyLimits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "provider": self.provider.value,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "cost": self.cost.to_dict(),
            "latency_profile": self.latency_profile.to_dict(),
            "max_context_tokens": self.max_context_tokens,
            "adapter_class_name": self.adapter_class_name,
            "config": dict(self.config),
            "safety_limits": self.safety_limits.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentDefinition:
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            version=str(data.get("version", "1.0.0")),
            provider=AgentProvider(data.get("provider", "custom")),
            capabilities=tuple(
                AgentCapability.from_dict(c) for c in data.get("capabilities", [])
            ),
            cost=AgentCost.from_dict(data.get("cost", {})),
            latency_profile=LatencyProfile.from_dict(data.get("latency_profile", {})),
            max_context_tokens=int(data.get("max_context_tokens", 100_000)),
            adapter_class_name=str(data.get("adapter_class_name", "")),
            config=dict(data.get("config", {})),
            safety_limits=SafetyLimits.from_dict(data.get("safety_limits", {})),
        )

    def has_capability(self, domain: str) -> bool:
        return any(c.domain == domain for c in self.capabilities)

    def capability_weight(self, domain: str) -> float:
        for c in self.capabilities:
            if c.domain == domain:
                return c.weight
        return 0.0
