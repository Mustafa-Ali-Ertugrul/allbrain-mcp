from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from allbrain.domains.collaboration.distributed.node_identity import NodeIdentity
from allbrain.domains.collaboration.distributed.worker_registry import WorkerRegistry


@dataclass
class ClusterManager:
    node: NodeIdentity = field(default_factory=NodeIdentity.create)
    registry: WorkerRegistry = field(default_factory=WorkerRegistry)

    def register_worker(
        self, worker_id: str, *, capabilities: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.registry.register(
            worker_id, node_id=self.node.node_id, capabilities=capabilities, metadata=metadata
        ).to_dict()

    def heartbeat(self, worker_id: str) -> dict[str, Any]:
        return self.registry.heartbeat(worker_id).to_dict()

    def health(self) -> dict[str, Any]:
        active = self.registry.discover()
        stale = self.registry.discover(include_stale=True)
        return {
            "node": self.node.to_dict(),
            "active_workers": len(active),
            "total_workers": len(stale),
            "workers": stale,
        }
