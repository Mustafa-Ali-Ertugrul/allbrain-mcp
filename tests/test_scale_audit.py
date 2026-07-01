from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from allbrain.events import EventType
from allbrain.server import BrainContext
from allbrain.server.app import create_snapshot_impl, orchestrate_project_impl, resume_project_impl
from tests._helpers import make_context


@dataclass(frozen=True)
class EventSpec:
    type: str
    payload: dict[str, Any]
    agent_id: str
    file_path: str | None = None


def build_scale_dataset() -> list[EventSpec]:
    agents = ["codex", "claude", "opencode"]
    owners = {f"task_{index:03d}": agents[index % len(agents)] for index in range(500)}
    specs: list[EventSpec] = []
    for index in range(500):
        task_id = f"task_{index:03d}"
        specs.append(
            EventSpec(
                type=EventType.TASK_CREATED.value,
                payload={
                    "task_id": task_id,
                    "goal": f"Scale task {index}",
                    "kind": "testing" if index % 5 == 0 else "implementation",
                    "related_files": [f"module_{index % 250}.py"],
                    "priority": (index % 5) + 1,
                },
                agent_id=owners[task_id],
            )
        )

    remaining = {
        "file": 4000,
        "lifecycle": 1500,
        "assignment": 2000,
        "handoff": 1000,
        "noise": 1000,
    }
    assignment_count = 0
    lifecycle_count = 0
    handoff_count = 0
    category_cycle = [
        "file",
        "file",
        "file",
        "file",
        "lifecycle",
        "lifecycle",
        "assignment",
        "assignment",
        "handoff",
        "noise",
    ]
    cursor = 0
    while sum(remaining.values()) > 0:
        category = category_cycle[cursor % len(category_cycle)]
        cursor += 1
        if remaining[category] == 0:
            continue
        index = len(specs)
        task_id = f"task_{index % 500:03d}"
        agent_id = owners[task_id]
        if category == "file":
            specs.append(
                EventSpec(
                    type=EventType.FILE_MODIFIED.value,
                    payload={"task_id": task_id, "index": index},
                    file_path=f"module_{index % 250}.py",
                    agent_id=agent_id,
                )
            )
        elif category == "lifecycle":
            specs.append(_lifecycle_event(task_id, agent_id, lifecycle_count))
            lifecycle_count += 1
        elif category == "assignment":
            if assignment_count < 100:
                next_agent = agents[(agents.index(agent_id) + 1) % len(agents)]
                owners[task_id] = next_agent
                agent_id = next_agent
            specs.append(
                EventSpec(
                    type=EventType.TASK_ASSIGNED.value,
                    payload={
                        "task_id": task_id,
                        "agent_id": owners[task_id],
                        "score": 80 + (assignment_count % 10),
                        "breakdown": {
                            "capability": 60,
                            "availability": 20,
                            "priority_bonus": assignment_count % 10,
                        },
                    },
                    agent_id=owners[task_id],
                )
            )
            assignment_count += 1
        elif category == "handoff":
            from_agent = owners[task_id]
            to_agent = agents[(agents.index(from_agent) + 1) % len(agents)]
            specs.append(
                EventSpec(
                    type=EventType.HANDOFF_CREATED.value,
                    payload={
                        "task_id": task_id,
                        "from_agent": from_agent,
                        "to_agent": to_agent,
                        "reason": "scale audit switch" if handoff_count < 50 else "scale audit handoff",
                    },
                    agent_id=from_agent,
                )
            )
            handoff_count += 1
        else:
            specs.append(
                EventSpec(
                    type=EventType.TOOL_CALL.value,
                    payload={"tool_name": "scale_noise", "tool_args": {"index": index}},
                    agent_id=agent_id,
                )
            )
        remaining[category] -= 1
    assert len(specs) == 10_000
    assert assignment_count == 2000
    assert handoff_count == 1000
    return specs


def _lifecycle_event(task_id: str, agent_id: str, index: int) -> EventSpec:
    if index < 500:
        return EventSpec(
            EventType.TASK_STARTED.value, {"task_id": task_id, "task": f"Scale task {index % 500}"}, agent_id
        )
    if index < 850:
        return EventSpec(EventType.TASK_BLOCKED.value, {"task_id": task_id, "reason": "scale blocked"}, agent_id)
    if index < 1200:
        return EventSpec(
            EventType.TASK_COMPLETED.value, {"task_id": task_id, "task": f"Scale task {index % 500}"}, agent_id
        )
    return EventSpec(EventType.TASK_FAILED.value, {"task_id": task_id, "reason": "scale failed"}, agent_id)


def append_specs(context: BrainContext, specs: list[EventSpec]) -> None:
    session_id = context.active_session_id or 0
    for spec in specs:
        context.repository.append_event(
            project_path=context.project_path,
            session_id=session_id,
            type=spec.type,
            source="scale_audit",
            payload=spec.payload,
            file_path=spec.file_path,
            agent_id=spec.agent_id,
        )


def test_audit2_scale_performance_baseline_and_snapshot_delta_determinism(tmp_path: Path, record_property) -> None:
    context = make_context(tmp_path, auto_snapshot_threshold=100_000)
    specs = build_scale_dataset()
    append_specs(context, specs[:9800])

    tracemalloc.start()
    snapshot_started = time.perf_counter()
    snapshot = create_snapshot_impl(context, force=True, limit=20_000)
    snapshot_build_time = (time.perf_counter() - snapshot_started) * 1000
    append_specs(context, specs[9800:])

    resume_started = time.perf_counter()
    resume = resume_project_impl(context, include_git=False, use_snapshot=True, limit=20_000)
    resume_time = (time.perf_counter() - resume_started) * 1000

    orchestrate_started = time.perf_counter()
    snapshot_delta = orchestrate_project_impl(context, include_git=False, use_snapshot=True, limit=20_000)
    orchestrate_time = (time.perf_counter() - orchestrate_started) * 1000

    full_replay = orchestrate_project_impl(context, include_git=False, use_snapshot=False, limit=20_000)
    _, memory_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    metrics = {
        "snapshot_build_time_ms": round(snapshot_build_time, 3),
        "resume_time_ms": round(resume_time, 3),
        "orchestrate_time_ms": round(orchestrate_time, 3),
        "memory_peak_bytes": memory_peak,
        "memory_peak_mb": round(memory_peak / (1024 * 1024), 3),
    }
    record_property("audit2_scale_metrics", metrics)
    print(f"AUDIT2_SCALE_BASELINE {metrics}")

    assert snapshot.ok, snapshot.error
    assert resume.ok, resume.error
    assert snapshot_delta.ok, snapshot_delta.error
    assert full_replay.ok, full_replay.error
    assert snapshot_delta.data["global_view"]["orchestrator_snapshot_used"] is True
    assert full_replay.data["global_view"]["orchestrator_snapshot_used"] is False
    assert snapshot_delta.data["task_view"] == full_replay.data["task_view"]
    assert snapshot_delta.data["task_graph"] == full_replay.data["task_graph"]
    assert snapshot_delta.data["assignment_view"] == full_replay.data["assignment_view"]
    assert snapshot_delta.data["handoff_view"] == full_replay.data["handoff_view"]
    assert snapshot_delta.data["decision_view"] == full_replay.data["decision_view"]
    assert snapshot_delta.data["agent_state"] == full_replay.data["agent_state"]
    assert snapshot_delta.data["scheduler_state"] == full_replay.data["scheduler_state"]
    assert metrics["snapshot_build_time_ms"] > 0
    assert metrics["resume_time_ms"] > 0
    assert metrics["orchestrate_time_ms"] > 0
    assert metrics["memory_peak_bytes"] > 0
