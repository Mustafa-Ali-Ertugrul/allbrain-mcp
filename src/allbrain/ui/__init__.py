"""Deprecated compatibility shim for allbrain.domains.memory.ui.

Moved to allbrain.domains.memory.ui in v0.4.4.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.ui",
    submodules=("dashboard_server", "graph_explorer", "metrics_dashboard", "replay_viewer", "trace_viewer"),
)
