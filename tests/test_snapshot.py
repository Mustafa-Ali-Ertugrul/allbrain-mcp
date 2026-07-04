from __future__ import annotations

import time
from pathlib import Path

from allbrain.compression import EventCompressor
from allbrain.resume import ResumeEngine
from allbrain.server import BrainContext
from allbrain.server.tools.events import save_event_impl
from allbrain.server.tools.snapshots import (
    create_snapshot_impl,
    resume_project_impl,
)
from allbrain.snapshot import SnapshotCompactor
from allbrain.snapshot.versions import snapshot_versions
from allbrain.storage import BrainRepository, SnapshotRepo
from tests._helpers import make_context_from_repo, make_repo


def seed_events(context: BrainContext, count: int) -> None:
    for index in range(count):
        if index % 10 == 0:
            result = save_event_impl(context, type="failure", payload={"error": "Repeated failure"})
        elif index % 4 == 0:
            result = save_event_impl(context, type="task_started", payload={"task": f"Task {index % 7}"})
        elif index % 4 == 1:
            result = save_event_impl(context, type="task_completed", payload={"task": f"Task {index % 7}"})
        else:
            result = save_event_impl(
                context,
                type="file_modified",
                payload={"index": index},
                file_path=f"module_{index % 13}.py",
            )
        assert result.ok, result.error


def seed_raw_file_events(repo: BrainRepository, project_root: Path, count: int) -> None:
    session = repo.create_session(project_root, "seeder")
    for index in range(count):
        repo.append_event(
            project_path=project_root,
            session_id=session.id or 0,
            type="file_modified",
            source="test",
            payload={"index": index},
            file_path=f"module_{index % 100}.py",
        )


def comparable_resume(data: dict) -> dict:
    return {
        key: data[key]
        for key in [
            "goal",
            "working_files",
            "open_tasks",
            "completed",
            "blocked",
            "failures",
            "tool_usage",
            "next_step",
            "event_count",
            "last_event_id",
        ]
    }


def test_snapshot_correctness_matches_full_replay_for_500_events(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    seed_events(context, 500)

    snapshot_result = create_snapshot_impl(context, force=True, limit=5000)
    events_after_snapshot = repo.list_events(project_path=project_root, limit=5000)
    full_data = ResumeEngine().resume(events=events_after_snapshot, project_path=str(project_root), include_git=False)
    incremental = resume_project_impl(context, include_git=False, use_snapshot=True, limit=5000)

    assert snapshot_result.ok
    assert incremental.ok
    assert incremental.data["snapshot_used"] is True
    assert comparable_resume(incremental.data) == comparable_resume(full_data)


def test_compression_safety_collapses_file_churn_and_groups_failure_metadata(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    for _ in range(5):
        assert save_event_impl(context, type="file_modified", payload={}, file_path="auth.py").ok
    for _ in range(3):
        assert save_event_impl(context, type="failure", payload={"error": "same"}).ok

    events = repo.list_events(project_path=project_root, limit=100)
    compressed = EventCompressor().compress(events)
    snapshot_result = create_snapshot_impl(context, force=True, limit=100)

    assert snapshot_result.ok
    for key, value in snapshot_versions().items():
        assert snapshot_result.data["metadata"][key] == value
    assert len([event for event in compressed if event.type == "file_modified"]) == 1
    assert snapshot_result.data["metadata"]["repeated_failures"] == [{"payload": {"error": "same"}, "count": 3}]
    assert snapshot_result.data["metadata"]["snapshot_profile"] == "core"
    assert snapshot_result.data["metadata"]["derived_layers_included"] is False


def test_compression_is_idempotent_and_deterministic(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    for index in range(10):
        assert save_event_impl(context, type="file_modified", payload={"index": index}, file_path="auth.py").ok
    assert save_event_impl(context, type="failure", payload={"error": "same"}).ok

    events = repo.list_events(project_path=project_root, limit=100)
    compressor = EventCompressor()
    once = compressor.compress(events)
    twice = compressor.compress(once)

    assert [event.id for event in once] == [event.id for event in twice]


def test_incremental_resume_applies_delta_after_snapshot_cursor(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    seed_events(context, 40)
    snapshot_result = create_snapshot_impl(context, force=True, limit=500)
    assert snapshot_result.ok

    assert save_event_impl(context, type="task_started", payload={"task": "Delta task"}).ok
    incremental = resume_project_impl(context, include_git=False, use_snapshot=True, limit=500)

    assert incremental.ok
    assert incremental.data["snapshot_used"] is True
    assert incremental.data["snapshot_cursor"] == snapshot_result.data["event_cursor"]
    assert incremental.data["delta_event_count"] == 3
    assert "Delta task" in incremental.data["open_tasks"]


def test_agent_switch_uses_snapshot_for_context_reconstruction(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    codex = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    seed_events(codex, 100)
    snapshot_result = create_snapshot_impl(codex, force=True, limit=1000)
    assert snapshot_result.ok

    claude = make_context_from_repo(repo, project_root, "claude", auto_snapshot_threshold=10_000)
    resumed = resume_project_impl(claude, include_git=False, use_snapshot=True, limit=1000)

    assert resumed.ok
    assert resumed.data["snapshot_used"] is True
    assert resumed.data["event_count"] == 201
    assert resumed.data["snapshot_cursor"] == snapshot_result.data["event_cursor"]


def test_auto_snapshot_trigger_uses_weighted_event_score(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(
        repo, project_root, "codex", auto_snapshot_threshold=100, snapshot_check_interval=1
    )
    for index in range(13):
        assert save_event_impl(context, type="failure", payload={"error": f"failure-{index}"}).ok
    project = repo.get_project_by_path(project_root)
    assert project is not None

    latest = SnapshotRepo(repo.engine).get_latest(project.id or 0)

    assert latest is not None
    assert latest.metadata["raw_event_count"] == 26


def test_snapshot_delta_rebuild_equals_full_replay(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    seed_events(context, 120)
    snapshot_result = create_snapshot_impl(context, force=True, limit=1000)
    assert snapshot_result.ok
    assert save_event_impl(context, type="task_started", payload={"task": "After snapshot"}).ok
    assert save_event_impl(context, type="file_modified", payload={}, file_path="after.py").ok

    events = repo.list_events(project_path=project_root, limit=1000)
    full = ResumeEngine().resume(events=events, project_path=str(project_root), include_git=False)
    incremental = resume_project_impl(context, include_git=False, use_snapshot=True, limit=1000)

    assert incremental.ok
    assert comparable_resume(incremental.data) == comparable_resume(full)


def test_incompatible_snapshot_falls_back_to_full_replay(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    seed_events(context, 20)
    snapshot_result = create_snapshot_impl(context, force=True, limit=100)
    assert snapshot_result.ok

    project = repo.get_project_by_path(project_root)
    assert project is not None
    SnapshotRepo(repo.engine).save(
        project_id=project.id or 0,
        event_cursor=snapshot_result.data["event_cursor"],
        state=snapshot_result.data["state"],
        metadata={"reducer_version": "old", "compression_version": "old", "snapshot_schema_version": "old"},
    )

    resumed = resume_project_impl(context, include_git=False, use_snapshot=True, limit=100)

    assert resumed.ok
    assert resumed.data["snapshot_used"] is False
    assert resumed.data["snapshot_rebuild_required"] is True


def test_v6_snapshot_adapter_adds_scheduler_defaults(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    seed_events(context, 5)
    project = repo.get_project_by_path(project_root)
    assert project is not None
    SnapshotRepo(repo.engine).save(
        project_id=project.id or 0,
        event_cursor=None,
        state={
            "global_view": {},
            "task_view": {
                "tasks": {},
                "dependencies": [],
                "handoffs": [],
                "agent_queue": {},
                "open_task_ids": [],
                "completed_task_ids": [],
            },
        },
        metadata={"snapshot_schema_version": "6.0", "reducer_version": "6.0", "compression_version": "1.1"},
    )

    resumed = resume_project_impl(context, include_git=False, use_snapshot=True, limit=100)

    assert resumed.ok
    assert resumed.data["snapshot_used"] is True


def test_snapshot_compaction_creates_checkpoint_from_latest_snapshot(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    seed_events(context, 30)
    snapshot_result = create_snapshot_impl(context, force=True, limit=100)
    assert snapshot_result.ok

    project = repo.get_project_by_path(project_root)
    assert project is not None
    compacted = SnapshotCompactor(SnapshotRepo(repo.engine)).compact_latest(project.id or 0)

    assert compacted is not None
    assert compacted.event_cursor == snapshot_result.data["event_cursor"]
    assert compacted.metadata["compacted_from_snapshot_id"] == snapshot_result.data["id"]


def test_snapshot_resume_10k_events_under_50ms(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=100_000)
    seed_raw_file_events(repo, project_root, 10_000)
    snapshot_result = create_snapshot_impl(context, force=True, limit=25_000)
    assert snapshot_result.ok

    started = time.perf_counter()
    resumed = resume_project_impl(context, include_git=False, use_snapshot=True, limit=25_000)
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert resumed.ok
    assert resumed.data["snapshot_used"] is True
    assert resumed.data["delta_event_count"] == 1
    assert elapsed_ms < 50


def test_snapshot_can_include_derived_layers_on_demand(tmp_path: Path) -> None:
    repo, project_root = make_repo(tmp_path)
    context = make_context_from_repo(repo, project_root, "codex", auto_snapshot_threshold=10_000)
    assert save_event_impl(context, type="task_started", payload={"task": "JWT"}, file_path="auth.py").ok

    snapshot_result = create_snapshot_impl(context, force=True, include_derived=True, limit=100)

    assert snapshot_result.ok
    assert snapshot_result.data["metadata"]["snapshot_profile"] == "full"
    assert snapshot_result.data["metadata"]["derived_layers_included"] is True
    assert snapshot_result.data["state"]["intent_view"]["active_intents"] == 1
