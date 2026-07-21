"""Deprecated compatibility shim for allbrain.domains.memory.memory.

Moved to allbrain.domains.memory.memory in v0.4.4.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.memory",
    submodules=(
        "memory_builder",
        "memory_domain_items",
        "memory_helpers",
        "memory_retriever",
        "semantic_memory",
        "workflow_memory_store",
    ),
)
