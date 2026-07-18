from __future__ import annotations

import pytest
from allbrain_sdk import AllBrainClient
from test_client import FakeMCPClient


@pytest.mark.asyncio
async def test_resume_project_prompt_calls_prompt() -> None:
    client = AllBrainClient(project=".", agent="a")
    fake = FakeMCPClient()
    client._client = fake
    result = await client.resume_project_prompt(limit=3000)
    assert fake.prompt_calls == [("resume_project", {"limit": 3000})]
    assert result.name == "resume_project"


@pytest.mark.asyncio
async def test_task_handoff_prompt_without_reason() -> None:
    client = AllBrainClient(project=".", agent="a")
    fake = FakeMCPClient()
    client._client = fake
    await client.task_handoff_prompt("t-1", "codex")
    assert fake.prompt_calls == [("task_handoff", {"task_id": "t-1", "from_agent": "codex"})]


@pytest.mark.asyncio
async def test_task_handoff_prompt_with_reason() -> None:
    client = AllBrainClient(project=".", agent="a")
    fake = FakeMCPClient()
    client._client = fake
    await client.task_handoff_prompt("t-1", "codex", reason="stuck")
    assert fake.prompt_calls == [("task_handoff", {"task_id": "t-1", "from_agent": "codex", "reason": "stuck"})]


@pytest.mark.asyncio
async def test_investigate_conflict_prompt_uri() -> None:
    client = AllBrainClient(project=".", agent="a")
    fake = FakeMCPClient()
    client._client = fake
    await client.investigate_conflict_prompt(9)
    assert fake.prompt_calls == [("investigate_conflict", {"session_id": 9})]
