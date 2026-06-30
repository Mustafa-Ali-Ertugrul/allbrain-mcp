from __future__ import annotations

import os
from typing import Any

from allbrain.agents.adapter import AgentAdapter
from allbrain.agents.definition import (
    AgentCapability,
    AgentCost,
    AgentDefinition,
    AgentProvider,
    LatencyProfile,
    SafetyLimits,
)


class AgentRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, AgentDefinition] = {}
        self._adapters: dict[str, AgentAdapter] = {}

    def register(self, definition: AgentDefinition) -> None:
        if definition.id in self._definitions:
            raise ValueError(f"Agent '{definition.id}' already registered")
        self._definitions[definition.id] = definition

    def unregister(self, agent_id: str) -> None:
        self._definitions.pop(agent_id, None)
        self._adapters.pop(agent_id, None)

    def get(self, agent_id: str) -> AgentDefinition:
        if agent_id not in self._definitions:
            raise KeyError(f"Agent '{agent_id}' not registered")
        return self._definitions[agent_id]

    def try_get(self, agent_id: str) -> AgentDefinition | None:
        return self._definitions.get(agent_id)

    def list_all(self) -> list[AgentDefinition]:
        return list(self._definitions.values())

    def list_by_capability(self, domain: str) -> list[AgentDefinition]:
        return [d for d in self._definitions.values() if d.has_capability(domain)]

    def has(self, agent_id: str) -> bool:
        return agent_id in self._definitions

    def register_adapter(self, agent_id: str, adapter: AgentAdapter) -> None:
        if agent_id not in self._definitions:
            raise KeyError(f"Agent '{agent_id}' not registered")
        self._adapters[agent_id] = adapter

    def get_adapter(self, agent_id: str) -> AgentAdapter:
        if agent_id not in self._adapters:
            raise KeyError(f"Adapter for '{agent_id}' not instantiated")
        return self._adapters[agent_id]

    def try_get_adapter(self, agent_id: str) -> AgentAdapter | None:
        return self._adapters.get(agent_id)

    def clear(self) -> None:
        self._definitions.clear()
        self._adapters.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "agents": {aid: d.to_dict() for aid, d in self._definitions.items()},
            "count": len(self._definitions),
        }

    @classmethod
    def discover_from_env(cls, *, include_mock: bool = False) -> AgentRegistry:
        """Auto-discover agents from environment variables."""
        registry = cls()

        if os.getenv("ANTHROPIC_API_KEY") or include_mock:
            registry.register(_claude_default())

        if os.getenv("OPENAI_API_KEY") or include_mock:
            registry.register(_openai_default())

        if os.getenv("GOOGLE_API_KEY") or include_mock:
            registry.register(_gemini_default())

        if os.getenv("DASHSCOPE_API_KEY") or include_mock:
            registry.register(_qwen_default())

        if os.getenv("OPENCODE_AVAILABLE") or include_mock:
            registry.register(_opencode_default())

        if os.getenv("CODEX_AVAILABLE") or include_mock:
            registry.register(_codex_default())

        if include_mock:
            registry.register(_mock_default())

        return registry


def _claude_default() -> AgentDefinition:
    return AgentDefinition(
        id="claude-opus-4",
        name="Claude Opus 4",
        version="4.0.0",
        provider=AgentProvider.ANTHROPIC,
        capabilities=(
            AgentCapability(domain="software", skills=frozenset({"design", "implementation", "review"}), weight=0.9),
            AgentCapability(domain="reasoning", skills=frozenset({"analysis", "planning"}), weight=0.95),
        ),
        cost=AgentCost(avg_cost_per_call=0.15, avg_input_token_cost=0.000015, avg_output_token_cost=0.000075),
        latency_profile=LatencyProfile(p50_ms=2000, p95_ms=8000, p99_ms=15000),
        max_context_tokens=200_000,
        adapter_class_name="allbrain.agents.adapters.claude.ClaudeAdapter",
        safety_limits=SafetyLimits(max_cost_per_call=2.0, max_cost_per_workflow=20.0),
    )


def _openai_default() -> AgentDefinition:
    return AgentDefinition(
        id="gpt-4-turbo",
        name="GPT-4 Turbo",
        version="1.0.0",
        provider=AgentProvider.OPENAI,
        capabilities=(
            AgentCapability(domain="software", skills=frozenset({"implementation", "testing"}), weight=0.85),
            AgentCapability(domain="reasoning", skills=frozenset({"analysis"}), weight=0.8),
        ),
        cost=AgentCost(avg_cost_per_call=0.10, avg_input_token_cost=0.00001, avg_output_token_cost=0.00003),
        latency_profile=LatencyProfile(p50_ms=1500, p95_ms=6000, p99_ms=12000),
        max_context_tokens=128_000,
        adapter_class_name="allbrain.agents.adapters.openai.OpenAIAdapter",
    )


def _gemini_default() -> AgentDefinition:
    return AgentDefinition(
        id="gemini-pro",
        name="Gemini Pro",
        version="1.0.0",
        provider=AgentProvider.GOOGLE,
        capabilities=(
            AgentCapability(domain="software", skills=frozenset({"implementation", "testing", "review"}), weight=0.8),
        ),
        cost=AgentCost(avg_cost_per_call=0.07),
        latency_profile=LatencyProfile(p50_ms=1800, p95_ms=7000, p99_ms=13000),
        max_context_tokens=100_000,
        adapter_class_name="allbrain.agents.adapters.gemini.GeminiAdapter",
    )


def _qwen_default() -> AgentDefinition:
    return AgentDefinition(
        id="qwen-coder",
        name="Qwen Coder",
        version="1.0.0",
        provider=AgentProvider.ALIBABA,
        capabilities=(
            AgentCapability(domain="software", skills=frozenset({"implementation", "testing"}), weight=0.75),
        ),
        cost=AgentCost(avg_cost_per_call=0.02),
        latency_profile=LatencyProfile(p50_ms=2500, p95_ms=9000, p99_ms=16000),
        max_context_tokens=64_000,
        adapter_class_name="allbrain.agents.adapters.qwen.QwenAdapter",
    )


def _opencode_default() -> AgentDefinition:
    return AgentDefinition(
        id="opencode-cli",
        name="OpenCode CLI",
        version="1.0.0",
        provider=AgentProvider.OPENCODE,
        capabilities=(
            AgentCapability(domain="software", skills=frozenset({"implementation", "testing", "design", "review"}), weight=0.85),
        ),
        cost=AgentCost(avg_cost_per_call=0.0),
        latency_profile=LatencyProfile(p50_ms=5000, p95_ms=20000, p99_ms=40000),
        max_context_tokens=64_000,
        adapter_class_name="allbrain.agents.adapters.opencode.OpenCodeAdapter",
    )


def _codex_default() -> AgentDefinition:
    return AgentDefinition(
        id="codex-cli",
        name="Codex CLI",
        version="1.0.0",
        provider=AgentProvider.CODEX,
        capabilities=(
            AgentCapability(domain="software", skills=frozenset({"implementation", "testing"}), weight=0.8),
        ),
        cost=AgentCost(avg_cost_per_call=0.0),
        latency_profile=LatencyProfile(p50_ms=4500, p95_ms=18000, p99_ms=35000),
        max_context_tokens=32_000,
        adapter_class_name="allbrain.agents.adapters.codex.CodexAdapter",
    )


def _mock_default() -> AgentDefinition:
    return AgentDefinition(
        id="mock",
        name="Mock Agent",
        version="1.0.0",
        provider=AgentProvider.MOCK,
        capabilities=(
            AgentCapability(domain="software", skills=frozenset({"implementation", "testing", "design", "review"}), weight=1.0),
        ),
        cost=AgentCost(avg_cost_per_call=0.0),
        latency_profile=LatencyProfile(p50_ms=1, p95_ms=5, p99_ms=10),
        max_context_tokens=1_000_000,
        adapter_class_name="allbrain.agents.adapters.mock.MockAdapter",
    )
