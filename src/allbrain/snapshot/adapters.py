from __future__ import annotations

from allbrain.snapshot.engine import Snapshot
from allbrain.snapshot.versions import snapshot_versions


class SnapshotAdapter:
    def adapt(self, snapshot: Snapshot) -> Snapshot:
        schema_version = snapshot.metadata.get("snapshot_schema_version")
        if schema_version not in {"3.1", "4.0", "5.0", "6.0"}:
            return snapshot
        state = dict(snapshot.state)
        if schema_version == "3.1":
            state.setdefault("global_view", dict(snapshot.state))
            state.setdefault("agent_view", [])
            state.setdefault("conflict_view", {"conflicts": [], "count": 0})
            state.setdefault("decision_view", {"next_step": "Start next task", "required_action": "continue"})
        if schema_version == "4.0":
            state.setdefault("global_view", dict(snapshot.state.get("global_view", snapshot.state)))
            state.setdefault("agent_view", snapshot.state.get("agent_view", []))
            state.setdefault("conflict_view", snapshot.state.get("conflict_view", {"conflicts": [], "count": 0}))
            state.setdefault(
                "decision_view",
                snapshot.state.get("decision_view", {"next_step": "Start next task", "required_action": "continue"}),
            )
        state.setdefault("intent_view", {"intents": [], "active_intents": 0, "unique_agents": []})
        state.setdefault("intent_graph", {"nodes": {}, "edges": {}})
        state.setdefault("contradiction_view", {"contradictions": [], "count": 0})
        state.setdefault(
            "task_view",
            {
                "tasks": {},
                "dependencies": [],
                "handoffs": [],
                "agent_queue": {},
                "open_task_ids": [],
                "completed_task_ids": [],
            },
        )
        state.setdefault("task_graph", {"nodes": [], "edges": []})
        state.setdefault("assignment_view", {"agent_queue": {}})
        state.setdefault("handoff_view", {"handoffs": [], "count": 0})
        state.setdefault("agent_metrics", {})
        state.setdefault("task_outcomes", {})
        state.setdefault("scheduler_state", {})
        state.setdefault("goal", None)
        state.setdefault("working_files", [])
        state.setdefault("open_tasks", [])
        state.setdefault("open_task_refs", {})
        state.setdefault("completed_tasks", [])
        state.setdefault("blocked", [])
        state.setdefault("failures", [])
        state.setdefault("tool_usage", [])
        state.setdefault("last_event_id", None)
        state.setdefault("last_working_file", None)
        state.setdefault("event_count", 0)
        state.setdefault("git", {})
        metadata = (
            dict(snapshot.metadata) | snapshot_versions() | {"adapted_from_snapshot_schema_version": schema_version}
        )
        return snapshot.model_copy(update={"state": state, "metadata": metadata})
