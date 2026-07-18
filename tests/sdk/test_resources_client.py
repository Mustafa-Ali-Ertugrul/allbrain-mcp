from __future__ import annotations

import pytest
from allbrain_sdk import AllBrainClient
from test_client import FakeMCPClient


@pytest.mark.asyncio
async def test_project_resume_raw_uri() -> None:
    client = AllBrainClient(project=".", agent="a")
    fake = FakeMCPClient()
    client._client = fake
    await client.project_resume_raw()
    assert fake.resource_calls == ["project://resume"]


@pytest.mark.asyncio
async def test_tasks_graph_raw_uri() -> None:
    client = AllBrainClient(project=".", agent="a")
    fake = FakeMCPClient()
    client._client = fake
    await client.tasks_graph_raw()
    assert fake.resource_calls == ["tasks://graph"]


@pytest.mark.asyncio
async def test_git_fingerprint_raw_uri() -> None:
    client = AllBrainClient(project=".", agent="a")
    fake = FakeMCPClient()
    client._client = fake
    await client.git_fingerprint_raw()
    assert fake.resource_calls == ["git://fingerprint"]


@pytest.mark.asyncio
async def test_session_summary_uri() -> None:
    client = AllBrainClient(project=".", agent="a")
    fake = FakeMCPClient()
    client._client = fake
    await client.session_summary(12)
    assert fake.resource_calls == ["session://12/summary"]


@pytest.mark.asyncio
async def test_event_by_id_uri() -> None:
    client = AllBrainClient(project=".", agent="a")
    fake = FakeMCPClient()
    client._client = fake
    await client.event_by_id("ev-9")
    assert fake.resource_calls == ["event://ev-9"]
