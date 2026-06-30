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
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    maybe_auto_snapshot,
    merge_agent_metrics,
)

# SnapshotRepo imported locally in resume_project_impl to avoid circular import
from allbrain.snapshot.adapters import SnapshotAdapter

logger = logging.getLogger(__name__)


def orchestrate_project_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
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
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def run_decision_pipeline_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
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
        audit_tool_call(
            context,
            tool_name="run_decision_pipeline",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=context.project_path)
        return ToolResult(ok=True, data=result)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def orchestrate_project(
        limit: int = 5000,
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
        limit: int = 5000,
        simulate_before_execute: bool = False,
        risk_threshold: float = 0.7,
        enable_counterfactual: bool = False,
        counterfactual_limit: int = 3,
        regret_threshold: float = 0.20,
        enable_scenarios: bool = False,
        scenarios_limit: int = 4,
        scenario_recommendation_threshold: float = 0.50,
        enable_foresight: bool = False,
        foresight_limit: int = 5,
        max_horizon: int = 5,
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
