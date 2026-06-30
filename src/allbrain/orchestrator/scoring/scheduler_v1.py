from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta, timezone
from math import log
from typing import Any, Protocol

from allbrain.orchestrator.agent_profile import AgentProfile, TaskRequirements
from allbrain.orchestrator.capabilities import CapabilityRegistry

EPSILON = 0.10
RECOVERY_AFTER = timedelta(minutes=15)
MIN_CAPABILITY_THRESHOLD = 0.1
CONFIDENCE_TARGET_SAMPLE_SIZE = 50
MAX_RETRIES = 3


class RandomLike(Protocol):
    def random(self) -> float: ...

    def choice(self, seq: list[dict[str, Any]]) -> dict[str, Any]: ...


class SchedulerV1:
    """Agent task assignment scheduler using epsilon-greedy selection.

    Balances exploitation (highest-scoring agent) with exploration (random selection)
    using configurable epsilon. Scores agents based on capability match, health,
    and historical performance metrics.
    """

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        *,
        rng: RandomLike | None = None,
        epsilon: float = EPSILON,
        min_capability_threshold: float = MIN_CAPABILITY_THRESHOLD,
        confidence_target_sample_size: int = CONFIDENCE_TARGET_SAMPLE_SIZE,
        max_retries: int = MAX_RETRIES,
    ):
        self.registry = registry or CapabilityRegistry.from_env()
        self.rng = rng or random.Random(0)
        self.epsilon = epsilon
        self.min_capability_threshold = min_capability_threshold
        self.confidence_target_sample_size = confidence_target_sample_size
        self.max_retries = max_retries

    def assign_task(
        self,
        *,
        task: dict[str, Any],
        candidate_agents: list[str],
        metrics: dict[str, dict[str, Any]],
        task_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assign task to best candidate agent using epsilon-greedy selection.

        Scores all candidates, filters by capability threshold, and selects either
        the highest-scoring agent (exploitation) or a random eligible agent (exploration).

        Returns:
            Assignment decision with selected agent_id, score, breakdown, and reason.

        Raises:
            ValueError: If no eligible agents available for assignment.
        """
        scored = [
            self.score_agent(
                agent_id=agent_id,
                task=task,
                metrics=metrics,
                task_state=task_state,
            )
            for agent_id in candidate_agents
        ]
        eligible = [item for item in scored if item["eligible"]]
        above_threshold = [
            item for item in eligible if item["breakdown"]["capability_score"] >= self.min_capability_threshold
        ]
        fallback_mode = False
        if above_threshold:
            eligible = above_threshold
        else:
            domain_matched = [item for item in eligible if item["breakdown"]["domain_matched"]]
            if domain_matched:
                eligible = domain_matched
                fallback_mode = True
        if not eligible:
            raise ValueError("no eligible agents available for assignment")

        if self.rng.random() < self.epsilon:
            winner = self.rng.choice(eligible)
            reason = "exploration"
        else:
            eligible.sort(
                key=lambda item: (
                    -item["score"],
                    item["metrics"]["failure_count"],
                    item["metrics"]["blocked_count"],
                    item["agent_id"],
                )
            )
            winner = eligible[0]
            reason = "highest_score"

        return {
            "agent_id": winner["agent_id"],
            "score": winner["score"],
            "total_score": winner["score"],
            "breakdown": winner["breakdown"],
            "reason": reason,
            "fallback_mode": fallback_mode,
            "selection_decision": {
                "agent_id": winner["agent_id"],
                "total_score": winner["score"],
                "breakdown": winner["breakdown"],
                "reason": reason,
                "fallback_mode": fallback_mode,
            },
            "candidate_agents": scored,
        }

    def score_agent(
        self,
        *,
        agent_id: str,
        task: dict[str, Any],
        metrics: dict[str, dict[str, Any]],
        task_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_state = task_state or {}
        agent_metrics = metrics.get(agent_id, self._empty_metrics(agent_id))
        agent_profile = AgentProfile.from_raw(
            agent_id,
            self.registry.capabilities.get(agent_id, {}),
            metrics=agent_metrics,
        )
        task_requirements = TaskRequirements.from_task(task)
        attempted_agents = set(task.get("attempted_agents") or task_state.get("attempted_agents") or [])
        attempt_count = int(task.get("attempt_count") or task_state.get("attempt_count") or len(attempted_agents))
        current_load = self._current_load(agent_id, task_state)

        capability_score = _clamp(agent_profile.capability_score(task_requirements))
        success_rate = _clamp(agent_metrics["success_rate"] if agent_metrics["total_tasks"] else 0.5)
        confidence = _clamp(agent_metrics.get("confidence") or self._confidence(agent_metrics["total_tasks"]))
        latency_score = _clamp(1 - min(agent_profile.cost["avg_latency_ms"] / 10_000, 1))
        load_score = _clamp(1 - min(current_load / 10, 1))
        score = _clamp(
            capability_score * 0.40 + success_rate * 0.30 + confidence * 0.15 + latency_score * 0.10 + load_score * 0.05
        )

        attempted = agent_id in attempted_agents
        recovery_probe = self._recovery_probe(agent_profile.health.last_failure_at)
        healthy = agent_profile.health.healthy or recovery_probe
        retry_budget_available = attempt_count < self.max_retries
        eligible = not attempted and healthy and retry_budget_available
        domain_matched = any(capability.domain == task_requirements.domain for capability in agent_profile.capabilities)

        return {
            "agent_id": agent_id,
            "score": round(score, 6),
            "eligible": eligible,
            "breakdown": {
                "domain": task_requirements.domain,
                "required_skills": sorted(task_requirements.required_skills),
                "agent_version": agent_profile.version,
                "metric_key": f"{agent_id}@{agent_profile.version}",
                "capability_score": round(capability_score, 6),
                "capability": round(capability_score, 6),
                "success_rate": round(success_rate, 6),
                "confidence": round(confidence, 6),
                "metrics_confidence": round(confidence, 6),
                "latency_score": round(latency_score, 6),
                "latency": round(latency_score, 6),
                "load_score": round(load_score, 6),
                "load": round(load_score, 6),
                "cold_start_weighted": agent_metrics["assigned_count"] < 10,
                "attempted": attempted,
                "attempt_count": attempt_count,
                "retry_budget_available": retry_budget_available,
                "domain_matched": domain_matched,
                "healthy": agent_profile.health.healthy,
                "recovery_probe": recovery_probe,
                "in_probe_mode": recovery_probe,
            },
            "metrics": agent_metrics,
        }

    def _current_load(self, agent_id: str, task_state: dict[str, Any]) -> int:
        queues = task_state.get("agent_queue", {})
        queue = queues.get(agent_id, []) if isinstance(queues, dict) else []
        return len(queue) if isinstance(queue, list) else 0

    def _recovery_probe(self, last_failure_at: datetime | None) -> bool:
        if last_failure_at is None:
            return False
        now = datetime.now(UTC)
        # last_failure_at may be naive (legacy data); treat as UTC for comparison
        if last_failure_at.tzinfo is None:
            last_failure_at = last_failure_at.replace(tzinfo=UTC)
        return now - last_failure_at >= RECOVERY_AFTER

    def _confidence(self, total_tasks: int) -> float:
        return min(1.0, log(total_tasks + 1) / log(self.confidence_target_sample_size))

    def _empty_metrics(self, agent_id: str) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "agent_version": None,
            "success_count": 0,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 0,
            "total_tasks": 0,
            "success_rate": 0.0,
            "failure_rate": 0.0,
            "blocked_rate": 0.0,
            "confidence": 0.0,
            "user_feedback_score": None,
            "consecutive_failures": 0,
            "last_failure_at": None,
            "last_failure_reason": None,
        }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
