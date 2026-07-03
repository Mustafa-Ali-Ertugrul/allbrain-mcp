from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.objective_system import make_objective_rebalanced_payload


class LearningRepairCoordinator:
    """Coordinate outcome learning, policy evolution, and self-repair."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def run(
        self,
        fault_id: str,
        fault_type: str,
        mitigation: Any,
        action: Any,
        risk_score: float,
        top_signals: tuple[str, ...],
        events: list[dict[str, Any]],
        now: float,
        candidates: list[str] | None = None,
    ) -> tuple[Any, Any]:
        owner = self.owner
        if not (
            mitigation is not None
            and action is not None
            and owner._outcome_tracker is not None
            and owner._learning_engine is not None
        ):
            return None, None
        outcome = self._measure_outcome(fault_id, fault_type, mitigation, risk_score, now, events)
        primary_signal = top_signals[0] if top_signals else "unknown"
        effectiveness = self._validated_effectiveness(fault_type, mitigation, outcome, events)
        stats = self._update_learning(
            fault_id, fault_type, mitigation, outcome, primary_signal, effectiveness, now, events
        )
        if stats is None:
            return None, None
        self._self_play(fault_type, candidates, events)
        policy = self._update_policy(fault_type, stats, events)
        if policy is None:
            self._advance_rollback()
            return stats, None
        stability = self._snapshot_policy(fault_type, policy, events)
        self._blend_policy(fault_type, policy, stability, events)
        self._update_graph(stats, events)
        self._rebalance_objective(fault_type, events)
        self._recover_if_unhealthy(fault_type, policy, stability, events)
        self._advance_rollback()
        return stats, stability

    def _measure_outcome(
        self,
        fault_id: str,
        fault_type: str,
        mitigation: Any,
        risk_score: float,
        now: float,
        events: list[dict[str, Any]],
    ) -> Any:
        outcome = self.owner._outcome_tracker.measure(
            fault_id=fault_id,
            fault_type=fault_type,
            plan_id=mitigation.plan_id,
            strategy=mitigation.strategy,
            pre_risk=risk_score,
            urgency=mitigation.urgency,
            timestamp=now,
        )
        events.append(
            {
                "event_type": EventType.OUTCOME_MEASURED.value,
                "outcome_id": outcome.outcome_id,
                "fault_id": outcome.fault_id,
                "plan_id": outcome.plan_id,
                "strategy": outcome.strategy,
                "pre_risk": outcome.pre_risk,
                "post_risk": outcome.post_risk,
                "risk_delta": outcome.risk_delta,
                "failure_prevented": outcome.failure_prevented,
                "stability_delta": outcome.stability_delta,
            }
        )
        return outcome

    def _validated_effectiveness(
        self, fault_type: str, mitigation: Any, outcome: Any, events: list[dict[str, Any]]
    ) -> float | None:
        validator = self.owner._outcome_validator
        if validator is None or outcome.pre_risk <= 0:
            return None
        simulated = (outcome.pre_risk - outcome.post_risk) / outcome.pre_risk
        real = None
        real_result = validator.call_real_provider(mitigation.strategy, outcome.pre_risk, mitigation.urgency)
        if real_result is not None:
            real = (outcome.pre_risk - real_result[0]) / outcome.pre_risk
        combined, capped = validator.compute_combined_effectiveness(
            sim_effectiveness=simulated,
            real_effectiveness=real,
        )
        if capped:
            events.append(
                {
                    "event_type": EventType.SIMULATION_WEIGHT_CAPPED.value,
                    "fault_type": fault_type,
                    "simulation_weight": validator.simulation_weight,
                    "real_weight": validator.real_weight,
                    "is_real_provider_set": validator.is_real_provider_set(),
                }
            )
        return combined

    def _update_learning(
        self,
        fault_id: str,
        fault_type: str,
        mitigation: Any,
        outcome: Any,
        primary_signal: str,
        effectiveness: float | None,
        now: float,
        events: list[dict[str, Any]],
    ) -> Any:
        owner = self.owner
        record = owner._learning_engine.make_learning_record(
            fault_id=fault_id,
            fault_type=fault_type,
            signal_type=primary_signal,
            strategy=mitigation.strategy,
            risk_delta=outcome.risk_delta,
            pre_risk=outcome.pre_risk,
            success=outcome.risk_delta > 0,
            occurred_at=now,
        )
        stats, _unused = owner._learning_engine.update(record)
        self._record_drift(fault_type, primary_signal, stats, effectiveness, events)
        events.append(
            {
                "event_type": EventType.MITIGATION_EVALUATED.value,
                "learning_id": record.learning_id,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "signal_type": record.signal_type,
                "strategy": record.strategy,
                "effectiveness_score": record.effectiveness_score,
                "success": record.success,
            }
        )
        if stats is not None:
            events.append(
                {
                    "event_type": EventType.STRATEGY_UPDATED.value,
                    "fault_type": stats.fault_type,
                    "signal_type": stats.signal_type,
                    "strategy": stats.strategy,
                    "total_uses": stats.total_uses,
                    "successes": stats.successes,
                    "failures": stats.failures,
                    "avg_effectiveness": stats.avg_effectiveness,
                    "success_rate": stats.success_rate,
                    "disabled": stats.disabled,
                }
            )
        return stats

    def _record_drift(
        self,
        fault_type: str,
        signal_type: str,
        stats: Any,
        effectiveness: float | None,
        events: list[dict[str, Any]],
    ) -> None:
        guard = self.owner._drift_guard
        if guard is None or stats is None or effectiveness is None:
            return
        guard.configure(fault_type, signal_type)
        drift = guard.record(stats.strategy, effectiveness)
        if drift is not None:
            events.append(
                {
                    "event_type": EventType.LEARNING_DRIFT_DETECTED.value,
                    "fault_type": drift.fault_type,
                    "signal_type": drift.signal_type,
                    "metric_value": drift.metric_value,
                    "threshold": drift.threshold,
                    "details": dict(drift.details),
                }
            )

    def _self_play(self, fault_type: str, candidates: list[str] | None, events: list[dict[str, Any]]) -> None:
        owner = self.owner
        if owner._match_engine is None:
            return
        strategies = sorted(
            {
                stats.strategy
                for stats in owner._learning_engine.stats.values()
                if stats.fault_type == fault_type and not stats.disabled
            }
        )
        if len(strategies) < 2 and candidates and len(candidates) >= 2:
            strategies = sorted(set(strategies) | set(candidates))
        for result in owner._match_engine.run_simulated_round(
            fault_type=fault_type,
            candidates=strategies,
            all_stats=owner._learning_engine.stats,
        ):
            events.append({"event_type": EventType.MATCH_PLAYED.value, **result.to_payload()})

    def _update_policy(self, fault_type: str, stats: Any, events: list[dict[str, Any]]) -> Any:
        owner = self.owner
        if owner._policy_store is None:
            return None
        policy = owner._policy_store.update_if_needed(fault_type, owner._learning_engine.stats)
        if policy is not None:
            events.append(
                {
                    "event_type": EventType.POLICY_IMPROVED.value,
                    "fault_type": policy.fault_type,
                    "version": policy.version,
                    "created_at": policy.created_at,
                    "disabled_strategies": sorted(policy.disabled_strategies),
                    "strategy_preferences": dict(policy.strategy_preferences),
                    "urgency_multipliers": dict(policy.urgency_multipliers),
                }
            )
        return policy

    def _snapshot_policy(self, fault_type: str, policy: Any, events: list[dict[str, Any]]) -> Any:
        owner = self.owner
        if owner._snapshot_manager is None:
            return None
        drift_count = owner._health_monitor.get_anomaly_count(fault_type) if owner._health_monitor is not None else 0
        safety_count = (
            owner._health_monitor.get_safety_violations(fault_type) if owner._health_monitor is not None else 0
        )
        stability = None
        if owner._validation_gate is not None:
            stability = owner._validation_gate.compute_stability(
                fault_type=fault_type,
                version=policy.version,
                all_stats=owner._learning_engine.stats,
                drift_events_recent=drift_count,
                safety_violations=safety_count,
            )
            validation = owner._validation_gate.validate(
                fault_type=fault_type,
                version=policy.version,
                all_stats=owner._learning_engine.stats,
                drift_events_recent=drift_count,
                safety_violations=safety_count,
            )
            if not validation.accepted:
                events.append(
                    {
                        "event_type": EventType.POLICY_VALIDATION_FAILED.value,
                        "fault_type": fault_type,
                        "policy_version": policy.version,
                        "stability_score": validation.stability_score,
                        "failure_reasons": list(validation.failure_reasons),
                    }
                )
        score = stability.stability_score if stability is not None else 0.5
        owner._snapshot_manager.take_snapshot(
            fault_type=fault_type,
            version=policy.version,
            stability_score=score,
            stats_snapshot=policy.stats_snapshot,
        )
        events.append(
            {
                "event_type": EventType.POLICY_SNAPSHOTTED.value,
                "snapshot_id": owner._snapshot_manager.get_history(fault_type)[-1].snapshot_id,
                "fault_type": fault_type,
                "policy_version": policy.version,
                "stability_score": score,
            }
        )
        return stability

    def _blend_policy(self, fault_type: str, policy: Any, stability: Any, events: list[dict[str, Any]]) -> None:
        owner = self.owner
        if owner._policy_blender is None or stability is None:
            return
        score = stability.stability_score if hasattr(stability, "stability_score") else 0.5
        history = owner._policy_store.get_history(fault_type)
        if not owner._policy_blender.should_blend(score) or len(history) < 2:
            return
        previous = history[-2]
        result = owner._policy_blender.blend(
            old_policy_id=f"v{previous.version}",
            new_policy_id=f"v{policy.version}",
            fault_type=fault_type,
            old_data={**dict(previous.strategy_preferences), **dict(previous.urgency_multipliers)},
            new_data={**dict(policy.strategy_preferences), **dict(policy.urgency_multipliers)},
            stability_score=score,
        )
        if result is not None:
            events.append(
                {
                    "event_type": EventType.POLICY_BLENDED.value,
                    "old_policy_id": result.old_policy_id,
                    "new_policy_id": result.new_policy_id,
                    "fault_type": result.fault_type,
                    "old_weight": result.old_weight,
                    "new_weight": result.new_weight,
                    "stability_score": result.stability_score,
                }
            )

    def _update_graph(self, stats: Any, events: list[dict[str, Any]]) -> None:
        owner = self.owner
        if owner._learning_graph is None:
            return
        for node_id in ["meta_scorer", "weight_optimizer", "competition_engine"]:
            node = owner._learning_graph.get_node(node_id)
            if node is not None:
                owner._learning_graph.update_performance(node_id, stats.success_rate)
                events.append(
                    {
                        "event_type": EventType.LEARNING_NODE_UPDATED.value,
                        "node_id": node_id,
                        "node_type": node.node_type,
                        "performance": node.performance,
                        "version": node.version,
                    }
                )
        rewrite = owner._graph_rewriter.maybe_rewrite() if owner._graph_rewriter is not None else None
        if rewrite is not None:
            events.append(
                {
                    "event_type": EventType.LEARNING_GRAPH_REWRITTEN.value,
                    "node_id": rewrite.node_id,
                    "param_name": rewrite.param_name,
                    "old_value": rewrite.old_value,
                    "new_value": rewrite.new_value,
                    "delta": rewrite.delta,
                    "triggered_by": rewrite.triggered_by,
                    "version": rewrite.version,
                }
            )

    def _rebalance_objective(self, fault_type: str, events: list[dict[str, Any]]) -> None:
        owner = self.owner
        if owner._objective_evaluator is None:
            return
        stable = owner._oscillation_detector is None or not owner._oscillation_detector.is_oscillating(fault_type)
        result = owner._objective_evaluator.maybe_rebalance(fault_type, stable)
        if result is not None:
            events.append(
                {
                    "event_type": EventType.OBJECTIVE_REBALANCED.value,
                    **make_objective_rebalanced_payload(
                        fault_type=fault_type,
                        safety=result.safety,
                        stability=result.stability,
                        success=result.success,
                        efficiency=result.efficiency,
                        version=result.version,
                    ),
                }
            )

    def _recover_if_unhealthy(self, fault_type: str, policy: Any, stability: Any, events: list[dict[str, Any]]) -> None:
        owner = self.owner
        if owner._health_monitor is None or stability is None or not owner._health_monitor.check(fault_type, stability):
            return
        history = owner._snapshot_manager.get_history(fault_type) if owner._snapshot_manager is not None else []
        plan = (
            owner._rollback_engine.plan_rollback(
                fault_type=fault_type,
                current_version=policy.version,
                history=history,
                stability=stability,
            )
            if owner._rollback_engine is not None
            else None
        )
        if plan is None:
            return
        events.append(
            {
                "event_type": EventType.ROLLBACK_TRIGGERED.value,
                "rollback_id": plan.rollback_id,
                "fault_type": plan.fault_type,
                "from_version": plan.from_version,
                "to_version": plan.to_version,
                "strategy": plan.strategy,
                "triggered_by": plan.triggered_by,
            }
        )
        owner._rollback_engine.execute(plan, owner._policy_store)
        events.append(
            {
                "event_type": EventType.ROLLBACK_COMPLETED.value,
                "rollback_id": plan.rollback_id,
                "fault_type": plan.fault_type,
                "from_version": plan.from_version,
                "to_version": plan.to_version,
                "success": True,
            }
        )
        if owner._recovery_executor is not None:
            recovery = owner._recovery_executor.stabilize(
                fault_type=fault_type,
                plan=plan,
                health_monitor=owner._health_monitor,
                drift_guard=owner._drift_guard,
            )
            events.append(
                {
                    "event_type": EventType.SYSTEM_RECOVERED.value,
                    "recovery_id": recovery.recovery_id,
                    "rollback_id": recovery.rollback_id,
                    "fault_type": recovery.fault_type,
                    "stabilized": recovery.stabilized,
                    "post_recovery_stability": recovery.post_recovery_stability,
                    "cycles_to_stable": recovery.cycles_to_stable,
                }
            )

    def _advance_rollback(self) -> None:
        if self.owner._rollback_engine is not None:
            self.owner._rollback_engine.advance_cycle()
