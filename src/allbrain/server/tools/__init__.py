"""Tool registration - delegates to domain modules."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from allbrain.server.tools import (
    conflicts,
    counterfactual,
    events,
    foresight,
    git,
    intents,
    knowledge,
    memory,
    observability,
    orchestrator,
    queue,
    scenarios,
    sessions,
    snapshots,
    tasks,
    ui,
    world,
)

ToolProfile = Literal["core", "full"]

CORE_TOOL_NAMES = frozenset(
    {
        "save_event",
        "list_events",
        "retrieve_memory",
        "get_git_context",
        "get_git_status",
        "get_recent_changes",
        "create_task",
        "get_task_graph",
        "orchestrate_project",
        "run_decision_pipeline",
        "create_snapshot",
        "resume_project",
    }
)


class _ProfiledToolRegistrar:
    """Filter tool registration and reject duplicate public tool names."""

    def __init__(self, mcp: Any, *, allowed: frozenset[str] | None):
        self._mcp = mcp
        self._allowed = allowed
        self.registered: set[str] = set()

    def tool(self, function: Callable[..., Any] | None = None, **kwargs: Any):
        def register(candidate: Callable[..., Any]):
            name = str(kwargs.get("name") or candidate.__name__)
            if self._allowed is not None and name not in self._allowed:
                return candidate
            if name in self.registered:
                raise RuntimeError(f"Duplicate MCP tool registration: {name}")
            self.registered.add(name)
            return self._mcp.tool(candidate, **kwargs)

        return register if function is None else register(function)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mcp, name)


def register_all_tools(mcp: Any, context: Any, *, tool_profile: ToolProfile = "full") -> frozenset[str]:
    if tool_profile not in {"core", "full"}:
        raise ValueError(f"Unknown tool profile: {tool_profile}")
    allowed = CORE_TOOL_NAMES if tool_profile == "core" else None
    registrar = _ProfiledToolRegistrar(mcp, allowed=allowed)
    for domain in (
        conflicts,
        counterfactual,
        events,
        foresight,
        git,
        intents,
        knowledge,
        memory,
        observability,
        orchestrator,
        queue,
        scenarios,
        snapshots,
        sessions,
        tasks,
        ui,
        world,
    ):
        domain.register_tools(registrar, context)
    if tool_profile == "core" and registrar.registered != CORE_TOOL_NAMES:
        missing = sorted(CORE_TOOL_NAMES - registrar.registered)
        raise RuntimeError(f"Core MCP tool profile is incomplete: {missing}")
    return frozenset(registrar.registered)
