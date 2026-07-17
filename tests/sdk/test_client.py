from __future__ import annotations

from types import SimpleNamespace

import pytest
from allbrain_sdk import (
    AllBrainClient,
    AllBrainProtocolError,
    AllBrainToolError,
    EventRecord,
)


class FakeMCPClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(self, name: str, arguments: dict[str, object]):
        self.calls.append((name, arguments))
        return self.responses.pop(0)


def response(data: object, *, is_error: bool = False):
    return SimpleNamespace(data=data, is_error=is_error, content=[])


@pytest.mark.asyncio
async def test_save_event_maps_friendly_arguments_and_validates_response() -> None:
    client = AllBrainClient(project=".", agent="code-agent", db_path="brain.db")
    fake = FakeMCPClient(
        [
            response(
                {
                    "ok": True,
                    "data": {
                        "id": "01900000-0000-7000-8000-000000000001",
                        "project_id": 1,
                        "session_id": 2,
                        "agent_id": "code-agent",
                        "type": "task_started",
                        "source": "agent",
                        "payload": {"task": "implement auth"},
                        "created_at": "2026-07-02T20:00:00Z",
                    },
                }
            )
        ]
    )
    client._client = fake  # type: ignore[assignment]

    event = await client.save_event("task_started", {"task": "implement auth"}, importance=4)

    assert event.agent_id == "code-agent"
    assert fake.calls == [
        (
            "save_event",
            {"type": "task_started", "payload": {"task": "implement auth"}, "importance": 4},
        )
    ]


@pytest.mark.asyncio
async def test_tool_error_becomes_typed_exception() -> None:
    client = AllBrainClient(project=".", agent="security-agent")
    client._client = FakeMCPClient([response({"ok": False, "error": "invalid event", "data": None})])  # type: ignore[assignment]

    with pytest.raises(AllBrainToolError, match="invalid event"):
        await client.save_event("not-valid", {})


@pytest.mark.asyncio
async def test_protocol_error_and_disconnected_client_are_explicit() -> None:
    client = AllBrainClient(project=".", agent="security-agent")
    with pytest.raises(AllBrainProtocolError, match="not connected"):
        await client.list_events()

    client._client = FakeMCPClient([response(None, is_error=True)])  # type: ignore[assignment]
    with pytest.raises(AllBrainProtocolError, match="MCP tool 'list_events' failed"):
        await client.list_events()


@pytest.mark.asyncio
async def test_create_task_returns_typed_result_with_queue() -> None:
    client = AllBrainClient(project=".", agent="code-agent")
    fake = FakeMCPClient(
        [
            response(
                {
                    "ok": True,
                    "data": {
                        "id": "ev-create-1",
                        "project_id": 1,
                        "session_id": 2,
                        "agent_id": "code-agent",
                        "type": "task_created",
                        "source": "allbrain",
                        "payload": {"task_id": "t-1", "goal": "implement auth"},
                        "created_at": "2026-07-17T09:00:00Z",
                        "queue": {"queue_item_id": "q-1", "state": "queued"},
                    },
                }
            )
        ]
    )
    client._client = fake  # type: ignore[assignment]
    result = await client.create_task("implement auth", enqueue=True, agent_id="code-agent")
    assert result.id == "ev-create-1"
    assert result.queue is not None
    assert result.queue["queue_item_id"] == "q-1"
    assert fake.calls[0][0] == "create_task"
    assert fake.calls[0][1]["enqueue"] is True
    assert fake.calls[0][1]["priority"] == 3


@pytest.mark.asyncio
async def test_assign_task_returns_event_decision_and_assignment() -> None:
    client = AllBrainClient(project=".", agent="code-agent")
    fake = FakeMCPClient(
        [
            response(
                {
                    "ok": True,
                    "data": {
                        "event": {
                            "id": "ev-assign",
                            "project_id": 1,
                            "session_id": 2,
                            "agent_id": "codex",
                            "type": "task_assigned",
                            "source": "allbrain",
                            "payload": {"task_id": "t-1", "agent_id": "codex"},
                            "created_at": "2026-07-17T09:01:00Z",
                        },
                        "decision_event": {
                            "id": "ev-decision",
                            "project_id": 1,
                            "session_id": 2,
                            "agent_id": "codex",
                            "type": "selection_decision",
                            "source": "allbrain",
                            "payload": {"task_id": "t-1"},
                            "created_at": "2026-07-17T09:01:01Z",
                        },
                        "assignment": {
                            "agent_id": "codex",
                            "score": 0.85,
                            "reason": "highest_score",
                            "breakdown": {"capability_score": 0.9},
                            "candidate_agents": [],
                        },
                    },
                }
            )
        ]
    )
    client._client = fake  # type: ignore[assignment]
    result = await client.assign_task("t-1")
    assert isinstance(result.event, EventRecord)
    assert result.event.id == "ev-assign"
    assert result.decision_event.id == "ev-decision"
    assert result.assignment.agent_id == "codex"
    assert result.assignment.score == 0.85
    assert fake.calls[0] == ("assign_task", {"task_id": "t-1", "limit": 5000})


@pytest.mark.asyncio
async def test_get_task_graph_returns_views() -> None:
    client = AllBrainClient(project=".", agent="code-agent")
    fake = FakeMCPClient(
        [
            response(
                {
                    "ok": True,
                    "data": {
                        "task_view": {"tasks": {"t-1": {"goal": "g"}}},
                        "task_graph": {"nodes": [], "edges": []},
                        "agent_state": {"codex": {"assigned_count": 1}},
                    },
                }
            )
        ]
    )
    client._client = fake  # type: ignore[assignment]
    result = await client.get_task_graph(limit=1000)
    assert result.task_view["tasks"]["t-1"]["goal"] == "g"
    assert result.agent_state["codex"]["assigned_count"] == 1
    assert fake.calls[0] == ("get_task_graph", {"limit": 1000})


@pytest.mark.asyncio
async def test_run_decision_pipeline_proxies_flags() -> None:
    client = AllBrainClient(project=".", agent="code-agent")
    fake = FakeMCPClient(
        [
            response(
                {
                    "ok": True,
                    "data": {
                        "run_id": "run-1",
                        "objective": {"goal": "ship v1"},
                        "decision": {"state": "DECISION"},
                        "stages": [{"name": "governance_precheck"}],
                    },
                }
            )
        ]
    )
    client._client = fake  # type: ignore[assignment]
    result = await client.run_decision_pipeline(
        {"goal": "ship v1"},
        enable_counterfactual=True,
        enable_foresight=True,
        foresight_limit=5,
    )
    assert result.run_id == "run-1"
    assert fake.calls[0][0] == "run_decision_pipeline"
    args = fake.calls[0][1]
    assert args["objective"] == {"goal": "ship v1"}
    assert args["enable_counterfactual"] is True
    assert args["enable_foresight"] is True
    # foresight_limit is a server-side param; keep default in client wrapper
    assert "foresight_limit" not in args


@pytest.mark.asyncio
async def test_get_context_pack_omits_nullables() -> None:
    client = AllBrainClient(project=".", agent="code-agent")
    fake = FakeMCPClient(
        [
            response(
                {
                    "ok": True,
                    "data": {
                        "project_resume": {"next_step": "review"},
                        "sessions": [],
                        "memory": [{"score": 0.8}],
                        "recent_events": [],
                    },
                }
            )
        ]
    )
    client._client = fake  # type: ignore[assignment]
    result = await client.get_context_pack(window_hours=48, top_k=10)
    assert result.project_resume["next_step"] == "review"
    assert result.memory[0]["score"] == 0.8
    args = fake.calls[0][1]
    assert args["window_hours"] == 48
    assert args["top_k"] == 10
    # Nullables should not appear when None
    assert "task_id" not in args
    assert "query" not in args


@pytest.mark.asyncio
async def test_detect_conflicts_passes_threshold() -> None:
    client = AllBrainClient(project=".", agent="code-agent")
    fake = FakeMCPClient([response({"ok": True, "data": {"conflicts": [{"id": "c1"}], "count": 1, "threshold": 0.8}})])
    client._client = fake  # type: ignore[assignment]
    result = await client.detect_conflicts(threshold=0.8, limit=1000)
    assert result.count == 1
    assert result.conflicts[0]["id"] == "c1"
    assert fake.calls[0] == ("detect_conflicts", {"limit": 1000, "threshold": 0.8})
