"""Deprecated compatibility shim for allbrain.domains.collaboration.agents.

Moved to allbrain.domains.collaboration.agents in v0.4.5.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.collaboration.agents",
    submodules=(
        "adapter",
        "adapters",
        "adapters.mock",
        "definition",
        "learner",
        "metrics",
        "queue",
        "queues",
        "queues.memory",
        "queues.rabbitmq",
        "queues.redis",
        "queues.sqlite",
        "registry",
        "runtime",
        "safety",
        "worker",
    ),
)
