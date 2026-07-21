"""Collaboration bounded context — multi-agent coordination.

Migrated in v0.4.5 from:
  allbrain.collaboration → allbrain.domains.collaboration.collaboration
  allbrain.conflict → allbrain.domains.collaboration.conflict
  allbrain.merge → allbrain.domains.collaboration.merge
  allbrain.arbitration → allbrain.domains.collaboration.arbitration
  allbrain.reputation → allbrain.domains.collaboration.reputation
  allbrain.distributed → allbrain.domains.collaboration.distributed
  allbrain.workflow → allbrain.domains.collaboration.workflow
  allbrain.workspace → allbrain.domains.collaboration.workspace
  allbrain.agents → allbrain.domains.collaboration.agents
  allbrain.routing → allbrain.domains.collaboration.routing

See docs/ARCHITECTURE.md for the full mapping.
"""

from __future__ import annotations

__all__ = [
    "agents",
    "arbitration",
    "collaboration",
    "conflict",
    "distributed",
    "merge",
    "reputation",
    "routing",
    "workflow",
    "workspace",
]
