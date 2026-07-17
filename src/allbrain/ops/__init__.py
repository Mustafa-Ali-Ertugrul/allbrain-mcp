"""Operational helpers for multi-client AllBrain installs."""

from allbrain.ops.clients import (
    agent_event_freshness,
    build_clients_report,
    format_clients_report,
    inspect_all_clients,
    inspect_client,
    kill_allbrain_processes,
    list_allbrain_processes,
)
from allbrain.ops.inventory import (
    PROMPT_INVENTORY,
    RESOURCE_INVENTORY,
    build_prompt_inventory,
    build_resource_inventory,
)

__all__ = [
    "PROMPT_INVENTORY",
    "RESOURCE_INVENTORY",
    "agent_event_freshness",
    "build_clients_report",
    "build_prompt_inventory",
    "build_resource_inventory",
    "format_clients_report",
    "inspect_all_clients",
    "inspect_client",
    "kill_allbrain_processes",
    "list_allbrain_processes",
]
