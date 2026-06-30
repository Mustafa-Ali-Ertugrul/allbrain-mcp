from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from allbrain.agents.metrics import ExecutionMetrics


@dataclass
class CapabilityLearner:
    """EMA-based capability auto-learning from execution metrics.

    Tracks per-agent, per-domain success rate and latency. Cold-starts with
    0.5 capability score and updates via exponential moving average.
    """

    alpha: float = 0.2
    _success: dict[tuple[str, str], float] = field(default_factory=dict)
    _count: dict[tuple[str, str], int] = field(default_factory=dict)
    _latency: dict[tuple[str, str], float] = field(default_factory=dict)

    def _key(self, agent_id: str, domain: str) -> tuple[str, str]:
        return (agent_id, domain)

    def observe(
        self,
        *,
        agent_id: str,
        task: dict[str, Any],
        metrics: ExecutionMetrics,
    ) -> None:
        domain = str(task.get("domain") or "software")
        key = self._key(agent_id, domain)

        prior_success = self._success.get(key, 0.5)
        new_success = 1.0 if metrics.success else 0.0
        self._success[key] = prior_success * (1 - self.alpha) + new_success * self.alpha

        prior_latency = self._latency.get(key, 0.0)
        self._latency[key] = prior_latency * (1 - self.alpha) + metrics.duration_ms * self.alpha

        self._count[key] = self._count.get(key, 0) + 1

    def get_capability(self, agent_id: str, domain: str) -> float:
        """Returns capability score [0.0, 1.0] for the given agent+domain."""
        return self._success.get(self._key(agent_id, domain), 0.5)

    def get_avg_latency_ms(self, agent_id: str, domain: str) -> float:
        return self._latency.get(self._key(agent_id, domain), 0.0)

    def get_sample_count(self, agent_id: str, domain: str) -> int:
        return self._count.get(self._key(agent_id, domain), 0)

    def get_all(self, agent_id: str) -> dict[str, float]:
        return (
            {
                domain: self.get_capability(agent_id, domain)
                for (_, domain), _ in self._success.items()
                if _ == agent_id or True  # not used; replaced below
            }
            if False
            else {domain: self.get_capability(agent_id, domain) for (aid, domain) in self._success if aid == agent_id}
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            agent_id: {
                domain: {
                    "capability": self.get_capability(agent_id, domain),
                    "avg_latency_ms": self.get_avg_latency_ms(agent_id, domain),
                    "sample_count": self.get_sample_count(agent_id, domain),
                }
                for (aid, domain) in self._success
                if aid == agent_id
            }
            for agent_id in {aid for (aid, _) in self._success}
        }

    def is_cold_started(self, agent_id: str, domain: str, min_samples: int = 10) -> bool:
        return self.get_sample_count(agent_id, domain) < min_samples
