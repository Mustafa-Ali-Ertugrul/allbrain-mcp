"""Deprecated compatibility shim for allbrain.graph.

Moved to allbrain.domains.analysis.graph in v0.4.1.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.analysis.graph",
    submodules=(
        "graph_query_engine",
        "state_graph",
        "workflow_graph_builder",
    ),
)
