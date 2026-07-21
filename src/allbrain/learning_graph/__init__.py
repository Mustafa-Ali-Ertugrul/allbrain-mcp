"""Deprecated compatibility shim for allbrain.learning_graph.

Moved to allbrain.domains.learning.learning_graph in v0.4.2.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.learning.learning_graph",
    submodules=(
        "graph", "model", "node", "rewriter"
    ),
)