from __future__ import annotations

from types import SimpleNamespace

import pytest
from allbrain_sdk import (
    AllBrainClient,
    AllBrainProtocolError,
    AllBrainToolError,
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
