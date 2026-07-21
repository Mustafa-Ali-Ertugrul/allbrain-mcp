"""Deprecated compatibility shim for allbrain.domains.collaboration.agents.queues."""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.collaboration.agents.queues",
    submodules=("memory", "rabbitmq", "redis", "sqlite"),
)
