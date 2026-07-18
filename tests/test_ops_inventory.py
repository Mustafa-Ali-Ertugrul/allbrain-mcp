"""Unit tests for ops inventory helpers and server-side verification."""

from __future__ import annotations

from allbrain.ops.inventory import (
    PROMPT_INVENTORY,
    RESOURCE_INVENTORY,
    build_prompt_inventory,
    build_resource_inventory,
    verify_inventory_against_server,
)
from tests.sdk.test_client import FakeMCPClient


def test_build_resource_inventory_returns_static_list() -> None:
    inventory = build_resource_inventory()
    assert inventory == RESOURCE_INVENTORY
    assert any(item["uri"] == "project://resume" for item in inventory)
    assert any(item["uri"] == "session://{session_id}/summary" for item in inventory)


def test_build_prompt_inventory_returns_static_list() -> None:
    inventory = build_prompt_inventory()
    assert inventory == PROMPT_INVENTORY
    assert any(item["name"] == "resume_project" for item in inventory)
    assert any(item["name"] == "task_handoff" for item in inventory)


def test_verify_inventory_matches_fake_client() -> None:
    client = FakeMCPClient([])
    report = verify_inventory_against_server(client)
    assert report["ok"] is True
    assert "project://resume" in report["resources"]["matched"]
    assert "resume_project" in report["prompts"]["matched"]
    assert report["resources"]["missing"] == []
    assert report["prompts"]["missing"] == []
    assert report["resources"]["extra"] == []
    assert report["prompts"]["extra"] == []


def test_verify_inventory_reports_missing_when_server_empty() -> None:
    client = FakeMCPClient([])

    async def empty_resources() -> list:
        return []

    client.list_resources = empty_resources  # type: ignore[assignment]
    client.list_resource_templates = empty_resources  # type: ignore[assignment]
    client.list_prompts = empty_resources  # type: ignore[assignment]

    report = verify_inventory_against_server(client)
    assert report["ok"] is False
    assert report["resources"]["missing"]
    assert report["prompts"]["missing"]
