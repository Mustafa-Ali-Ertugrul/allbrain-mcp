from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from allbrain.compression import EventCompressor
from allbrain.conflict import ConflictDetector, ConflictResolver
from allbrain.context import ParallelContextBuilder
from allbrain.contradiction import ContradictionDetector
from allbrain.core import StateEngine
from allbrain.domains.reasoning.intent import IntentExtractor, IntentStore
from allbrain.merge import EventMergeEngine
from allbrain.models.schemas import EventRead
from allbrain.orchestrator import TaskGraphBuilder, TaskStateReducer
from allbrain.orchestrator.metrics import AgentPerformanceReducer, TaskOutcomeReducer
from allbrain.orchestrator.state import AgentStateBuilder
from allbrain.resume.orchestrated import OrchestratedResumeEngine
from allbrain.snapshot.versions import snapshot_versions


@dataclass(frozen=True)
class EventStreamBuffer:
    raw_events: list[EventRead]
    compressed_events: list[EventRead]


class CoreStateSnapshotBuilder:
    def __init__(self, state_engine: StateEngine | None = None):
        self.state_engine = state_engine or StateEngine()

    def build(self, buffer: EventStreamBuffer) -> dict[str, Any]:
        git = _latest_git_fingerprint(buffer.raw_events)
        state = self.state_engine.build_state({"events": buffer.compressed_events, "git": git})
        state["event_count"] = len(buffer.raw_events)
        state["global_view"] = dict(state)
        return state


class OrchestratorCacheBuilder:
    def __init__(self, task_reducer: TaskStateReducer | None = None):
        self.task_reducer = task_reducer or TaskStateReducer()
        self.metrics_reducer = AgentPerformanceReducer()
        self.outcome_reducer = TaskOutcomeReducer()
        self.agent_state_builder = AgentStateBuilder()

    def build(self, buffer: EventStreamBuffer, global_view: dict[str, Any]) -> dict[str, Any]:
        task_state = self.task_reducer.build(buffer.compressed_events)
        agent_metrics = self.metrics_reducer.reduce(buffer.compressed_events)
        task_outcomes = self.outcome_reducer.reduce(buffer.compressed_events)
        task_graph = TaskGraphBuilder().build(task_state)
        orchestrated = OrchestratedResumeEngine(task_reducer=self.task_reducer).build_from_task_state(
            task_state=task_state,
            base=global_view,
            events=buffer.compressed_events,
            metrics=agent_metrics,
        )
        agent_state = self.agent_state_builder.build(metrics=agent_metrics, task_state=task_state)
        return {
            "task_view": task_state,
            "task_graph": task_graph,
            "assignment_view": orchestrated["assignment_view"],
            "handoff_view": orchestrated["handoff_view"],
            "orchestrator_decision_view": orchestrated["decision_view"],
            "agent_metrics": agent_metrics,
            "task_outcomes": task_outcomes,
            "scheduler_state": {"agent_state": agent_state},
        }


class DerivedLayersBuilder:
    def __init__(self, state_engine: StateEngine | None = None):
        self.state_engine = state_engine or StateEngine()

    def build(self, buffer: EventStreamBuffer) -> dict[str, Any]:
        agent_view = ParallelContextBuilder(self.state_engine).build_agent_view(buffer.compressed_events)
        conflicts = ConflictDetector().detect(buffer.compressed_events)
        resolved_conflicts = ConflictResolver().resolve(conflicts, buffer.compressed_events, agent_view)
        merged_events = EventMergeEngine().merge(buffer.compressed_events, resolved_conflicts)
        merged_state = self.state_engine.build_state(
            {"events": merged_events, "git": _latest_git_fingerprint(buffer.raw_events)}
        )
        intents = IntentExtractor().extract(buffer.compressed_events)
        intent_graph = IntentStore().build_graph(intents, buffer.compressed_events)
        contradictions = ContradictionDetector().detect(intents)
        return {
            "agent_view": agent_view,
            "conflict_view": {"conflicts": conflicts, "count": len(conflicts)},
            "decision_view": {
                "next_step": f"resolve conflict in {conflicts[0].get('file') or conflicts[0].get('task')}"
                if conflicts
                else "continue",
                "required_action": "resolve_conflict" if conflicts else "continue",
                "resolved_conflicts": resolved_conflicts,
                "confidence": 0.7 if conflicts else 1.0,
            },
            "merged_state": merged_state,
            "resolved_conflicts": resolved_conflicts,
            "intent_view": {
                "intents": [intent.model_dump(mode="json") for intent in intents],
                "active_intents": len(intents),
                "unique_agents": sorted({intent.agent_id for intent in intents}),
            },
            "intent_graph": intent_graph.to_dict(),
            "contradiction_view": {"contradictions": contradictions, "count": len(contradictions)},
        }


class SnapshotBuilder:
    def __init__(
        self,
        compressor: EventCompressor | None = None,
        state_engine: StateEngine | None = None,
        *,
        include_derived: bool = False,
    ):
        self.compressor = compressor or EventCompressor()
        self.state_engine = state_engine or StateEngine()
        self.include_derived = include_derived
        self.core_builder = CoreStateSnapshotBuilder(self.state_engine)
        self.orchestrator_builder = OrchestratorCacheBuilder()
        self.derived_builder = DerivedLayersBuilder(self.state_engine)

    def build(self, events: list[EventRead]) -> tuple[dict[str, Any], dict[str, Any]]:
        compressed_events = self.compressor.compress(events)
        buffer = EventStreamBuffer(raw_events=events, compressed_events=compressed_events)
        state = self.core_builder.build(buffer)
        state.update(self._default_derived_layers())
        state.update(self.orchestrator_builder.build(buffer, state["global_view"]))
        if self.include_derived:
            state.update(self.derived_builder.build(buffer))
        metadata = (
            self.compressor.metadata(events, compressed_events)
            | snapshot_versions()
            | {
                "snapshot_profile": "full" if self.include_derived else "core",
                "derived_layers_included": self.include_derived,
            }
        )
        return state, metadata

    def _default_derived_layers(self) -> dict[str, Any]:
        return {
            "agent_view": [],
            "conflict_view": {"conflicts": [], "count": 0},
            "decision_view": {
                "next_step": "continue",
                "required_action": "continue",
                "resolved_conflicts": [],
                "confidence": 1.0,
            },
            "merged_state": {},
            "resolved_conflicts": [],
            "intent_view": {"intents": [], "active_intents": 0, "unique_agents": []},
            "intent_graph": {"nodes": {}, "edges": {}},
            "contradiction_view": {"contradictions": [], "count": 0},
        }


def _latest_git_fingerprint(events: list[EventRead]) -> dict[str, Any]:
    """Return the newest content-free Git fingerprint recorded by lifecycle events."""
    for event in reversed(events):
        if event.type not in {"session_started", "session_summary"}:
            continue
        git = event.payload.get("git")
        if isinstance(git, dict) and git:
            return dict(git)
    return {}

