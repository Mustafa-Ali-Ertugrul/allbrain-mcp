"""Tool registration - delegates to domain modules."""

from __future__ import annotations

from allbrain.server.tools import (
    conflicts,
    counterfactual,
    decisions,
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


def register_all_tools(mcp, context) -> None:
    conflicts.register_tools(mcp, context)
    counterfactual.register_tools(mcp, context)
    decisions.register_tools(mcp, context)
    events.register_tools(mcp, context)
    foresight.register_tools(mcp, context)
    git.register_tools(mcp, context)
    intents.register_tools(mcp, context)
    knowledge.register_tools(mcp, context)
    memory.register_tools(mcp, context)
    observability.register_tools(mcp, context)
    orchestrator.register_tools(mcp, context)
    queue.register_tools(mcp, context)
    scenarios.register_tools(mcp, context)
    snapshots.register_tools(mcp, context)
    sessions.register_tools(mcp, context)
    tasks.register_tools(mcp, context)
    ui.register_tools(mcp, context)
    world.register_tools(mcp, context)
