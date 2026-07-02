from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from allbrain.events import EventType
from allbrain.governance import (
    AutonomousGovernanceCoordinator,
    ConstitutionalReasoner,
    GovernanceMetrics,
    GovernanceStateBuilder,
    SelfModificationGuard,
)
from allbrain.graph import WorkflowGraphBuilder
from allbrain.memory import MemoryBuilder
from allbrain.observability import DashboardDataBuilder
from allbrain.replay import EventReplayEngine
from allbrain.server.app import save_event_impl
from tests.test_sprint12_memory_policy_ui import events, make_context


def test_self_modification_guard_records_and_prunes_history() -> None:
    guard = SelfModificationGuard(window_seconds=3600, threshold=3)

    guard.record_rejection("agent_a", "alignment_failed")
    guard.record_rejection("agent_a", "alignment_failed")
    guard.record_rejection("agent_a", "confidence_low")

    summary = guard.get_rejection_summary("agent_a")
    assert summary["total_rejections"] == 3
    assert summary["recent_rejections"] == 3
    assert summary["reasons"]["alignment_failed"] == 2
    assert summary["reasons"]["confidence_low"] == 1
    assert summary["can_propose"] is False
    assert "supervisor escalation required" in summary["message"]

    guard.clear_history("agent_a")
    assert guard.get_rejection_summary("agent_a")["total_rejections"] == 0
    assert guard.can_propose("agent_a")[0] is True


def test_self_modification_guard_allows_below_threshold() -> None:
    guard = SelfModificationGuard(window_seconds=3600, threshold=3)

    guard.record_rejection("agent_b", "identity_restructure_needed")
    guard.record_rejection("agent_b", "identity_restructure_needed")

    assert guard.detect_repetitive_rejection("agent_b") is False
    assert guard.can_propose("agent_b")[0] is True


def test_self_modification_guard_respects_window() -> None:
    guard = SelfModificationGuard(window_seconds=60, threshold=2)

    old = datetime.now(UTC) - timedelta(seconds=120)
    guard.record_rejection("agent_c", "alignment_failed", timestamp=old)
    guard.record_rejection("agent_c", "alignment_failed", timestamp=old)

    assert guard.detect_repetitive_rejection("agent_c") is False

    guard.record_rejection("agent_c", "alignment_failed")
    guard.record_rejection("agent_c", "alignment_failed")

    assert guard.detect_repetitive_rejection("agent_c") is True


def test_self_modification_guard_detect_passes_override_params() -> None:
    guard = SelfModificationGuard(window_seconds=3600, threshold=5)

    for _ in range(3):
        guard.record_rejection("agent_d", "alignment_failed")

    assert guard.detect_repetitive_rejection("agent_d") is False
    assert guard.detect_repetitive_rejection("agent_d", window_seconds=3600, threshold=3) is True


def test_self_modification_guard_clear_history() -> None:
    guard = SelfModificationGuard(window_seconds=3600, threshold=3)
    guard.record_rejection("agent_e", "alignment_failed")
    guard.record_rejection("agent_e", "alignment_failed")
    guard.record_rejection("agent_e", "alignment_failed")

    assert guard.can_propose("agent_e")[0] is False

    guard.clear_history("agent_e")
    assert guard.can_propose("agent_e")[0] is True
    summary = guard.get_rejection_summary("agent_e")
    assert summary["total_rejections"] == 0


def test_constitutional_reasoner_includes_supervisor_required() -> None:
    reasoner = ConstitutionalReasoner()

    result = reasoner.reason(
        {"constitutional_violations": ["do_not_trade_long_term_alignment_for_short_term_gain"]},
        [{"short_term_gain_bias": True, "confidence": 0.8}],
        {"long_term_drift_score": 0.6, "alignment_score": 0.5, "safety_alignment_score": 0.7},
    )

    assert result["supervisor_required"] is True
    assert result["has_explicit_violation"] is True
    assert "do_not_trade_long_term_alignment_for_short_term_gain" in result["violations"]


def test_constitutional_reasoner_no_violation_no_supervisor() -> None:
    reasoner = ConstitutionalReasoner()

    result = reasoner.reason(
        {},
        [{"confidence": 0.9, "safety_validation": True, "requested_autonomy_level": 2}],
        {"long_term_drift_score": 0.2, "alignment_score": 0.9, "safety_alignment_score": 0.85},
    )

    assert result["supervisor_required"] is False
    assert result["has_explicit_violation"] is False
    assert len(result["violations"]) == 0


def test_self_modification_guard_isolates_agents() -> None:
    guard = SelfModificationGuard(window_seconds=3600, threshold=3)

    guard.record_rejection("agent_x", "alignment_failed")
    guard.record_rejection("agent_x", "alignment_failed")
    guard.record_rejection("agent_x", "alignment_failed")
    guard.record_rejection("agent_y", "confidence_low")

    assert guard.can_propose("agent_x")[0] is False
    assert guard.can_propose("agent_y")[0] is True


def test_architecture_mutation_with_alignment_decay_is_rejected() -> None:
    result = AutonomousGovernanceCoordinator().review(
        {"current_autonomy_level": 3, "trajectory_confidence": 0.8},
        [
            {
                "proposal_id": "p_arch",
                "change_type": "architecture_change",
                "mutation_type": "new_subsystem_proposal",
                "risk_level": "high",
                "alignment_decay_risk": 0.85,
                "confidence": 0.8,
            }
        ],
    )

    assert result["governance_decision"]["decision"] == "reject_expansion"
    assert result["alignment_report"]["safety_alignment_score"] < 0.4
    assert "constitutional_reasoning" in result["meta_governance_feedback"]


def test_efficiency_gain_that_reduces_interpretability_is_constrained() -> None:
    result = AutonomousGovernanceCoordinator().review(
        {"current_autonomy_level": 2, "trajectory_confidence": 0.8},
        [
            {
                "proposal_id": "p_efficiency",
                "change_type": "strategy_change",
                "risk_level": "medium",
                "expected_improvement": 0.25,
                "reduces_interpretability": True,
                "confidence": 0.8,
            }
        ],
    )

    assert result["governance_decision"]["decision"] == "approve_with_constraints"
    assert "canary_rollout" in result["system_constraints_update"]["constraints"]
    assert "post_change_alignment_check" in result["autonomy_action"]["constraints_applied"]


def test_autonomy_jump_beyond_one_band_escalates_with_safety_validation() -> None:
    result = AutonomousGovernanceCoordinator().review(
        {"current_autonomy_level": 1, "trajectory_confidence": 0.85},
        [
            {
                "proposal_id": "p_autonomy",
                "change_type": "policy_update",
                "risk_level": "medium",
                "requested_autonomy_level": 4,
                "safety_validation": True,
                "confidence": 0.85,
            }
        ],
    )

    assert result["governance_decision"]["decision"] == "escalate_to_supervision"
    assert result["autonomy_action"]["autonomy_level_allowed"] == 2
    assert "limit_autonomy_transition_to_single_band" in result["autonomy_action"]["constraints"]


def test_repeated_post_checks_raise_allowed_autonomy_in_state(tmp_path) -> None:
    context = make_context(tmp_path)
    for index in range(3):
        assert save_event_impl(
            context,
            type=EventType.GOVERNANCE_POST_CHECK_COMPLETED.value,
            payload={"review_id": f"gr{index}", "status": "success", "alignment_preserved": True},
        ).ok

    state = GovernanceStateBuilder().build(events(context))

    assert state["current_autonomy_level"] == 1


def test_governance_events_integrate_with_replay_graph_memory_and_dashboard(tmp_path) -> None:
    context = make_context(tmp_path)
    assert save_event_impl(
        context,
        type=EventType.GOVERNANCE_REVIEW_INITIATED.value,
        payload={
            "review_id": "gr1",
            "trigger_source": "meta_optimization",
            "proposal_batch_id": "batch1",
            "system_area": "scheduler",
        },
    ).ok
    assert save_event_impl(
        context,
        type=EventType.GOVERNANCE_ALIGNMENT_EVALUATED.value,
        payload={
            "review_id": "gr1",
            "report_id": "ar1",
            "alignment_score": 0.68,
            "long_term_drift_score": 0.32,
            "safety_alignment_score": 0.76,
            "identity_consistency_score": 0.82,
        },
    ).ok
    assert save_event_impl(
        context,
        type=EventType.GOVERNANCE_TRAJECTORY_SIMULATED.value,
        payload={"review_id": "gr1", "trajectory_id": "st1", "trajectory_score": 0.7, "confidence": 0.72},
    ).ok
    assert save_event_impl(
        context,
        type=EventType.GOVERNANCE_AUTONOMY_ASSESSED.value,
        payload={"review_id": "gr1", "decision_id": "ad1", "autonomy_level_allowed": 3, "autonomy_impact": 1},
    ).ok
    assert save_event_impl(
        context,
        type=EventType.GOVERNANCE_DECISION_SYNTHESIZED.value,
        payload={
            "review_id": "gr1",
            "decision_id": "gd1",
            "decision": "approve_with_constraints",
            "alignment_score": 0.68,
            "trajectory_score": 0.7,
            "autonomy_level_allowed": 3,
            "confidence": 0.72,
        },
    ).ok
    assert save_event_impl(
        context,
        type=EventType.GOVERNANCE_CONSTRAINTS_APPLIED.value,
        payload={"review_id": "gr1", "constraints": ["canary_rollout", "post_change_alignment_check"]},
    ).ok

    all_events = events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]
    graph = WorkflowGraphBuilder().build(all_events)
    memory = MemoryBuilder().build(all_events)
    dashboard = DashboardDataBuilder().build(all_events)
    metrics = GovernanceMetrics().build(all_events)

    assert replay["governance"]["decisions"]["gd1"]["decision"] == "approve_with_constraints"
    assert "governance_review:gr1" in graph["nodes"]
    assert "governance_decision:gd1" in graph["nodes"]
    assert "governance_constraint:gr1" in graph["nodes"]
    assert any(item.tags.get("kind") == "governance_decision" for item in memory)
    assert any(item.tags.get("kind") == "alignment_report" for item in memory)
    assert dashboard["governance"]["constrained_mutation_ratio"] == 1.0
    assert metrics["decision_counts"]["approve_with_constraints"] == 1


def _rejection_proposals() -> list[dict[str, Any]]:
    """Proposals that trigger reject_expansion from SelfModificationAuthorityEngine."""
    return [
        {
            "proposal_id": "p_reject",
            "change_type": "architecture_change",
            "mutation_type": "high_risk_change",
            "risk_level": "high",
            "alignment_decay_risk": 0.85,
            "confidence": 0.3,
        }
    ]


def _approval_proposals() -> list[dict[str, Any]]:
    """Proposals that trigger approve_expansion from SelfModificationAuthorityEngine."""
    return [
        {
            "proposal_id": "p_approve",
            "change_type": "strategy_change",
            "risk_level": "low",
            "confidence": 0.85,
        }
    ]


def test_repeated_rejections_escalate_via_coordinator() -> None:
    coordinator = AutonomousGovernanceCoordinator()
    context: dict[str, Any] = {"agent_id": "agent_repeat", "current_autonomy_level": 1}
    bad_ctx = {**context, "trajectory_confidence": 0.3}

    # First 2 calls: reject_expansion (guard below threshold)
    for i in range(2):
        result = coordinator.review(bad_ctx, _rejection_proposals())
        assert result["governance_decision"]["decision"] in {
            "reject_expansion",
            "require_restructuring",
            "delay_expansion",
        }, f"iteration {i} should be a rejection"

    # 3rd call: guard kicks in (threshold=3, >=), escalates
    third = coordinator.review(bad_ctx, _rejection_proposals())
    assert third["governance_decision"]["decision"] == "escalate_to_supervision"
    assert "supervisor escalation required" in third["governance_decision"]["reasoning"]
    assert third["governance_decision"]["risk_level"] == "high"


def test_approval_clears_coordinator_guard_history() -> None:
    coordinator = AutonomousGovernanceCoordinator()
    context: dict[str, Any] = {"agent_id": "agent_clear", "current_autonomy_level": 1}
    bad_ctx = {**context, "trajectory_confidence": 0.3}

    for _ in range(2):
        coordinator.review(bad_ctx, _rejection_proposals())

    coordinator.review(context, _approval_proposals())

    after_approval = coordinator.review(bad_ctx, _rejection_proposals())
    assert after_approval["governance_decision"]["decision"] in {
        "reject_expansion",
        "require_restructuring",
        "delay_expansion",
    }, "approval should have cleared guard history"


def test_coordinator_guard_isolates_agents() -> None:
    coordinator = AutonomousGovernanceCoordinator()
    bad_ctx: dict[str, Any] = {"agent_id": "agent_x", "current_autonomy_level": 1, "trajectory_confidence": 0.3}

    # 3 calls to agent_x: 3rd triggers escalation
    for i in range(3):
        if i < 2:
            r = coordinator.review(bad_ctx, _rejection_proposals())
            assert r["governance_decision"]["decision"] in {
                "reject_expansion",
                "require_restructuring",
                "delay_expansion",
            }, f"iteration {i} should reject"
        else:
            x_result = coordinator.review(bad_ctx, _rejection_proposals())
            assert x_result["governance_decision"]["decision"] == "escalate_to_supervision"

    # agent_y with fresh history should still reject (not escalate)
    y_result = coordinator.review({**bad_ctx, "agent_id": "agent_y"}, _rejection_proposals())
    assert y_result["governance_decision"]["decision"] in {
        "reject_expansion",
        "require_restructuring",
        "delay_expansion",
    }, "agent_y should not be affected by agent_x history"


def test_guard_summary_in_meta_feedback() -> None:
    coordinator = AutonomousGovernanceCoordinator()
    context: dict[str, Any] = {"agent_id": "agent_fb", "current_autonomy_level": 1}
    bad_ctx = {**context, "trajectory_confidence": 0.3}

    result = coordinator.review(bad_ctx, _rejection_proposals())
    feedback = result["meta_governance_feedback"]
    assert "self_modification_guard" in feedback
    guard_data = feedback["self_modification_guard"]
    assert guard_data["agent_id"] == "agent_fb"
    assert guard_data["recent_rejections"] >= 1
