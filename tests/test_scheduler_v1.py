from allbrain.orchestrator.capabilities import CapabilityRegistry
from allbrain.orchestrator.scoring import SchedulerV1


def scheduler() -> SchedulerV1:
    return SchedulerV1(
        CapabilityRegistry(
            {
                "codex": {"implementation": 10, "testing": 5},
                "claude": {"implementation": 7, "testing": 6},
                "opencode": {"implementation": 7, "testing": 10},
            }
        )
    )


def metric(agent_id: str, *, assigned: int, success: int, failed: int = 0, blocked: int = 0) -> dict:
    total = success + failed + blocked
    denominator = max(1, total)
    import math

    return {
        "agent_id": agent_id,
        "success_count": success,
        "failure_count": failed,
        "blocked_count": blocked,
        "assigned_count": assigned,
        "total_tasks": total,
        "success_rate": success / denominator,
        "failure_rate": failed / denominator,
        "blocked_rate": blocked / denominator,
        "confidence": min(1.0, math.log(total + 1) / math.log(50)),
    }


def test_cold_start_capability_dominates_assignment() -> None:
    result = scheduler().assign_task(
        task={"task_id": "t", "kind": "implementation"},
        candidate_agents=["claude", "codex"],
        metrics={},
    )

    assert result["agent_id"] == "codex"
    assert result["breakdown"]["metrics_confidence"] == 0
    assert result["breakdown"]["cold_start_weighted"] is True


def test_sample_size_confidence_prevents_one_success_from_overpowering_capability() -> None:
    result = scheduler().assign_task(
        task={"task_id": "t", "kind": "implementation"},
        candidate_agents=["codex", "claude"],
        metrics={
            "codex": metric("codex", assigned=100, success=80, failed=20),
            "claude": metric("claude", assigned=1, success=1),
        },
    )

    assert result["agent_id"] == "codex"


def test_failure_penalty_lowers_ranking_and_tie_break_is_deterministic() -> None:
    result = scheduler().assign_task(
        task={"task_id": "t", "kind": "implementation"},
        candidate_agents=["opencode", "claude"],
        metrics={
            "claude": metric("claude", assigned=20, success=10, failed=10),
            "opencode": metric("opencode", assigned=20, success=10),
        },
    )

    assert result["agent_id"] == "opencode"

    tied = scheduler().assign_task(
        task={"task_id": "t", "kind": "implementation"},
        candidate_agents=["opencode", "claude"],
        metrics={
            "claude": metric("claude", assigned=20, success=10),
            "opencode": metric("opencode", assigned=20, success=10),
        },
    )

    assert tied["agent_id"] == "claude"
