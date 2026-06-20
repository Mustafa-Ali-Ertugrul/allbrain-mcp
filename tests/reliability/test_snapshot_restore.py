from __future__ import annotations

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.snapshot import GraphSnapshotBuilder, SnapshotManager, WorkflowSnapshotBuilder
from tests.test_sprint12_memory_policy_ui import events, make_context, save_event_impl


def seed(context) -> list[EventRead]:
    assert save_event_impl(context, type=EventType.TASK_CREATED.value, payload={"task_id": "t1", "workflow_id": "wf1", "goal": "Build"}).ok
    assert save_event_impl(context, type=EventType.TASK_ASSIGNED.value, payload={"task_id": "t1", "workflow_id": "wf1", "agent_id": "builder"}).ok
    return events(context)


def test_workflow_snapshot_restore_matches_full_replay(tmp_path) -> None:
    context = make_context(tmp_path)
    all_events = seed(context)
    snapshot = WorkflowSnapshotBuilder().build(all_events)

    restored = SnapshotManager().restore_workflow(snapshot_state=snapshot, remaining_events=[])

    assert restored["snapshot_hit"] is True
    assert restored["workflow_state"] == snapshot["workflow_state"]


def test_graph_snapshot_restore_matches_full_graph(tmp_path) -> None:
    context = make_context(tmp_path)
    all_events = seed(context)
    snapshot = GraphSnapshotBuilder().build(all_events)

    restored = SnapshotManager().restore_graph(snapshot_state=snapshot, remaining_events=[])

    assert restored["graph"] == snapshot["graph"]
