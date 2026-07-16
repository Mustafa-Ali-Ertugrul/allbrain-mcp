"""Operational helpers for multi-client AllBrain installs."""

from allbrain.ops.clients import (
    build_clients_report,
    format_clients_report,
    inspect_all_clients,
    inspect_client,
    kill_allbrain_processes,
    list_allbrain_processes,
)

__all__ = [
    "build_clients_report",
    "format_clients_report",
    "inspect_all_clients",
    "inspect_client",
    "kill_allbrain_processes",
    "list_allbrain_processes",
]
