"""Tool registration - delegates to domain modules dynamically."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from typing import Any, Literal

import allbrain.server.tools

logger = logging.getLogger(__name__)

ToolProfile = Literal["core", "full", "minimal", "memory", "collaboration", "reasoning"]

CORE_TOOL_NAMES = frozenset(
    {
        "save_event",
        "list_events",
        "retrieve_memory",
        "git_info",
        "create_task",
        "get_task_graph",
        "orchestrate_project",
        "run_decision_pipeline",
        "create_snapshot",
        "resume_project",
        "get_context_pack",
    }
)

MINIMAL_TOOL_NAMES = frozenset(
    {
        "save_event",
        "list_events",
        "resume_project",
    }
)

MEMORY_TOOL_NAMES = MINIMAL_TOOL_NAMES | {"retrieve_memory", "get_context_pack"}

COLLABORATION_TOOL_NAMES = MEMORY_TOOL_NAMES | {
    "create_task",
    "get_task_graph",
    "orchestrate_project",
    "detect_conflicts",
    "resolve_conflicts",
}

REASONING_TOOL_NAMES = MEMORY_TOOL_NAMES | {
    "run_decision_pipeline",
    "generate_counterfactual",
    "generate_scenarios",
    "generate_future_plans",
    "evaluate_plan",
    "evaluate_scenarios",
    "estimate_uncertainty",
    "estimate_information_gain",
    "identify_information_needs",
}


def _allowed_for_profile(profile: ToolProfile) -> frozenset[str] | None:
    mapping: dict[ToolProfile, frozenset[str]] = {
        "minimal": MINIMAL_TOOL_NAMES,
        "memory": MEMORY_TOOL_NAMES,
        "collaboration": COLLABORATION_TOOL_NAMES,
        "reasoning": REASONING_TOOL_NAMES,
    }
    return mapping.get(profile)  # type: ignore[arg-type]


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
    valid_profiles = {"core", "full", "minimal", "memory", "collaboration", "reasoning"}
    if tool_profile not in valid_profiles:
        raise ValueError(f"Unknown tool profile: {tool_profile}")
    if tool_profile == "core":
        allowed: frozenset[str] | None = CORE_TOOL_NAMES
    elif tool_profile == "full":
        allowed = None
    else:
        allowed = _allowed_for_profile(tool_profile)
    registrar = _ProfiledToolRegistrar(mcp, allowed=allowed)

    # Dynamically scan, import, and register all modules in the package
    for _, module_name, _ in pkgutil.iter_modules(allbrain.server.tools.__path__):
        # Skip private helpers and decorators which don't register tools
        if module_name.startswith("_") or module_name == "decorators":
            continue
        try:
            domain = importlib.import_module(f"allbrain.server.tools.{module_name}")
            if hasattr(domain, "register_tools"):
                domain.register_tools(registrar, context)
        except Exception:
            logger.exception("Failed to load and register tools from domain module: %s", module_name)
            raise

    if tool_profile in ("core",) and registrar.registered != CORE_TOOL_NAMES:
        missing = sorted(CORE_TOOL_NAMES - registrar.registered)
        raise RuntimeError(f"Core MCP tool profile is incomplete: {missing}")
    return frozenset(registrar.registered)
