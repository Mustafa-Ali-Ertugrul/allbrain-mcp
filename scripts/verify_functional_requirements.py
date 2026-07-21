"""Functional verification test runner for allbrain-mcp v1.0.

Verifies:
1. MCP Tool Completeness (all 51 registered tools)
2. Decision Pipeline E2E (Preparation -> Reasoning -> Feedback -> Learning)
3. Conflict Resolution (ConflictDetector + ConflictResolver multi-agent flow)
4. Event Sourcing (Append -> Replay -> Snapshot -> Restore)
5. Session Management (Start -> Claim -> Renew -> Close)
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastmcp import FastMCP  # noqa: E402

from allbrain.server.tools import register_all_tools  # noqa: E402
from tests._helpers import make_context  # noqa: E402


def test_mcp_tool_completeness() -> dict[str, Any]:
    """Verify all 51 MCP tools are registered and match the documented tool inventory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        context = make_context(Path(tmpdir))
        mcp = FastMCP("QA-Test")
        register_all_tools(mcp, context, tool_profile="full")

        async def _get_tools():
            return await mcp.list_tools()

        tools = asyncio.run(_get_tools())
        tool_names = sorted(t.name for t in tools)
        context.repository.close()
        return {
            "total_count": len(tool_names),
            "expected_count": 51,
            "passed": len(tool_names) == 51,
            "tools": tool_names,
        }


def test_decision_pipeline_e2e() -> dict[str, Any]:
    """Verify 4-step decision pipeline: Preparation -> Reasoning -> Feedback -> Learning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        context = make_context(Path(tmpdir))

        from allbrain.server.tools.events import list_events_impl, save_event_impl
        from allbrain.server.tools.orchestrator import run_decision_pipeline_impl

        # 1. Preparation: Seed initial task and environmental context
        save_event_impl(
            context,
            type="task_created",
            payload={"task_id": "task-db-opt", "goal": "Optimize concurrent write latency"},
        )
        save_event_impl(
            context,
            type="decision_made",
            payload={
                "decision_id": "dec-db-001",
                "goal": "Optimize concurrent write latency",
                "selected_plan": "Add composite index on project_id and stream_position",
                "confidence": 0.88,
            },
        )

        baseline_listed = list_events_impl(context, limit=50)
        baseline_events = (
            baseline_listed.data.get("events", []) if isinstance(baseline_listed.data, dict) else baseline_listed.data
        ) or []
        baseline_count = len(baseline_events)

        # 2. Reasoning: Run multi-stage decision pipeline (counterfactual, scenarios, foresight, uncertainty)
        res = run_decision_pipeline_impl(
            context,
            objective={"goal": "Optimize concurrent write latency", "reason": "high write contention"},
            enable_counterfactual=True,
            enable_scenarios=True,
            enable_foresight=True,
            enable_uncertainty=True,
            enable_meta_reasoning=True,
        )

        # 3. Feedback & Learning: Verify recorded decision/reasoning events strictly created by this pipeline run
        post_listed = list_events_impl(context, limit=100)
        all_post_events = (
            post_listed.data.get("events", []) if isinstance(post_listed.data, dict) else post_listed.data
        ) or []
        # Slice only new events produced after baseline
        pipeline_new_events = all_post_events[baseline_count:]
        pipeline_event_types = [
            e.get("type") if isinstance(e, dict) else getattr(e, "type", "") for e in pipeline_new_events
        ]

        context.repository.close()
        has_post_pipeline_reasoning = any(
            "world" in t or "decision" in t or "scenario" in t or "foresight" in t for t in pipeline_event_types
        )
        return {
            "pipeline_ok": res.ok,
            "pipeline_data": res.data is not None,
            "event_count": len(pipeline_new_events),
            "event_types": pipeline_event_types,
            "passed": res.ok and has_post_pipeline_reasoning and len(pipeline_new_events) > 0,
        }


def test_conflict_resolution() -> dict[str, Any]:
    """Verify ConflictDetector and ConflictResolver in multi-agent workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        context = make_context(Path(tmpdir))

        from allbrain.server.tools.conflicts import detect_conflicts_impl, resolve_conflicts_impl
        from allbrain.server.tools.events import save_event_impl

        # Two agents modifying the same file with different intent
        save_event_impl(
            context,
            type="file_modified",
            agent_id="agent-alpha",
            file_path="src/config.py",
            payload={"change": "use Redis for caching", "strategy": "redis", "reason": "cache setup"},
        )
        save_event_impl(
            context,
            type="file_modified",
            agent_id="agent-beta",
            file_path="src/config.py",
            payload={"change": "use Memcached for caching", "strategy": "memcached", "reason": "cache setup"},
        )

        detect_res = detect_conflicts_impl(context, threshold=0.1)
        resolve_res = resolve_conflicts_impl(context, threshold=0.1)

        context.repository.close()
        return {
            "detect_ok": detect_res.ok,
            "detect_data": detect_res.data,
            "resolve_ok": resolve_res.ok,
            "resolve_data": resolve_res.data,
            "passed": detect_res.ok and resolve_res.ok,
        }


def test_event_sourcing_and_snapshots() -> dict[str, Any]:
    """Verify Event Sourcing (Append -> Replay -> Snapshot -> Restore)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        context = make_context(Path(tmpdir))

        from allbrain.server.tools.events import list_events_impl, save_event_impl
        from allbrain.server.tools.snapshots import create_snapshot_impl, resume_project_impl

        # Append events across multiple types
        for i in range(10):
            save_event_impl(
                context,
                type="task_created" if i % 2 == 0 else "tool_call",
                payload={"seq": i, "goal": f"Task goal {i}", "reason": "event sourcing verification"},
            )

        listed = list_events_impl(context, limit=50)
        events_before = (listed.data.get("events", []) if isinstance(listed.data, dict) else listed.data) or []

        # Generate Snapshot
        snap_res = create_snapshot_impl(context, force=True, include_derived=True)

        # Restore from Snapshot / Resume Project
        resume_res = resume_project_impl(context, detail="full", use_snapshot=True)

        context.repository.close()
        return {
            "append_count": len(events_before),
            "snapshot_ok": snap_res.ok,
            "snapshot_data": snap_res.data is not None,
            "resume_ok": resume_res.ok,
            "resume_data": resume_res.data is not None,
            "passed": len(events_before) >= 10 and snap_res.ok and resume_res.ok,
        }


def test_session_lifecycle() -> dict[str, Any]:
    """Verify Session lifecycle: Start -> Claim -> Renew -> Close."""
    with tempfile.TemporaryDirectory() as tmpdir:
        context = make_context(Path(tmpdir))

        from allbrain.server.queueing import QueueCoordinator
        from allbrain.server.tools.sessions import close_session_impl, summarize_sessions_impl
        from allbrain.server.tools.tasks import create_task_impl

        # 1. Create a task enqueued for workers
        created = create_task_impl(
            context,
            goal="Process data ingestion pipeline",
            kind="implementation",
            enqueue=True,
        )

        # 2. Worker claims task via QueueCoordinator
        coordinator = QueueCoordinator(context)
        claim_data = coordinator.claim(
            agent_id=context.agent_name,
            server_instance_id=context.server_instance_id,
            lease_ttl_seconds=60,
        )
        lease_id = claim_data.get("lease_id") if claim_data else None
        queue_item_id = claim_data.get("queue_item_id") if claim_data else None

        # 3. Renew lease
        renew_data = None
        if queue_item_id and lease_id:
            renew_data = coordinator.renew(
                queue_item_id=queue_item_id,
                lease_id=lease_id,
                server_instance_id=context.server_instance_id,
                lease_ttl_seconds=120,
            )

        # 4. Complete task
        complete_data = None
        if queue_item_id and lease_id:
            complete_data = coordinator.complete(
                queue_item_id=queue_item_id,
                lease_id=lease_id,
                server_instance_id=context.server_instance_id,
                output="Data ingestion completed successfully",
                artifacts=["data/output.parquet"],
            )

        # 5. Summarize and close session
        summary_res = summarize_sessions_impl(context)
        sessions = summary_res.data.get("sessions", []) if summary_res.data else []
        session_id = sessions[0]["id"] if sessions else context.active_session_id or 1

        close_res = close_session_impl(context, session_id=session_id, reason="completed")

        context.repository.close()
        passed = (
            created.ok
            and (claim_data is not None)
            and ("state" in str(renew_data) if renew_data else False)
            and ("state" in str(complete_data) if complete_data else False)
            and close_res.ok
        )
        return {
            "task_created": created.ok,
            "claim_ok": claim_data is not None and "lease_id" in claim_data,
            "renew_ok": renew_data is not None and "state" in str(renew_data),
            "complete_ok": complete_data is not None and "state" in str(complete_data),
            "close_ok": close_res.ok,
            "passed": passed,
        }


def main() -> int:
    print("=" * 60)
    print("  allbrain-mcp Functional Verification Suite")
    print("=" * 60)

    # 1. MCP Tools
    print("[1/5] Verifying MCP Tool Completeness...")
    t1 = test_mcp_tool_completeness()
    status_1 = "PASS" if t1["passed"] else "FAIL"
    print(f"  -> Count: {t1['total_count']}/51 tools registered [{status_1}]")

    # 2. Decision Pipeline
    print("[2/5] Verifying Decision Pipeline E2E...")
    t2 = test_decision_pipeline_e2e()
    status_2 = "PASS" if t2["passed"] else "FAIL"
    print(f"  -> Pipeline ok: {t2['pipeline_ok']}, Events: {t2['event_count']} [{status_2}]")

    # 3. Conflict Resolution
    print("[3/5] Verifying Conflict Resolution...")
    t3 = test_conflict_resolution()
    status_3 = "PASS" if t3["passed"] else "FAIL"
    print(f"  -> Detect ok: {t3['detect_ok']}, Resolve ok: {t3['resolve_ok']} [{status_3}]")

    # 4. Event Sourcing
    print("[4/5] Verifying Event Sourcing & Snapshot Restore...")
    t4 = test_event_sourcing_and_snapshots()
    status_4 = "PASS" if t4["passed"] else "FAIL"
    print(f"  -> Events: {t4['append_count']}, Snapshot: {t4['snapshot_ok']}, Resume: {t4['resume_ok']} [{status_4}]")

    # 5. Session Lifecycle
    print("[5/5] Verifying Session Management...")
    t5 = test_session_lifecycle()
    status_5 = "PASS" if t5["passed"] else "FAIL"
    print(f"  -> Create: {t5['task_created']}, Claim: {t5['claim_ok']}, Close: {t5['close_ok']} [{status_5}]")

    all_passed = all([t1["passed"], t2["passed"], t3["passed"], t4["passed"], t5["passed"]])
    print("=" * 60)
    print(f"  Overall Functional Verification: {'ALL PASS' if all_passed else 'SOME FAIL'}")
    print("=" * 60)
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
