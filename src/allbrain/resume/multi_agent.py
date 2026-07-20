from __future__ import annotations

from typing import Any

from allbrain.conflict import ConflictDetector, ConflictResolver
from allbrain.core import StateEngine
from allbrain.domains.analysis.context import ParallelContextBuilder
from allbrain.merge import EventMergeEngine
from allbrain.models.schemas import EventRead
from allbrain.resume.incremental import IncrementalResumeEngine


class MultiAgentResumeEngine:
    def __init__(
        self,
        incremental_engine: IncrementalResumeEngine,
        detector: ConflictDetector | None = None,
        resolver: ConflictResolver | None = None,
        parallel_builder: ParallelContextBuilder | None = None,
        merge_engine: EventMergeEngine | None = None,
    ):
        self.incremental_engine = incremental_engine
        self.detector = detector or ConflictDetector()
        self.resolver = resolver or ConflictResolver()
        self.parallel_builder = parallel_builder or ParallelContextBuilder()
        self.merge_engine = merge_engine or EventMergeEngine()
        self.state_engine = StateEngine()

    def resume(
        self,
        *,
        project_path: str,
        project_id: int,
        events: list[EventRead],
        limit: int,
        include_git: bool,
        use_snapshot: bool,
        threshold: float = 0.7,
    ) -> dict[str, Any]:
        global_state = self.incremental_engine.resume(
            project_path=project_path,
            project_id=project_id,
            events=None if use_snapshot else events,
            limit=limit,
            include_git=include_git,
            use_snapshot=use_snapshot,
        )
        agent_view = self.parallel_builder.build_agent_view(events)
        conflicts = self.detector.detect(events, threshold=threshold)
        resolved = self.resolver.resolve(conflicts, events, agent_view)
        merged_events = self.merge_engine.merge(events, resolved)
        merged_state = self.state_engine.build_state({"events": merged_events, "git": global_state.get("git", {})})
        decision_view = self._decision_view(global_state=global_state, conflicts=conflicts, resolved=resolved)
        layered = {
            "global_view": global_state,
            "agent_view": agent_view,
            "conflict_view": {"conflicts": conflicts, "count": len(conflicts)},
            "decision_view": decision_view,
            "merged_state": merged_state,
            "resolved_conflicts": resolved,
        }
        return global_state | {"next_step": decision_view["next_step"]} | layered

    def _decision_view(
        self, *, global_state: dict[str, Any], conflicts: list[dict[str, Any]], resolved: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if conflicts:
            first = conflicts[0]
            target = first.get("file") or first.get("task") or first["level"]
            unresolved = [item for item in resolved if item.get("status") != "resolved"]
            return {
                "next_step": f"resolve conflict in {target}",
                "required_action": "manual_conflict_review" if unresolved else "resolve_conflict",
                "resolved_conflicts": resolved,
                "confidence": 0.45 if unresolved else 0.7,
            }
        return {
            "next_step": global_state.get("next_step", "Start next task"),
            "required_action": "continue",
            "resolved_conflicts": resolved,
            "confidence": 1.0,
        }
