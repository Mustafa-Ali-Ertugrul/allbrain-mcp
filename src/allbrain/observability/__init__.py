"""Deprecated compatibility shim for allbrain.domains.memory.observability.

Moved to allbrain.domains.memory.observability in v0.4.4.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.observability",
    submodules=("dashboard", "dashboard_data_builder", "exporter", "span", "tracer"),
)
