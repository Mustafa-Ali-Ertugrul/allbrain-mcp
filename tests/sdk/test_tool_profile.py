from __future__ import annotations

import pytest
from allbrain_sdk import AllBrainClient, AllBrainConfig
from allbrain_sdk.models import ToolProfile
from pydantic import ValidationError

PROFILES: tuple[ToolProfile, ...] = (
    "minimal",
    "memory",
    "collaboration",
    "reasoning",
    "core",
    "full",
)


@pytest.mark.parametrize("profile", PROFILES)
def test_allbrain_config_accepts_server_profiles(profile: ToolProfile) -> None:
    config = AllBrainConfig(agent="agent-a", tool_profile=profile)
    assert config.tool_profile == profile


@pytest.mark.parametrize("profile", PROFILES)
def test_client_accepts_server_profiles(profile: ToolProfile) -> None:
    client = AllBrainClient(agent="agent-a", tool_profile=profile)
    assert client.config.tool_profile == profile


def test_invalid_tool_profile_rejected() -> None:
    with pytest.raises(ValidationError):
        AllBrainConfig(agent="agent-a", tool_profile="everything")  # type: ignore[arg-type]
