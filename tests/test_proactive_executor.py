from __future__ import annotations

from allbrain.domains.analysis.predictive_failure.model import MitigationPlan
from allbrain.domains.analysis.predictive_failure.proactive_executor import ProactiveExecutor


def _make_plan(
    plan_id: str = "p1",
    fault_id: str = "f1",
    fault_type: str = "timeout",
    strategy: str = "throttle_retry",
    urgency: float = 0.80,
) -> MitigationPlan:
    return MitigationPlan(
        plan_id=plan_id,
        fault_id=fault_id,
        fault_type=fault_type,
        strategy=strategy,
        urgency=urgency,
        expected_risk_reduction=0.64,
    )


class TestProactiveExecutor:
    def setup_method(self) -> None:
        self.executor = ProactiveExecutor()

    def test_execute_returns_success(self) -> None:
        plan = _make_plan()
        action = self.executor.execute(plan)
        assert action.success is True

    def test_snapshot_id_deterministic(self) -> None:
        plan = _make_plan()
        action1 = self.executor.execute(plan)
        action2 = self.executor.execute(plan)
        assert action1.snapshot_id == action2.snapshot_id

    def test_snapshot_id_length_16(self) -> None:
        plan = _make_plan()
        action = self.executor.execute(plan)
        assert len(action.snapshot_id) == 16

    def test_action_id_deterministic(self) -> None:
        plan = _make_plan()
        action1 = self.executor.execute(plan)
        action2 = self.executor.execute(plan)
        assert action1.action_id == action2.action_id

    def test_action_id_length_16(self) -> None:
        plan = _make_plan()
        action = self.executor.execute(plan)
        assert len(action.action_id) == 16

    def test_rollback_possible_for_pre_rollback_snapshot(self) -> None:
        plan = _make_plan(strategy="pre_rollback_snapshot")
        action = self.executor.execute(plan)
        assert action.rollback_possible is True

    def test_rollback_possible_for_circuit_warmup(self) -> None:
        plan = _make_plan(strategy="circuit_warmup")
        action = self.executor.execute(plan)
        assert action.rollback_possible is True

    def test_rollback_possible_for_rate_limit(self) -> None:
        plan = _make_plan(strategy="rate_limit")
        action = self.executor.execute(plan)
        assert action.rollback_possible is True

    def test_rollback_not_possible_for_throttle_retry(self) -> None:
        plan = _make_plan(strategy="throttle_retry")
        action = self.executor.execute(plan)
        assert action.rollback_possible is False

    def test_rollback_not_possible_for_log_warning(self) -> None:
        plan = _make_plan(strategy="log_warning")
        action = self.executor.execute(plan)
        assert action.rollback_possible is False

    def test_message_contains_strategy(self) -> None:
        plan = _make_plan(strategy="throttle_retry")
        action = self.executor.execute(plan)
        assert "throttle_retry" in action.message

    def test_plan_id_reference_preserved(self) -> None:
        plan = _make_plan(plan_id="my_plan_1")
        action = self.executor.execute(plan)
        assert action.plan_id == "my_plan_1"

    def test_different_plans_different_actions(self) -> None:
        plan1 = _make_plan(plan_id="p1", strategy="throttle_retry")
        plan2 = _make_plan(plan_id="p2", strategy="circuit_warmup")
        action1 = self.executor.execute(plan1)
        action2 = self.executor.execute(plan2)
        assert action1.action_id != action2.action_id
        assert action1.snapshot_id != action2.snapshot_id
