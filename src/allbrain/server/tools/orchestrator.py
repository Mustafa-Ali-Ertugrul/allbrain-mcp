"""Domain module: orchestrator and decision pipeline tools."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.events import EventType
from allbrain.models.schemas import (
    OrchestratorInput,
    RunDecisionPipelineInput,
    ToolResult,
    UserInputError,
)
from allbrain.orchestrator import TaskStateReducer
from allbrain.orchestrator.metrics import AgentPerformanceReducer

# is_compatible, OrchestratedResumeEngine imported locally to avoid circular import
from allbrain.runtime_core import SystemDecisionPipeline
from allbrain.runtime_core.constants import (
    DEFAULT_COUNTERFACTUAL_LIMIT,
    DEFAULT_FORESIGHT_LIMIT,
    DEFAULT_MAX_HORIZON,
    DEFAULT_PIPELINE_EVENT_LIMIT,
    DEFAULT_REGRET_THRESHOLD,
    DEFAULT_RISK_THRESHOLD,
    DEFAULT_SCENARIO_RECOMMENDATION_THRESHOLD,
    DEFAULT_SCENARIOS_LIMIT,
)
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.queueing import QueueCoordinator
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    maybe_auto_snapshot,
    merge_agent_metrics,
)
from allbrain.server.tools.decorators import handle_tool_errors

# SnapshotRepo imported locally in resume_project_impl to avoid circular import
from allbrain.snapshot.adapters import SnapshotAdapter

logger = logging.getLogger(__name__)


@handle_tool_errors
def orchestrate_project_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    """Build orchestrated project view with task state and agent assignments.

    Combines snapshot-based state (if available) with incremental event replay
    to construct the full orchestration view. Uses OrchestratedResumeEngine
    to merge task state, agent metrics, and global context.

    Returns:
        ToolResult with orchestration data including task_view, agent_queue,
        and global_view, or error if project doesn't exist or resume fails.

    Raises:
        ValueError: If project does not exist or base resume fails.
    """
    data = OrchestratorInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    project_path = context.project_path
    project = context.repository.get_project_by_path(project_path)
    if project is None or project.id is None:
        raise ValueError("project does not exist")
    events = context.repository.list_events(project_path=context.project_path, limit=data.limit)
    from allbrain.resume.orchestrated import OrchestratedResumeEngine
    from allbrain.server.tools.snapshots import resume_project_impl
    from allbrain.snapshot.versions import is_compatible

    base = resume_project_impl(
        context,
        limit=data.limit,
        include_git=data.include_git,
        use_snapshot=data.use_snapshot,
    )
    if not base.ok:
        raise ValueError(base.error or "resume failed")
    task_state = None
    if data.use_snapshot:
        from allbrain.storage.snapshot_repo import SnapshotRepo

        snapshot = SnapshotRepo(context.repository.engine).get_latest(project.id)
        if snapshot is not None:
            snapshot = SnapshotAdapter().adapt(snapshot)
        if snapshot is not None and is_compatible(snapshot.metadata):
            delta_events = context.repository.list_events_after(
                project_path=context.project_path,
                event_cursor=snapshot.event_cursor,
            )
            task_state = TaskStateReducer().apply_events(snapshot.state.get("task_view", {}), delta_events)
            snapshot_metrics = snapshot.state.get("agent_metrics", {})
            delta_metrics = AgentPerformanceReducer().reduce(delta_events)
            metrics = merge_agent_metrics(snapshot_metrics, delta_metrics)
    metrics = locals().get("metrics")
    engine = OrchestratedResumeEngine()
    if task_state is not None:
        result = engine.build_from_task_state(task_state=task_state, base=base.data, metrics=metrics)
        result["global_view"]["orchestrator_snapshot_used"] = True
    else:
        result = engine.build(events=events, base=base.data)
        result["global_view"]["orchestrator_snapshot_used"] = False
    audit_tool_call(
        context,
        tool_name="orchestrate_project",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data=result)


@handle_tool_errors
def run_decision_pipeline_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    """Run decision pipeline with optional reasoning stages.

    Executes the system decision pipeline with configurable stages including
    counterfactual reasoning, scenario planning, foresight, meta-reasoning,
    uncertainty estimation, and information seeking.

    Returns:
        ToolResult with pipeline execution results or error message.
    """
    data = RunDecisionPipelineInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)

    result = SystemDecisionPipeline().run(
        context,
        data.objective,
        execute_mode=data.execute_mode,
        limit=data.limit,
        simulate_before_execute=data.simulate_before_execute,
        risk_threshold=data.risk_threshold,
        enable_counterfactual=data.enable_counterfactual,
        counterfactual_limit=data.counterfactual_limit,
        regret_threshold=data.regret_threshold,
        enable_scenarios=data.enable_scenarios,
        scenarios_limit=data.scenarios_limit,
        scenario_recommendation_threshold=data.scenario_recommendation_threshold,
        enable_foresight=data.enable_foresight,
        foresight_limit=data.foresight_limit,
        max_horizon=data.max_horizon,
        enable_meta_reasoning=data.enable_meta_reasoning,
        enable_uncertainty=data.enable_uncertainty,
        enable_information_seeking=data.enable_information_seeking,
    )
    if data.execute_mode == "queued_runtime" and result.get("status") not in ("BLOCKED", "FAILED"):
        result["queue"] = QueueCoordinator(context).enqueue_pipeline_result(result)
    audit_tool_call(
        context,
        tool_name="run_decision_pipeline",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    maybe_auto_snapshot(context, project_path=context.project_path)
    return ToolResult(ok=True, data=result)


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def orchestrate_project(
        limit: int = DEFAULT_PIPELINE_EVENT_LIMIT,
        include_git: bool = True,
        use_snapshot: bool = True,
    ) -> dict[str, Any]:
        result = orchestrate_project_impl(
            context,
            limit=limit,
            include_git=include_git,
            use_snapshot=use_snapshot,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def run_decision_pipeline(
        objective: dict[str, Any],
        execute_mode: str = "event_only",
        limit: int = DEFAULT_PIPELINE_EVENT_LIMIT,
        simulate_before_execute: bool = False,
        risk_threshold: float = DEFAULT_RISK_THRESHOLD,
        enable_counterfactual: bool = False,
        counterfactual_limit: int = DEFAULT_COUNTERFACTUAL_LIMIT,
        regret_threshold: float = DEFAULT_REGRET_THRESHOLD,
        enable_scenarios: bool = False,
        scenarios_limit: int = DEFAULT_SCENARIOS_LIMIT,
        scenario_recommendation_threshold: float = DEFAULT_SCENARIO_RECOMMENDATION_THRESHOLD,
        enable_foresight: bool = False,
        foresight_limit: int = DEFAULT_FORESIGHT_LIMIT,
        max_horizon: int = DEFAULT_MAX_HORIZON,
        enable_meta_reasoning: bool = False,
        enable_uncertainty: bool = False,
        enable_information_seeking: bool = False,
    ) -> dict[str, Any]:
        result = run_decision_pipeline_impl(
            context,
            objective=objective,
            execute_mode=execute_mode,
            limit=limit,
            simulate_before_execute=simulate_before_execute,
            risk_threshold=risk_threshold,
            enable_counterfactual=enable_counterfactual,
            counterfactual_limit=counterfactual_limit,
            regret_threshold=regret_threshold,
            enable_scenarios=enable_scenarios,
            scenarios_limit=scenarios_limit,
            scenario_recommendation_threshold=scenario_recommendation_threshold,
            enable_foresight=enable_foresight,
            foresight_limit=foresight_limit,
            max_horizon=max_horizon,
            enable_meta_reasoning=enable_meta_reasoning,
            enable_uncertainty=enable_uncertainty,
            enable_information_seeking=enable_information_seeking,
        )
        return result.model_dump(mode="json")
