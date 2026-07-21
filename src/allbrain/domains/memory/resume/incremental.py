from __future__ import annotations

from typing import Any

from allbrain.core import StateEngine
from allbrain.domains.analysis.context import ContextBuilder
from allbrain.domains.memory.resume.engine import ResumeEngine
from allbrain.domains.memory.resume.protocols import EventRepository, SnapshotStore
from allbrain.models.schemas import EventRead
from allbrain.snapshot.adapters import SnapshotAdapter
from allbrain.snapshot.versions import is_compatible


class IncrementalResumeEngine:
    def __init__(
        self,
        repository: EventRepository,
        snapshot_repo: SnapshotStore,
        context_builder: ContextBuilder | None = None,
        state_engine: StateEngine | None = None,
        resume_engine: ResumeEngine | None = None,
    ):
        self.repository = repository
        self.snapshot_repo = snapshot_repo
        self.context_builder = context_builder or ContextBuilder()
        self.state_engine = state_engine or StateEngine()
        self.resume_engine = resume_engine or ResumeEngine(
            context_builder=self.context_builder,
            state_engine=self.state_engine,
        )

    def resume(
        self,
        *,
        project_path: str,
        project_id: int,
        events: list[EventRead] | None = None,
        limit: int = 5000,
        include_git: bool = True,
        use_snapshot: bool = True,
    ) -> dict[str, Any]:
        events = events or []
        if not use_snapshot:
            if not events:
                events = self.repository.list_events(project_path=project_path, limit=limit)
            result = self.resume_engine.resume(events=events, project_path=project_path, include_git=include_git)
            result.update({"snapshot_used": False, "snapshot_cursor": None, "delta_event_count": len(events)})
            return result

        snapshot = self.snapshot_repo.get_latest(project_id)
        if snapshot is not None:
            snapshot = SnapshotAdapter().adapt(snapshot)
        if snapshot is None or not is_compatible(snapshot.metadata):
            if not events:
                events = self.repository.list_events(project_path=project_path, limit=limit)
            result = self.resume_engine.resume(events=events, project_path=project_path, include_git=include_git)
            result.update(
                {
                    "snapshot_used": False,
                    "snapshot_cursor": snapshot.event_cursor if snapshot is not None else None,
                    "delta_event_count": len(events),
                    "snapshot_rebuild_required": snapshot is not None,
                }
            )
            return result

        delta_events = self.repository.list_events_after(
            project_path=project_path,
            event_cursor=snapshot.event_cursor,
        )
        git_context = self.context_builder.build(events=[], project_path=project_path, include_git=include_git)["git"]
        state = self.state_engine.apply_events(snapshot.state, delta_events, git=git_context)
        result = self.resume_engine.response_from_state(state)
        result.update(
            {
                "snapshot_used": True,
                "snapshot_cursor": snapshot.event_cursor,
                "delta_event_count": len(delta_events),
                "snapshot_rebuild_required": False,
            }
        )
        return result
