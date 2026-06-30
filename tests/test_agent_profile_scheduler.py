from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from allbrain.orchestrator.scoring import SchedulerV1
from allbrain.orchestrator.state import AgentStateBuilder


class FakeRegistry:
    capabilities = {
        "build": {
            "version": "1.0.0",
            "capabilities": {
                "software": ["coding", "implementation", "refactoring"],
            },
            "cost": {"avg_latency_ms": 1000, "avg_cost": 0.004},
        },
        "reviewer": {
            "version": "2.1.0",
            "capabilities": {
                "software": ["security", "review", "performance"],
            },
            "cost": {"avg_latency_ms": 1200, "avg_cost": 0.006},
        },
        "architect": {
            "version": "1.4.0",
            "capabilities": {
                "software": ["architecture", "review"],
            },
            "cost": {"avg_latency_ms": 1600, "avg_cost": 0.005},
        },
    }

    def agents(self) -> list[str]:
        return list(self.capabilities)


class ExplorationRng:
    def random(self) -> float:
        return 0.0

    def choice(self, seq: list[dict[str, object]]) -> dict[str, object]:
        return seq[-1]


def metrics(
    agent_id: str,
    *,
    total_tasks: int = 0,
    success_rate: float = 0.0,
    confidence: float = 0.0,
    consecutive_failures: int = 0,
    last_failure_reason: str | None = None,
) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "agent_version": None,
        "success_count": int(total_tasks * success_rate),
        "failure_count": total_tasks - int(total_tasks * success_rate),
        "blocked_count": 0,
        "assigned_count": total_tasks,
        "total_tasks": total_tasks,
        "success_rate": success_rate,
        "failure_rate": 1 - success_rate if total_tasks else 0.0,
        "blocked_rate": 0.0,
        "confidence": confidence,
        "user_feedback_score": None,
        "consecutive_failures": consecutive_failures,
        "last_failure_at": datetime.now(UTC).isoformat() if consecutive_failures else None,
        "last_failure_reason": last_failure_reason,
    }


def test_security_task_selects_reviewer_by_capability_overlap() -> None:
    scheduler = SchedulerV1(FakeRegistry(), epsilon=0.0)  # type: ignore[arg-type]

    result = scheduler.assign_task(
        task={"domain": "software", "required_skills": ["security"]},
        candidate_agents=["build", "reviewer"],
        metrics={},
    )

    assert result["agent_id"] == "reviewer"
    assert result["candidate_agents"][0]["breakdown"]["capability_score"] == 0.0
    assert result["candidate_agents"][1]["breakdown"]["capability_score"] == 1.0


def test_unhealthy_reviewer_is_skipped() -> None:
    scheduler = SchedulerV1(FakeRegistry(), epsilon=0.0)  # type: ignore[arg-type]

    result = scheduler.assign_task(
        task={"domain": "software", "required_skills": ["security"]},
        candidate_agents=["reviewer", "architect"],
        metrics={"reviewer": metrics("reviewer", consecutive_failures=5)},
    )

    assert result["agent_id"] == "architect"
    reviewer = next(item for item in result["candidate_agents"] if item["agent_id"] == "reviewer")
    assert reviewer["eligible"] is False


def test_retry_routing_does_not_select_attempted_agent() -> None:
    scheduler = SchedulerV1(FakeRegistry(), epsilon=0.0)  # type: ignore[arg-type]

    result = scheduler.assign_task(
        task={"domain": "software", "required_skills": ["implementation"], "attempted_agents": ["build"]},
        candidate_agents=["build", "architect"],
        metrics={},
    )

    assert result["agent_id"] == "architect"
    build = next(item for item in result["candidate_agents"] if item["agent_id"] == "build")
    assert build["eligible"] is False
    assert build["breakdown"]["attempted"] is True


def test_unhealthy_agent_can_recover_after_circuit_breaker_window() -> None:
    scheduler = SchedulerV1(FakeRegistry(), epsilon=0.0)  # type: ignore[arg-type]
    old_failure = (datetime.now(UTC) - timedelta(minutes=16)).isoformat()

    result = scheduler.assign_task(
        task={"domain": "software", "required_skills": ["security"]},
        candidate_agents=["reviewer", "architect"],
        metrics={
            "reviewer": metrics("reviewer", consecutive_failures=5)
            | {"last_failure_at": old_failure}
        },
    )

    assert result["agent_id"] == "reviewer"
    reviewer = next(item for item in result["candidate_agents"] if item["agent_id"] == "reviewer")
    assert reviewer["eligible"] is True
    assert reviewer["breakdown"]["recovery_probe"] is True
    assert reviewer["breakdown"]["in_probe_mode"] is True


def test_fallback_mode_uses_domain_matched_agents_when_no_capability_threshold_passes() -> None:
    scheduler = SchedulerV1(FakeRegistry(), epsilon=0.0)  # type: ignore[arg-type]

    result = scheduler.assign_task(
        task={"domain": "software", "required_skills": ["observability"]},
        candidate_agents=["reviewer", "architect"],
        metrics={
            "reviewer": metrics("reviewer", total_tasks=100, success_rate=0.95, confidence=1.0),
            "architect": metrics("architect", total_tasks=100, success_rate=0.40, confidence=1.0),
        },
    )

    assert result["fallback_mode"] is True
    assert result["agent_id"] == "reviewer"


def test_retry_budget_exhaustion_removes_all_candidates() -> None:
    scheduler = SchedulerV1(FakeRegistry(), epsilon=0.0)  # type: ignore[arg-type]

    try:
        scheduler.assign_task(
            task={"domain": "software", "required_skills": ["review"], "attempt_count": 3},
            candidate_agents=["reviewer", "architect"],
            metrics={},
        )
    except ValueError as exc:
        assert "no eligible agents" in str(exc)
    else:
        raise AssertionError("expected exhausted retry budget to fail assignment")


def test_high_success_agent_wins_with_enough_history() -> None:
    scheduler = SchedulerV1(FakeRegistry(), epsilon=0.0)  # type: ignore[arg-type]

    result = scheduler.assign_task(
        task={"domain": "software", "required_skills": ["review"]},
        candidate_agents=["reviewer", "architect"],
        metrics={
            "reviewer": metrics("reviewer", total_tasks=100, success_rate=0.60, confidence=1.0),
            "architect": metrics("architect", total_tasks=100, success_rate=0.95, confidence=1.0),
        },
    )

    assert result["agent_id"] == "architect"


def test_exploration_can_select_lower_scored_eligible_agent() -> None:
    scheduler = SchedulerV1(
        FakeRegistry(),  # type: ignore[arg-type]
        rng=ExplorationRng(),  # type: ignore[arg-type]
        epsilon=0.10,
    )

    result = scheduler.assign_task(
        task={"domain": "software", "required_skills": ["review"]},
        candidate_agents=["reviewer", "architect"],
        metrics={
            "reviewer": metrics("reviewer", total_tasks=100, success_rate=0.95, confidence=1.0),
            "architect": metrics("architect", total_tasks=100, success_rate=0.30, confidence=1.0),
        },
    )

    assert result["reason"] == "exploration"
    assert result["agent_id"] == "architect"
    assert result["selection_decision"]["breakdown"]["capability"] == 1.0


def test_confidence_target_sample_size_is_configurable() -> None:
    scheduler = SchedulerV1(  # type: ignore[arg-type]
        FakeRegistry(),
        epsilon=0.0,
        confidence_target_sample_size=100,
    )

    scored = scheduler.score_agent(
        agent_id="reviewer",
        task={"domain": "software", "required_skills": ["review"]},
        metrics={"reviewer": metrics("reviewer", total_tasks=10, success_rate=1.0)},
    )

    assert 0.0 < scored["breakdown"]["confidence"] < 1.0


def test_agent_state_exposes_version_capabilities_cost_health_and_feedback() -> None:
    state = AgentStateBuilder(FakeRegistry()).build(  # type: ignore[arg-type]
        metrics={
            "build": metrics(
                "build",
                total_tasks=5,
                success_rate=0.0,
                confidence=0.35,
                consecutive_failures=5,
                last_failure_reason="timeout",
            )
            | {"user_feedback_score": 0.2}
        },
        task_state={"agent_queue": {"build": ["task-1"]}},
    )

    assert state["build"]["version"] == "1.0.0"
    assert state["build"]["capabilities"] == {
        "software": ["coding", "implementation", "refactoring"]
    }
    assert state["build"]["health"]["healthy"] is False
    assert state["build"]["health"]["last_failure_reason"] == "timeout"
    assert state["build"]["health"]["in_probe_mode"] is False
    assert state["build"]["cost"]["avg_cost"] == 0.004
    assert state["build"]["performance"]["metric_key"] == "build@1.0.0"
    assert state["build"]["performance"]["user_feedback_score"] == 0.2
