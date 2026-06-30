from __future__ import annotations

import logging

from fastmcp import FastMCP

from allbrain.server.context import BrainContext
from allbrain.server.lifecycle import AllBrainMiddleware, create_lifespan
from allbrain.server.tools import register_all_tools

# Re-exports of all *_impl functions for backward compatibility with tests.
from allbrain.server.tools.conflicts import (
    detect_conflicts_impl,
    resolve_conflicts_impl,
)
from allbrain.server.tools.counterfactual import (
    generate_counterfactual_impl,
    rank_alternatives_impl,
)
from allbrain.server.tools.events import list_events_impl, save_event_impl
from allbrain.server.tools.foresight import (
    estimate_confidence_impl,
    evaluate_plan_impl,
    explain_decision_impl,
    generate_future_plans_impl,
)
from allbrain.server.tools.git import (
    get_git_context_impl,
    get_git_status_impl,
    get_recent_changes_impl,
)
from allbrain.server.tools.intents import (
    detect_contradictions_impl,
    extract_intents_impl,
)
from allbrain.server.tools.knowledge import (
    detect_knowledge_gaps_impl,
    estimate_information_gain_impl,
    estimate_information_gain_v2_impl,
    estimate_uncertainty_impl,
    identify_information_needs_impl,
    query_belief_impl,
    recommend_policy_impl,
)
from allbrain.server.tools.memory import (
    build_memory_impl,
    retrieve_memory_impl,
)
from allbrain.server.tools.observability import (
    compare_agents_impl,
    get_observability_dashboard_impl,
    get_reliability_status_impl,
    get_system_metrics_impl,
    get_workflow_graph_impl,
    get_workflow_trace_impl,
    replay_workflow_impl,
)
from allbrain.server.tools.orchestrator import (
    orchestrate_project_impl,
    run_decision_pipeline_impl,
)
from allbrain.server.tools.scenarios import (
    evaluate_scenarios_impl,
    generate_scenarios_impl,
)
from allbrain.server.tools.snapshots import (
    create_snapshot_impl,
    resume_project_impl,
    resume_with_intent_impl,
)
from allbrain.server.tools.tasks import (
    add_task_dependency_impl,
    assign_task_impl,
    change_task_priority_impl,
    create_task_impl,
    get_task_graph_impl,
    handoff_task_impl,
)
from allbrain.server.tools.ui import (
    get_ui_graph_view_impl,
    get_ui_metrics_view_impl,
    get_ui_replay_view_impl,
    get_ui_trace_view_impl,
)
from allbrain.server.tools.world import (
    observe_world_impl,
    simulate_action_impl,
)

logger = logging.getLogger(__name__)


def create_mcp_server(context: BrainContext) -> FastMCP:
    mcp = FastMCP(
        "AllBrain MCP",
        middleware=[AllBrainMiddleware(context)],
        lifespan=create_lifespan(context),
    )
    register_all_tools(mcp, context)
    return mcp
