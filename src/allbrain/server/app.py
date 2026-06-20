from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import ValidationError

from allbrain.gitbrain import GitBrain
from allbrain.intent import IntentExtractor, IntentStore
from allbrain.contradiction import ContradictionDetector
from allbrain.models.entities import Session
from allbrain.models.schemas import (
    AlternativeRankingInput,
    AssignTaskInput,
    ConflictInput,
    CounterfactualInput,
    CreateSnapshotInput,
    CreateTaskInput,
    EvaluateScenariosInput,
    GenerateScenariosInput,
    GitContextInput,
    HandoffTaskInput,
    IntentInput,
    ListEventsInput,
    ObserveWorldInput,
    OrchestratorInput,
    RecentChangesInput,
    ResumeProjectInput,
    RunDecisionPipelineInput,
    SaveEventInput,
    SimulateActionInput,
    TaskDependencyInput,
    TaskPriorityInput,
    ToolResult,
)
from allbrain.api import ObservabilityAPI
from allbrain.memory import MemoryBuilder, MemoryRetriever, WorkflowMemoryStore
from allbrain.observability import ObservabilityBuilder
from allbrain.policy import RoutingEngine
from allbrain.reliability import ReliabilityMetrics
from allbrain.ui import GraphExplorer, MetricsDashboard, ReplayViewer, TraceViewer
from allbrain.events import EventType
from allbrain.conflict import ConflictDetector, ConflictResolver
from allbrain.context import ParallelContextBuilder
from allbrain.orchestrator import DeterministicScheduler, HandoffEngine, TaskGraphBuilder, TaskStateReducer
from allbrain.orchestrator.metrics import AgentPerformanceReducer
from allbrain.orchestrator.state import AgentStateBuilder
from allbrain.resume import IncrementalResumeEngine, IntentResumeEngine, MultiAgentResumeEngine, ResumeEngine
from allbrain.resume.orchestrated import OrchestratedResumeEngine
from allbrain.snapshot import SnapshotBuilder, SnapshotEngine
from allbrain.snapshot.adapters import SnapshotAdapter
from allbrain.snapshot.trigger import snapshot_weight
from allbrain.snapshot.versions import is_compatible
from allbrain.storage.repository import BrainRepository, event_to_read
from allbrain.storage.snapshot_repo import SnapshotRepo
from allbrain.counterfactual import (
    AlternativeRanker,
    CounterfactualEngine,
    recommendation_severity,
)
from allbrain.scenarios import (
    SCENARIO_TEMPLATE_VERSION,
    ScenarioAnalysis,
    ScenarioEngine,
)
from allbrain.world import WorldModel


@dataclass
class BrainContext:
    repository: BrainRepository
    project_path: str
    active_session: Session | None
    auto_snapshot_threshold: int = 100

    @property
    def active_session_id(self) -> int | None:
        if self.active_session is None:
            return None
        return self.active_session.id


def create_mcp_server(context: BrainContext) -> FastMCP:
    mcp = FastMCP("AllBrain MCP")

    @mcp.tool
    def save_event(
        type: str,
        payload: dict[str, Any],
        file_path: str | None = None,
        project_path: str | None = None,
        source: str = "agent",
        session_id: int | None = None,
        agent_id: str | None = None,
        task_hint: str | None = None,
        importance: int | None = None,
        impact_score: float | None = None,
        caused_by: str | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        result = save_event_impl(
            context,
            type=type,
            payload=payload,
            file_path=file_path,
            project_path=project_path,
            source=source,
            session_id=session_id,
            agent_id=agent_id,
            task_hint=task_hint,
            importance=importance,
            impact_score=impact_score,
            caused_by=caused_by,
            branch=branch,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def list_events(
        project_path: str | None = None,
        session_id: int | None = None,
        agent_id: str | None = None,
        type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        result = list_events_impl(
            context,
            project_path=project_path,
            session_id=session_id,
            agent_id=agent_id,
            type=type,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def resume_project(
        project_path: str | None = None,
        limit: int = 5000,
        include_git: bool = True,
        use_snapshot: bool = True,
    ) -> dict[str, Any]:
        result = resume_project_impl(
            context,
            project_path=project_path,
            limit=limit,
            include_git=include_git,
            use_snapshot=use_snapshot,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def create_snapshot(
        project_path: str | None = None,
        limit: int = 5000,
        force: bool = False,
        include_derived: bool = False,
    ) -> dict[str, Any]:
        result = create_snapshot_impl(
            context,
            project_path=project_path,
            limit=limit,
            force=force,
            include_derived=include_derived,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_git_context(project_path: str | None = None) -> dict[str, Any]:
        result = get_git_context_impl(context, project_path=project_path)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_git_status(project_path: str | None = None) -> dict[str, Any]:
        result = get_git_status_impl(context, project_path=project_path)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_recent_changes(project_path: str | None = None, limit: int = 10) -> dict[str, Any]:
        result = get_recent_changes_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def detect_conflicts(project_path: str | None = None, limit: int = 5000, threshold: float = 0.7) -> dict[str, Any]:
        result = detect_conflicts_impl(context, project_path=project_path, limit=limit, threshold=threshold)
        return result.model_dump(mode="json")

    @mcp.tool
    def resolve_conflicts(project_path: str | None = None, limit: int = 5000, threshold: float = 0.7) -> dict[str, Any]:
        result = resolve_conflicts_impl(context, project_path=project_path, limit=limit, threshold=threshold)
        return result.model_dump(mode="json")

    @mcp.tool
    def extract_intents(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = extract_intents_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def detect_contradictions(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = detect_contradictions_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def resume_with_intent(
        project_path: str | None = None,
        limit: int = 5000,
        include_git: bool = True,
        use_snapshot: bool = True,
    ) -> dict[str, Any]:
        result = resume_with_intent_impl(
            context,
            project_path=project_path,
            limit=limit,
            include_git=include_git,
            use_snapshot=use_snapshot,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def create_task(
        goal: str,
        kind: str = "implementation",
        related_files: list[str] | None = None,
        priority: int = 3,
        task_id: str | None = None,
        project_path: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        result = create_task_impl(
            context,
            goal=goal,
            kind=kind,
            related_files=related_files or [],
            priority=priority,
            task_id=task_id,
            project_path=project_path,
            agent_id=agent_id,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def assign_task(
        task_id: str,
        agent_id: str | None = None,
        project_path: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = assign_task_impl(context, task_id=task_id, agent_id=agent_id, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def add_task_dependency(
        task_id: str,
        depends_on: str,
        project_path: str | None = None,
    ) -> dict[str, Any]:
        result = add_task_dependency_impl(context, task_id=task_id, depends_on=depends_on, project_path=project_path)
        return result.model_dump(mode="json")

    @mcp.tool
    def change_task_priority(
        task_id: str,
        new: int,
        old: int | None = None,
        project_path: str | None = None,
    ) -> dict[str, Any]:
        result = change_task_priority_impl(context, task_id=task_id, old=old, new=new, project_path=project_path)
        return result.model_dump(mode="json")

    @mcp.tool
    def handoff_task(
        task_id: str,
        from_agent: str,
        to_agent: str | None = None,
        reason: str | None = None,
        project_path: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = handoff_task_impl(
            context,
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
            project_path=project_path,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_task_graph(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = get_task_graph_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def orchestrate_project(
        project_path: str | None = None,
        limit: int = 5000,
        include_git: bool = True,
        use_snapshot: bool = True,
    ) -> dict[str, Any]:
        result = orchestrate_project_impl(
            context,
            project_path=project_path,
            limit=limit,
            include_git=include_git,
            use_snapshot=use_snapshot,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def run_decision_pipeline(
        objective: dict[str, Any],
        execute_mode: str = "event_only",
        project_path: str | None = None,
        limit: int = 5000,
        simulate_before_execute: bool = False,
        risk_threshold: float = 0.7,
        enable_counterfactual: bool = False,
        counterfactual_limit: int = 3,
        regret_threshold: float = 0.20,
        enable_scenarios: bool = False,
        scenarios_limit: int = 4,
        scenario_recommendation_threshold: float = 0.50,
    ) -> dict[str, Any]:
        result = run_decision_pipeline_impl(
            context,
            objective=objective,
            execute_mode=execute_mode,
            project_path=project_path,
            limit=limit,
            simulate_before_execute=simulate_before_execute,
            risk_threshold=risk_threshold,
            enable_counterfactual=enable_counterfactual,
            counterfactual_limit=counterfactual_limit,
            regret_threshold=regret_threshold,
            enable_scenarios=enable_scenarios,
            scenarios_limit=scenarios_limit,
            scenario_recommendation_threshold=scenario_recommendation_threshold,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def observe_world(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = observe_world_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def simulate_action(
        action: str,
        project_path: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = simulate_action_impl(context, action=action, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def generate_counterfactual(
        action: str,
        project_path: str | None = None,
        limit: int = 5000,
        counterfactual_limit: int = 3,
    ) -> dict[str, Any]:
        result = generate_counterfactual_impl(
            context,
            action=action,
            project_path=project_path,
            limit=limit,
            counterfactual_limit=counterfactual_limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def rank_alternatives(
        actions: list[str],
        project_path: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = rank_alternatives_impl(context, actions=actions, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def generate_scenarios(
        action: str,
        project_path: str | None = None,
        limit: int = 5000,
        scenarios_limit: int = 4,
    ) -> dict[str, Any]:
        result = generate_scenarios_impl(
            context,
            action=action,
            project_path=project_path,
            limit=limit,
            scenarios_limit=scenarios_limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def evaluate_scenarios(
        action: str,
        scenarios: list[dict[str, Any]],
        project_path: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = evaluate_scenarios_impl(
            context,
            action=action,
            scenarios=scenarios,
            project_path=project_path,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_observability_dashboard(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = get_observability_dashboard_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_workflow_trace(
        workflow_id: str | None = None,
        task_id: str | None = None,
        project_path: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_workflow_trace_impl(
            context,
            workflow_id=workflow_id,
            task_id=task_id,
            project_path=project_path,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_system_metrics(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = get_system_metrics_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_reliability_status(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = get_reliability_status_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def replay_workflow(
        project_path: str | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        cursor: int = 0,
        step_count: int | None = None,
        deterministic: bool = True,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = replay_workflow_impl(
            context,
            project_path=project_path,
            workflow_id=workflow_id,
            task_id=task_id,
            cursor=cursor,
            step_count=step_count,
            deterministic=deterministic,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_workflow_graph(
        project_path: str | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_workflow_graph_impl(
            context,
            project_path=project_path,
            workflow_id=workflow_id,
            task_id=task_id,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def compare_agents(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = compare_agents_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def build_memory(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = build_memory_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def retrieve_memory(
        query: str,
        project_path: str | None = None,
        limit: int = 5000,
        top_k: int = 5,
    ) -> dict[str, Any]:
        result = retrieve_memory_impl(context, query=query, project_path=project_path, limit=limit, top_k=top_k)
        return result.model_dump(mode="json")

    @mcp.tool
    def recommend_policy(
        task: dict[str, Any],
        project_path: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = recommend_policy_impl(context, task=task, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_ui_trace_view(
        project_path: str | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_ui_trace_view_impl(context, project_path=project_path, workflow_id=workflow_id, task_id=task_id, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_ui_replay_view(
        project_path: str | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        cursor: int = 0,
        step_count: int | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_ui_replay_view_impl(
            context,
            project_path=project_path,
            workflow_id=workflow_id,
            task_id=task_id,
            cursor=cursor,
            step_count=step_count,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_ui_graph_view(
        project_path: str | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_ui_graph_view_impl(context, project_path=project_path, workflow_id=workflow_id, task_id=task_id, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_ui_metrics_view(project_path: str | None = None, limit: int = 5000) -> dict[str, Any]:
        result = get_ui_metrics_view_impl(context, project_path=project_path, limit=limit)
        return result.model_dump(mode="json")

    return mcp


def save_event_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = SaveEventInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, data.session_id)
        project_path = data.project_path or context.project_path
        event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=data.type,
            source=data.source,
            payload=data.payload,
            file_path=data.file_path,
            agent_id=data.agent_id,
            task_hint=data.task_hint,
            importance=data.importance,
            impact_score=data.impact_score,
            caused_by=data.caused_by,
            branch=data.branch,
        )
        audit_tool_call(
            context,
            tool_name="save_event",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(ok=True, data=event_to_read(event).model_dump(mode="json"))
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def list_events_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = ListEventsInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(
            project_path=project_path,
            session_id=data.session_id,
            agent_id=data.agent_id,
            type=data.type,
            limit=data.limit,
        )
        audit_tool_call(
            context,
            tool_name="list_events",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=[event.model_dump(mode="json") for event in events])
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def resume_project_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = ResumeProjectInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        project = context.repository.get_project_by_path(project_path)
        if project is None or project.id is None:
            raise ValueError("project does not exist")
        events = None
        if not data.use_snapshot:
            events = context.repository.list_events(project_path=project_path, limit=data.limit)
        all_events = events
        if all_events is None:
            snapshot = SnapshotRepo(context.repository.engine).get_latest(project.id)
            if snapshot is not None and is_compatible(snapshot.metadata):
                all_events = context.repository.list_events_after(project_path=project_path, event_cursor=snapshot.event_cursor)
            else:
                all_events = context.repository.list_events(project_path=project_path, limit=data.limit)
        incremental = IncrementalResumeEngine(
            repository=context.repository,
            snapshot_repo=SnapshotRepo(context.repository.engine),
        )
        resume = MultiAgentResumeEngine(incremental).resume(
            project_path=project_path,
            project_id=project.id,
            events=all_events if events is None else events,
            limit=data.limit,
            include_git=data.include_git,
            use_snapshot=data.use_snapshot,
        )
        audit_tool_call(
            context,
            tool_name="resume_project",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=resume)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def create_snapshot_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = CreateSnapshotInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        project = context.repository.get_project_by_path(project_path)
        if project is None or project.id is None:
            raise ValueError("project does not exist")

        snapshot_repo = SnapshotRepo(context.repository.engine)
        latest = snapshot_repo.get_latest(project.id)
        if latest is not None and not data.force:
            delta_events = context.repository.list_events_after(
                project_path=project_path,
                event_cursor=latest.event_cursor,
            )
            if semantic_event_count(delta_events) == 0:
                audit_tool_call(
                    context,
                    tool_name="create_snapshot",
                    tool_args=data.model_dump(mode="json"),
                    project_path=project_path,
                    session_id=bound_session_id,
                )
                return ToolResult(ok=True, data=snapshot_to_dict(latest) | {"reused": True})

        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        snapshot = SnapshotEngine(SnapshotBuilder(include_derived=data.include_derived), snapshot_repo).build_snapshot(
            project_id=project.id,
            events=events,
        )
        audit_tool_call(
            context,
            tool_name="create_snapshot",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=snapshot_to_dict(snapshot) | {"reused": False})
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_git_context_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = GitContextInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        git_context = GitBrain(project_path).build_git_context()
        audit_tool_call(
            context,
            tool_name="get_git_context",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=git_context)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_git_status_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = GitContextInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        git_status = GitBrain(project_path).get_status()
        audit_tool_call(
            context,
            tool_name="get_git_status",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=git_status)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_recent_changes_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = RecentChangesInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        recent_changes = GitBrain(project_path).get_recent_changes(limit=data.limit)
        audit_tool_call(
            context,
            tool_name="get_recent_changes",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=recent_changes)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def detect_conflicts_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = ConflictInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        conflicts = ConflictDetector().detect(events, threshold=data.threshold)
        audit_tool_call(
            context,
            tool_name="detect_conflicts",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data={"conflicts": conflicts, "count": len(conflicts)})
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def resolve_conflicts_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = ConflictInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        conflicts = ConflictDetector().detect(events, threshold=data.threshold)
        agent_view = ParallelContextBuilder().build_agent_view(events)
        resolved = ConflictResolver().resolve(conflicts, events, agent_view)
        audit_tool_call(
            context,
            tool_name="resolve_conflicts",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data={"resolved_conflicts": resolved, "count": len(resolved)})
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def extract_intents_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = IntentInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        intents = IntentExtractor().extract(events)
        audit_tool_call(
            context,
            tool_name="extract_intents",
            tool_args={"project_path": data.project_path, "limit": data.limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data={"intents": [intent.model_dump(mode="json") for intent in intents], "count": len(intents)})
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def detect_contradictions_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = IntentInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        intents = IntentExtractor().extract(events)
        contradictions = ContradictionDetector().detect(intents)
        audit_tool_call(
            context,
            tool_name="detect_contradictions",
            tool_args={"project_path": data.project_path, "limit": data.limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data={"contradictions": contradictions, "count": len(contradictions)})
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def resume_with_intent_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = IntentInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        project = context.repository.get_project_by_path(project_path)
        if project is None or project.id is None:
            raise ValueError("project does not exist")
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        incremental = IncrementalResumeEngine(
            repository=context.repository,
            snapshot_repo=SnapshotRepo(context.repository.engine),
        )
        multi_agent = MultiAgentResumeEngine(incremental)
        result = IntentResumeEngine(multi_agent).resume(
            events=events,
            project_path=project_path,
            project_id=project.id,
            limit=data.limit,
            include_git=data.include_git,
            use_snapshot=data.use_snapshot,
        )
        audit_tool_call(
            context,
            tool_name="resume_with_intent",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def create_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = CreateTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        task_id = data.task_id or TaskStateReducer.new_task_id()
        event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.TASK_CREATED.value,
            source="allbrain",
            payload={
                "task_id": task_id,
                "goal": data.goal,
                "kind": data.kind,
                "related_files": data.related_files,
                "priority": data.priority,
            },
            agent_id=data.agent_id,
            task_hint=data.goal,
            importance=data.priority,
        )
        audit_tool_call(
            context,
            tool_name="create_task",
            tool_args=data.model_dump(mode="json") | {"task_id": task_id},
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(ok=True, data=event_to_read(event).model_dump(mode="json"))
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def assign_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = AssignTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        task_state = TaskStateReducer().build(events)
        task = get_task_or_raise(task_state, data.task_id)
        metrics = AgentPerformanceReducer().reduce(events)
        assignment = DeterministicScheduler().choose_agent(
            task=task,
            task_state=task_state,
            explicit_agent_id=data.agent_id,
            events=events,
            metrics=metrics,
        )
        event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.TASK_ASSIGNED.value,
            source="allbrain",
            payload={
                "task_id": data.task_id,
                "agent_id": assignment["agent_id"],
                "score": assignment["score"],
                "breakdown": assignment["breakdown"],
                "reason": assignment["reason"],
                "candidate_agents": assignment["candidate_agents"],
            },
            agent_id=assignment["agent_id"],
            task_hint=task.get("goal"),
        )
        decision_event = append_selection_decision(
            context,
            project_path=project_path,
            session_id=bound_session_id,
            task_id=data.task_id,
            assignment=assignment,
            assignment_event_id=event.id,
            task_hint=task.get("goal"),
        )
        audit_tool_call(
            context,
            tool_name="assign_task",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(
            ok=True,
            data={
                "event": event_to_read(event).model_dump(mode="json"),
                "decision_event": event_to_read(decision_event).model_dump(mode="json"),
                "assignment": assignment,
            },
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def add_task_dependency_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = TaskDependencyInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.TASK_DEPENDENCY_ADDED.value,
            source="allbrain",
            payload={"task_id": data.task_id, "depends_on": data.depends_on},
        )
        audit_tool_call(
            context,
            tool_name="add_task_dependency",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(ok=True, data=event_to_read(event).model_dump(mode="json"))
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def change_task_priority_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = TaskPriorityInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.TASK_PRIORITY_CHANGED.value,
            source="allbrain",
            payload={"task_id": data.task_id, "old": data.old, "new": data.new},
            importance=data.new,
        )
        audit_tool_call(
            context,
            tool_name="change_task_priority",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(ok=True, data=event_to_read(event).model_dump(mode="json"))
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def handoff_task_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = HandoffTaskInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        task_state = TaskStateReducer().build(events)
        task = get_task_or_raise(task_state, data.task_id)
        metrics = AgentPerformanceReducer().reduce(events)
        recommendation = HandoffEngine().recommend(
            task=task,
            task_state=task_state,
            from_agent=data.from_agent,
            to_agent=data.to_agent,
            events=events,
            metrics=metrics,
        )
        handoff_event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.HANDOFF_CREATED.value,
            source="allbrain",
            payload={
                "task_id": data.task_id,
                "from_agent": data.from_agent,
                "to_agent": recommendation["to_agent"],
                "reason": data.reason,
                "assignment": recommendation["assignment"],
            },
            agent_id=data.from_agent,
            task_hint=task.get("goal"),
        )
        assignment = recommendation["assignment"]
        assigned_event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.TASK_ASSIGNED.value,
            source="allbrain",
            payload={
                "task_id": data.task_id,
                "agent_id": assignment["agent_id"],
                "score": assignment["score"],
                "breakdown": assignment["breakdown"],
                "reason": "handoff",
                "candidate_agents": assignment["candidate_agents"],
            },
            agent_id=assignment["agent_id"],
            task_hint=task.get("goal"),
            caused_by=handoff_event.id,
        )
        decision_event = append_selection_decision(
            context,
            project_path=project_path,
            session_id=bound_session_id,
            task_id=data.task_id,
            assignment=assignment,
            assignment_event_id=assigned_event.id,
            task_hint=task.get("goal"),
            caused_by=handoff_event.id,
        )
        audit_tool_call(
            context,
            tool_name="handoff_task",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(
            ok=True,
            data={
                "handoff_event": event_to_read(handoff_event).model_dump(mode="json"),
                "assigned_event": event_to_read(assigned_event).model_dump(mode="json"),
                "decision_event": event_to_read(decision_event).model_dump(mode="json"),
                "handoff": recommendation,
            },
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_task_graph_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = OrchestratorInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        task_state = TaskStateReducer().build(events)
        graph = TaskGraphBuilder().build(task_state)
        metrics = AgentPerformanceReducer().reduce(events)
        agent_state = AgentStateBuilder().build(metrics=metrics, task_state=task_state)
        audit_tool_call(
            context,
            tool_name="get_task_graph",
            tool_args={"project_path": data.project_path, "limit": data.limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data={"task_view": task_state, "task_graph": graph, "agent_state": agent_state})
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def orchestrate_project_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = OrchestratorInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        project = context.repository.get_project_by_path(project_path)
        if project is None or project.id is None:
            raise ValueError("project does not exist")
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        base = resume_project_impl(
            context,
            project_path=project_path,
            limit=data.limit,
            include_git=data.include_git,
            use_snapshot=data.use_snapshot,
        )
        if not base.ok:
            raise ValueError(base.error or "resume failed")
        task_state = None
        if data.use_snapshot:
            snapshot = SnapshotRepo(context.repository.engine).get_latest(project.id)
            if snapshot is not None:
                snapshot = SnapshotAdapter().adapt(snapshot)
            if snapshot is not None and is_compatible(snapshot.metadata):
                delta_events = context.repository.list_events_after(
                    project_path=project_path,
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
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def run_decision_pipeline_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = RunDecisionPipelineInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        from allbrain.runtime_core import SystemDecisionPipeline

        result = SystemDecisionPipeline().run(
            context,
            data.objective,
            execute_mode=data.execute_mode,
            project_path=project_path,
            limit=data.limit,
            simulate_before_execute=data.simulate_before_execute,
            risk_threshold=data.risk_threshold,
            enable_counterfactual=data.enable_counterfactual,
            counterfactual_limit=data.counterfactual_limit,
            regret_threshold=data.regret_threshold,
            enable_scenarios=data.enable_scenarios,
            scenarios_limit=data.scenarios_limit,
            scenario_recommendation_threshold=data.scenario_recommendation_threshold,
        )
        audit_tool_call(
            context,
            tool_name="run_decision_pipeline",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(ok=True, data=result)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def generate_counterfactual_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = CounterfactualInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        world_model = WorldModel()
        engine = CounterfactualEngine()
        current_state = world_model.observe()
        observation_event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="counterfactual",
            payload=current_state.model_dump(mode="json"),
        )
        generated_payload: dict[str, Any] = {"action": data.action, "alternatives": []}
        unknown = not engine.generator.generate(data.action)
        if unknown:
            generated_payload["reason"] = "unknown_action"
        generated_event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.COUNTERFACTUAL_GENERATED.value,
            source="counterfactual",
            payload=generated_payload,
            caused_by=observation_event.id,
        )
        alternatives = engine.generator.generate(data.action)[: data.counterfactual_limit]
        results_payloads: list[dict[str, Any]] = []
        for alternative in alternatives:
            result = engine.evaluator.compare(current_state, data.action, alternative)
            context.repository.append_event(
                project_path=project_path,
                session_id=bound_session_id,
                type=EventType.COUNTERFACTUAL_EVALUATED.value,
                source="counterfactual",
                payload=result.model_dump(mode="json"),
                caused_by=generated_event.id,
                impact_score=result.improvement,
            )
            results_payloads.append(result.model_dump(mode="json"))
        best_payload: dict[str, Any] | None = None
        recommendation_payload: dict[str, Any] | None = None
        if results_payloads:
            best_payload = max(results_payloads, key=lambda item: item["improvement"])
            if best_payload["improvement"] >= 0.20:
                severity = recommendation_severity(best_payload["improvement"])
                recommendation_payload = {"best": best_payload, "threshold": 0.20, "severity": severity}
                context.repository.append_event(
                    project_path=project_path,
                    session_id=bound_session_id,
                    type=EventType.COUNTERFACTUAL_RECOMMENDATION.value,
                    source="counterfactual",
                    payload=recommendation_payload,
                    caused_by=generated_event.id,
                    impact_score=best_payload["improvement"],
                )
        summary = {
            "action": data.action,
            "alternatives": alternatives,
            "unknown_action": unknown,
            "results": results_payloads,
            "best": best_payload,
            "decision_regret": best_payload["regret"] if best_payload else 0.0,
            "recommendation": recommendation_payload,
        }
        audit_tool_call(
            context,
            tool_name="generate_counterfactual",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(ok=True, data=summary)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def rank_alternatives_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = AlternativeRankingInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        world_model = WorldModel()
        current_state = world_model.observe()
        ranker = AlternativeRanker()
        ranked = ranker.rank(current_state, list(data.actions))
        audit_tool_call(
            context,
            tool_name="rank_alternatives",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(
            ok=True,
            data={
                "state": current_state.model_dump(mode="json"),
                "ranked": [item.model_dump(mode="json") for item in ranked],
            },
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def _publish_scenario_events(
    context: BrainContext,
    bound_session_id: int,
    project_path: str,
    analysis: ScenarioAnalysis,
    action: str,
) -> None:
    analysis_payload = analysis.model_dump(mode="json")
    generated_event = context.repository.append_event(
        project_path=project_path,
        session_id=bound_session_id,
        type=EventType.SCENARIO_GENERATED.value,
        source="scenarios",
        payload={
            "action": action,
            "templates": [item.scenario for item in analysis.results],
            "template_version": analysis.template_version,
            "analysis_id": analysis_payload["analysis_id"],
        },
    )
    last_id = generated_event.id
    for result in analysis.results:
        ev_event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.SCENARIO_EVALUATED.value,
            source="scenarios",
            payload={
                "analysis_id": analysis_payload["analysis_id"],
                "scenario": result.scenario,
                "prediction": result.prediction.model_dump(mode="json"),
                "confidence": result.confidence,
            },
            caused_by=last_id,
            impact_score=result.confidence,
        )
        last_id = ev_event.id
    rationale = (
        f"best={analysis.best_case.prediction.success_probability:.2f} "
        f"vs expected={analysis.expected_case.prediction.success_probability:.2f}, "
        f"spread={analysis.prediction_spread:.2f}"
    )
    context.repository.append_event(
        project_path=project_path,
        session_id=bound_session_id,
        type=EventType.SCENARIO_RECOMMENDED.value,
        source="scenarios",
        payload={
            "analysis_id": analysis_payload["analysis_id"],
            "best_case": analysis.best_case.model_dump(mode="json"),
            "expected_case": analysis.expected_case.model_dump(mode="json"),
            "rationale": rationale,
            "template_version": analysis.template_version,
        },
        caused_by=last_id,
        impact_score=analysis.prediction_spread,
    )


def generate_scenarios_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = GenerateScenariosInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        world_model = WorldModel()
        engine = ScenarioEngine()
        current_state = world_model.observe()
        context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="scenarios",
            payload=current_state.model_dump(mode="json"),
        )
        analysis = engine.analyze(current_state, data.action, limit=data.scenarios_limit)
        _publish_scenario_events(context, bound_session_id, project_path, analysis, data.action)
        audit_tool_call(
            context,
            tool_name="generate_scenarios",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(ok=True, data=analysis.model_dump(mode="json"))
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def evaluate_scenarios_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = EvaluateScenariosInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        world_model = WorldModel()
        engine = ScenarioEngine()
        current_state = world_model.observe()
        context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="scenarios",
            payload=current_state.model_dump(mode="json"),
        )
        analysis = engine.evaluate_custom(current_state, data.action, list(data.scenarios))
        _publish_scenario_events(context, bound_session_id, project_path, analysis, data.action)
        audit_tool_call(
            context,
            tool_name="evaluate_scenarios",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(ok=True, data=analysis.model_dump(mode="json"))
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def observe_world_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = ObserveWorldInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        world_model = WorldModel()
        state = world_model.observe()
        event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="world",
            payload=state.model_dump(mode="json"),
        )
        audit_tool_call(
            context,
            tool_name="observe_world",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(
            ok=True,
            data={"state": state.model_dump(mode="json"), "event": event_to_read(event).model_dump(mode="json")},
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def simulate_action_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = SimulateActionInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        world_model = WorldModel()
        state = world_model.observe()
        observation_event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_STATE_OBSERVED.value,
            source="world",
            payload=state.model_dump(mode="json"),
        )
        sim_result = world_model.simulate(data.action, state)
        sim_event = context.repository.append_event(
            project_path=project_path,
            session_id=bound_session_id,
            type=EventType.WORLD_SIMULATION_RUN.value,
            source="world",
            payload=sim_result.model_dump(mode="json"),
            caused_by=observation_event.id,
            impact_score=sim_result.prediction.risk,
        )
        audit_tool_call(
            context,
            tool_name="simulate_action",
            tool_args=data.model_dump(mode="json"),
            project_path=project_path,
            session_id=bound_session_id,
        )
        maybe_auto_snapshot(context, project_path=project_path)
        return ToolResult(
            ok=True,
            data={
                "observation_event": event_to_read(observation_event).model_dump(mode="json"),
                "simulation_event": event_to_read(sim_event).model_dump(mode="json"),
                "simulation": sim_result.model_dump(mode="json"),
            },
        )
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_task_or_raise(task_state: dict[str, Any], task_id: str) -> dict[str, Any]:
    task = task_state.get("tasks", {}).get(task_id)
    if task is None:
        raise ValueError(f"unknown task_id '{task_id}'")
    return task


def get_observability_dashboard_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = OrchestratorInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        audit_tool_call(
            context,
            tool_name="get_observability_dashboard",
            tool_args={"project_path": data.project_path, "limit": data.limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=ObservabilityBuilder().build(events))
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def replay_workflow_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        replay = ObservabilityAPI().replay(
            events,
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
            cursor=int(kwargs.get("cursor", 0) or 0),
            step_count=kwargs.get("step_count"),
            deterministic=bool(kwargs.get("deterministic", True)),
        )
        replay = replay | {
            "tasks": replay["visualization"]["tasks"],
            "task_count": replay["visualization"]["task_count"],
        }
        audit_tool_call(
            context,
            tool_name="replay_workflow",
            tool_args={
                "project_path": kwargs.get("project_path"),
                "workflow_id": kwargs.get("workflow_id"),
                "task_id": kwargs.get("task_id"),
                "cursor": kwargs.get("cursor", 0),
                "step_count": kwargs.get("step_count"),
                "deterministic": kwargs.get("deterministic", True),
                "limit": limit,
            },
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=replay)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_workflow_trace_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        result = ObservabilityAPI().workflow_trace(
            events,
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        audit_tool_call(
            context,
            tool_name="get_workflow_trace",
            tool_args={
                "project_path": kwargs.get("project_path"),
                "workflow_id": kwargs.get("workflow_id"),
                "task_id": kwargs.get("task_id"),
                "limit": limit,
            },
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_system_metrics_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        result = ObservabilityAPI().system_metrics(events)
        result["reliability"] = ReliabilityMetrics().build(events)
        audit_tool_call(
            context,
            tool_name="get_system_metrics",
            tool_args={"project_path": kwargs.get("project_path"), "limit": limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_reliability_status_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        result = ReliabilityMetrics().build(events)
        audit_tool_call(
            context,
            tool_name="get_reliability_status",
            tool_args={"project_path": kwargs.get("project_path"), "limit": limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_workflow_graph_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        result = ObservabilityAPI().graph(
            events,
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        audit_tool_call(
            context,
            tool_name="get_workflow_graph",
            tool_args={
                "project_path": kwargs.get("project_path"),
                "workflow_id": kwargs.get("workflow_id"),
                "task_id": kwargs.get("task_id"),
                "limit": limit,
            },
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def compare_agents_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = OrchestratorInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
        bound_session_id = bind_session_id(context, None)
        project_path = data.project_path or context.project_path
        events = context.repository.list_events(project_path=project_path, limit=data.limit)
        comparison = ObservabilityBuilder().agent_comparison(events)
        audit_tool_call(
            context,
            tool_name="compare_agents",
            tool_args={"project_path": data.project_path, "limit": data.limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=comparison)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def build_memory_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        store = WorkflowMemoryStore(MemoryBuilder().build(events))
        audit_tool_call(
            context,
            tool_name="build_memory",
            tool_args={"project_path": kwargs.get("project_path"), "limit": limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=store.to_dict())
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def retrieve_memory_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        query = kwargs.get("query")
        if not isinstance(query, str) or not query:
            raise ValueError("query is required")
        project_path, limit = observability_project_and_limit(context, kwargs)
        top_k = int(kwargs.get("top_k", 5) or 5)
        if top_k < 1 or top_k > 50:
            raise ValueError("top_k must be between 1 and 50")
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        retriever = MemoryRetriever(MemoryBuilder().build(events))
        result = {
            "similar_workflows": retriever.retrieve_similar_workflows(query, top_k=top_k),
            "failure_patterns": retriever.retrieve_failure_patterns(query, top_k=top_k),
        }
        audit_tool_call(
            context,
            tool_name="retrieve_memory",
            tool_args={"query": query, "project_path": kwargs.get("project_path"), "limit": limit, "top_k": top_k},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def recommend_policy_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        task = kwargs.get("task")
        if not isinstance(task, dict):
            raise ValueError("task must be a dict")
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        memory = MemoryRetriever(MemoryBuilder().build(events))
        recommendation = RoutingEngine().recommend(task=task, events=events, memory=memory)
        audit_tool_call(
            context,
            tool_name="recommend_policy",
            tool_args={"task": task, "project_path": kwargs.get("project_path"), "limit": limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=recommendation)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_ui_trace_view_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = filter_observability_events(
            context.repository.list_events(project_path=project_path, limit=limit),
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        view = TraceViewer().build(events)
        audit_tool_call(
            context,
            tool_name="get_ui_trace_view",
            tool_args={"project_path": kwargs.get("project_path"), "workflow_id": kwargs.get("workflow_id"), "task_id": kwargs.get("task_id"), "limit": limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=view)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_ui_replay_view_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = filter_observability_events(
            context.repository.list_events(project_path=project_path, limit=limit),
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        view = ReplayViewer().build(
            events,
            cursor=int(kwargs.get("cursor", 0) or 0),
            step_count=kwargs.get("step_count"),
        )
        audit_tool_call(
            context,
            tool_name="get_ui_replay_view",
            tool_args={"project_path": kwargs.get("project_path"), "workflow_id": kwargs.get("workflow_id"), "task_id": kwargs.get("task_id"), "cursor": kwargs.get("cursor", 0), "step_count": kwargs.get("step_count"), "limit": limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=view)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_ui_graph_view_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = filter_observability_events(
            context.repository.list_events(project_path=project_path, limit=limit),
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        view = GraphExplorer().build(events)
        audit_tool_call(
            context,
            tool_name="get_ui_graph_view",
            tool_args={"project_path": kwargs.get("project_path"), "workflow_id": kwargs.get("workflow_id"), "task_id": kwargs.get("task_id"), "limit": limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=view)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_ui_metrics_view_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        view = MetricsDashboard().build(events)
        audit_tool_call(
            context,
            tool_name="get_ui_metrics_view",
            tool_args={"project_path": kwargs.get("project_path"), "limit": limit},
            project_path=project_path,
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=view)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def append_selection_decision(
    context: BrainContext,
    *,
    project_path: str,
    session_id: int,
    task_id: str,
    assignment: dict[str, Any],
    assignment_event_id: str,
    task_hint: str | None,
    caused_by: str | None = None,
):
    selection_decision = assignment.get("selection_decision", {})
    return context.repository.append_event(
        project_path=project_path,
        session_id=session_id,
        type=EventType.SELECTION_DECISION.value,
        source="allbrain",
        payload={
            "task_id": task_id,
            "assignment_event_id": assignment_event_id,
            "agent_id": assignment["agent_id"],
            "total_score": assignment["score"],
            "breakdown": assignment["breakdown"],
            "reason": assignment["reason"],
            "fallback_mode": assignment.get("fallback_mode", False),
            "selection_decision": selection_decision,
        },
        agent_id=assignment["agent_id"],
        task_hint=task_hint,
        caused_by=caused_by or assignment_event_id,
    )


def observability_project_and_limit(context: BrainContext, kwargs: dict[str, Any]) -> tuple[str, int]:
    project_path = kwargs.get("project_path") or context.project_path
    limit = int(kwargs.get("limit", 5000) or 5000)
    if limit < 1 or limit > 50000:
        raise ValueError("limit must be between 1 and 50000")
    return project_path, limit


def filter_observability_events(
    events,
    *,
    workflow_id: str | None = None,
    task_id: str | None = None,
):
    if workflow_id is None and task_id is None:
        return events
    return [
        event
        for event in events
        if (
            workflow_id is None
            or event.payload.get("workflow_id") == workflow_id
            or event.payload.get("root_task_id") == workflow_id
            or event.payload.get("task_id") == workflow_id
        )
        and (task_id is None or event.payload.get("task_id") == task_id)
    ]


def merge_agent_metrics(base: dict[str, dict[str, Any]], delta: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not base:
        return delta
    merged: dict[str, dict[str, Any]] = {agent_id: dict(metrics) for agent_id, metrics in base.items()}
    for agent_id, delta_metrics in delta.items():
        metrics = merged.setdefault(agent_id, AgentPerformanceReducer().reduce([]).get(agent_id, {
            "agent_id": agent_id,
            "success_count": 0,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 0,
            "total_tasks": 0,
            "success_rate": 0.0,
            "failure_rate": 0.0,
            "blocked_rate": 0.0,
            "confidence": 0.0,
        }))
        for key in ["success_count", "failure_count", "blocked_count", "assigned_count"]:
            metrics[key] = int(metrics.get(key, 0)) + int(delta_metrics.get(key, 0))
        total_tasks = metrics["success_count"] + metrics["failure_count"] + metrics["blocked_count"]
        metrics["total_tasks"] = total_tasks
        denominator = max(1, total_tasks)
        metrics["success_rate"] = metrics["success_count"] / denominator
        metrics["failure_rate"] = metrics["failure_count"] / denominator
        metrics["blocked_rate"] = metrics["blocked_count"] / denominator
        from math import log

        metrics["confidence"] = min(1.0, log(total_tasks + 1) / log(50))
    return dict(sorted(merged.items()))


def bind_session_id(context: BrainContext, session_id: int | None) -> int:
    if session_id is not None:
        return session_id
    if context.active_session_id is None:
        raise ValueError("No active session is available")
    return context.active_session_id


def audit_tool_call(
    context: BrainContext,
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    project_path: str | Path,
    session_id: int,
) -> None:
    context.repository.append_event(
        project_path=project_path,
        session_id=session_id,
        type="tool_call",
        source="allbrain",
        payload={
            "tool_name": tool_name,
            "tool_args": tool_args,
            "timestamp": datetime_now_iso(),
            "session_id": session_id,
        },
    )


def datetime_now_iso() -> str:
    from datetime import datetime

    return datetime.now(timezone.utc).isoformat()


def snapshot_to_dict(snapshot) -> dict[str, Any]:
    return snapshot.model_dump(mode="json")


def maybe_auto_snapshot(context: BrainContext, *, project_path: str | Path) -> None:
    project = context.repository.get_project_by_path(project_path)
    if project is None or project.id is None:
        return
    snapshot_repo = SnapshotRepo(context.repository.engine)
    latest = snapshot_repo.get_latest(project.id)
    event_cursor = latest.event_cursor if latest is not None else None
    events = context.repository.list_events_after(project_path=project_path, event_cursor=event_cursor)
    if snapshot_weight(events) < context.auto_snapshot_threshold:
        return
    all_events = context.repository.list_events(project_path=project_path, limit=50000)
    SnapshotEngine(SnapshotBuilder(include_derived=False), snapshot_repo).build_snapshot(project_id=project.id, events=all_events)


def semantic_event_count(events) -> int:
    return sum(1 for event in events if event.type != "tool_call")
