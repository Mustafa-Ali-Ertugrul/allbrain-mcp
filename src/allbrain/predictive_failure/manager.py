from __future__ import annotations

import time
from typing import Any

from allbrain.events.schemas import EventType
from allbrain.predictive_failure.model import (
    RiskSignal,
    SIGNAL_TO_FAULT_TYPE,
    LEVEL_FAILURE,
    MITIGATION_STRATEGIES,
    DEFAULT_MITIGATION,
    STRATEGY_URGENCY,
)
from allbrain.predictive_failure.risk_engine import RiskEngine
from allbrain.predictive_failure.predictor import Predictor
from allbrain.predictive_failure.mitigation_planner import MitigationPlanner
from allbrain.predictive_failure.proactive_executor import ProactiveExecutor


class PredictiveFailureManager:
    """Orchestrates the predictive failure pipeline with optional learning.

    Flow:
      1. Emit PREDICTIVE_SIGNAL_DETECTED per signal
      2. Compute risk via RiskEngine → emit FAILURE_RISK_COMPUTED
      3. Predict via Predictor → emit FAILURE_PREDICTED
      4. If FAILURE level: plan mitigation → emit PROACTIVE_MITIGATION_PLANNED
         (optionally uses StrategyOptimizer to override default strategy)
      5. Execute mitigation → emit PROACTIVE_RECOVERY_EXECUTED
      6. If learning enabled: measure outcome → learning update → events
      7. If successful: emit FAILURE_AVOIDED

    Accepts optional drift_detector and learning components.
    """

    def __init__(
        self,
        drift_detector: Any = None,
        *,
        outcome_tracker: Any = None,
        learning_engine: Any = None,
        strategy_optimizer: Any = None,
        policy_store: Any = None,
        explorer: Any = None,
        outcome_validator: Any = None,
        drift_guard: Any = None,
        validation_gate: Any = None,
        health_monitor: Any = None,
        rollback_engine: Any = None,
        snapshot_manager: Any = None,
        recovery_executor: Any = None,
    ) -> None:
        self._risk_engine = RiskEngine()
        self._predictor = Predictor()
        self._planner = MitigationPlanner()
        self._executor = ProactiveExecutor()
        self._drift_detector = drift_detector
        self._outcome_tracker = outcome_tracker
        self._learning_engine = learning_engine
        self._strategy_optimizer = strategy_optimizer
        self._policy_store = policy_store
        self._explorer = explorer
        self._outcome_validator = outcome_validator
        self._drift_guard = drift_guard
        self._validation_gate = validation_gate
        self._health_monitor = health_monitor
        self._rollback_engine = rollback_engine
        self._snapshot_manager = snapshot_manager
        self._recovery_executor = recovery_executor

    def run_cycle(
        self,
        *,
        fault_id: str,
        fault_type: str,
        signals: list[RiskSignal],
    ) -> dict[str, Any]:
        """Run one predictive failure cycle for a fault."""
        events: list[dict[str, Any]] = []
        avoided = False
        now = time.time()

        # 1. Emit signal detected events
        for signal in signals:
            events.append({
                "event_type": EventType.PREDICTIVE_SIGNAL_DETECTED.value,
                "fault_id": fault_id,
                "signal_type": signal.signal_type,
                "severity": signal.severity,
                "frequency": signal.frequency,
            })

        # 2. Compute risk
        risk_map = self._risk_engine.compute_risk(signals)
        if not risk_map:
            return {
                "fault_id": fault_id,
                "fault_type": fault_type,
                "risk_score": 0.0,
                "prediction": None,
                "mitigation": None,
                "action": None,
                "avoided": False,
                "events": events,
            }

        risk_score = risk_map.get(fault_type, 0.0)
        contributing_types = list(dict.fromkeys(
            SIGNAL_TO_FAULT_TYPE.get(s.signal_type, s.signal_type)
            for s in signals
        ))

        # Optional drift detection
        drift_boost = 0.0
        if self._drift_detector is not None:
            self._drift_detector.ingest(fault_type, risk_score)
            drift_boost = self._drift_detector.get_drift_boost(
                fault_type, risk_score,
            )

        effective_risk = min(1.0, risk_score + drift_boost)

        events.append({
            "event_type": EventType.FAILURE_RISK_COMPUTED.value,
            "fault_id": fault_id,
            "fault_type": fault_type,
            "risk_score": risk_score,
            "contributing_signal_types": contributing_types,
            "drift_boost": drift_boost,
        })

        # 3. Predict
        top_signals = tuple(
            s.signal_type
            for s in sorted(signals, key=lambda x: x.severity, reverse=True)[:3]
        )
        prediction = self._predictor.predict(
            fault_id=fault_id,
            fault_type=fault_type,
            risk_score=effective_risk,
            top_signals=top_signals,
        )

        events.append({
            "event_type": EventType.FAILURE_PREDICTED.value,
            "fault_id": fault_id,
            "fault_type": fault_type,
            "probability": prediction.probability,
            "confidence": prediction.confidence,
            "level": prediction.level,
        })

        # 4. Plan mitigation (only at LEVEL_FAILURE)
        #    Optionally use StrategyOptimizer + Explorer to override default
        mitigation = self._planner.plan(prediction)
        optimizer_strategy: str | None = None
        if mitigation is not None and self._strategy_optimizer is not None:
            primary_signal = top_signals[0] if top_signals else "unknown"
            default_strategy = mitigation.strategy
            if hasattr(self._learning_engine, "stats") and self._learning_engine is not None:
                optimizer_strategy = self._strategy_optimizer.recommend(
                    fault_type=fault_type,
                    signal_type=primary_signal,
                    default_strategy=default_strategy,
                    all_stats=self._learning_engine.stats,
                )

                final_strategy = optimizer_strategy
                if self._explorer is not None:
                    candidates = sorted({
                        s.strategy
                        for s in self._learning_engine.stats.values()
                        if s.fault_type == fault_type and s.signal_type == primary_signal
                    })
                    if not candidates:
                        candidates = [optimizer_strategy, default_strategy]
                    decision = self._explorer.select(
                        fault_type=fault_type,
                        signal_type=primary_signal,
                        candidates=candidates,
                        recommended=optimizer_strategy,
                        all_stats=self._learning_engine.stats,
                    )
                    final_strategy = decision.selected_strategy
                    events.append({
                        "event_type": EventType.EXPLORATION_TRIGGERED.value,
                        "fault_type": fault_type,
                        "signal_type": primary_signal,
                        "epsilon": decision.epsilon,
                        "selected_strategy": decision.selected_strategy,
                        "was_exploration": decision.was_exploration,
                    })
                    self._explorer.advance_cycle()

                if final_strategy != default_strategy:
                    from allbrain.predictive_failure.model import MitigationPlan
                    import hashlib
                    urgency = STRATEGY_URGENCY.get(final_strategy, 0.30)
                    import allbrain.predictive_failure.mitigation_planner as mp
                    expected_reduction = mp._clamp(urgency * prediction.probability)
                    plan_id = hashlib.sha256(
                        f"{prediction.fault_id}::{final_strategy}".encode()
                    ).hexdigest()[:16]
                    mitigation = MitigationPlan(
                        plan_id=plan_id,
                        fault_id=prediction.fault_id,
                        fault_type=prediction.fault_type,
                        strategy=final_strategy,
                        urgency=urgency,
                        expected_risk_reduction=expected_reduction,
                    )

        if mitigation is not None:
            events.append({
                "event_type": EventType.PROACTIVE_MITIGATION_PLANNED.value,
                "plan_id": mitigation.plan_id,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "strategy": mitigation.strategy,
                "urgency": mitigation.urgency,
                "expected_risk_reduction": mitigation.expected_risk_reduction,
            })

        # 5. Execute action
        action = None
        if mitigation is not None:
            action = self._executor.execute(mitigation)
            events.append({
                "event_type": EventType.PROACTIVE_RECOVERY_EXECUTED.value,
                "action_id": action.action_id,
                "plan_id": action.plan_id,
                "snapshot_id": action.snapshot_id,
                "success": action.success,
                "message": action.message,
                "rollback_possible": action.rollback_possible,
            })

        # 6. Learning step (after execution, before avoided event)
        learning_outcome_measured = False
        if mitigation is not None and action is not None:
            if self._outcome_tracker is not None and self._learning_engine is not None:
                outcome = self._outcome_tracker.measure(
                    fault_id=fault_id,
                    fault_type=fault_type,
                    plan_id=mitigation.plan_id,
                    strategy=mitigation.strategy,
                    pre_risk=risk_score,
                    urgency=mitigation.urgency,
                    timestamp=now,
                )
                events.append({
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
                })

                primary_signal = top_signals[0] if top_signals else "unknown"

                sim_effectiveness_for_record = None
                if self._outcome_validator is not None and outcome.pre_risk > 0:
                    sim_eff = (
                        (outcome.pre_risk - outcome.post_risk)
                        / outcome.pre_risk
                        if outcome.pre_risk > 0
                        else 0.0
                    )
                    real_eff: float | None = None
                    real_result = self._outcome_validator.call_real_provider(
                        mitigation.strategy,
                        outcome.pre_risk,
                        mitigation.urgency,
                    )
                    if real_result is not None:
                        real_post, _, _ = real_result
                        real_eff = (
                            (outcome.pre_risk - real_post)
                            / outcome.pre_risk
                            if outcome.pre_risk > 0
                            else 0.0
                        )

                    combined_eff, was_capped = (
                        self._outcome_validator.compute_combined_effectiveness(
                            sim_effectiveness=sim_eff,
                            real_effectiveness=real_eff,
                        )
                    )
                    sim_effectiveness_for_record = combined_eff
                    if was_capped:
                        events.append({
                            "event_type": EventType.SIMULATION_WEIGHT_CAPPED.value,
                            "fault_type": fault_type,
                            "simulation_weight": self._outcome_validator.simulation_weight,
                            "real_weight": self._outcome_validator.real_weight,
                            "is_real_provider_set": (
                                self._outcome_validator.is_real_provider_set()
                            ),
                        })

                learning_record = self._learning_engine.make_learning_record(
                    fault_id=fault_id,
                    fault_type=fault_type,
                    signal_type=primary_signal,
                    strategy=mitigation.strategy,
                    risk_delta=outcome.risk_delta,
                    pre_risk=outcome.pre_risk,
                    success=outcome.risk_delta > 0,
                    occurred_at=now,
                )

                stats, _unused = self._learning_engine.update(learning_record)

                if (
                    self._drift_guard is not None
                    and stats is not None
                    and sim_effectiveness_for_record is not None
                ):
                    self._drift_guard.configure(fault_type, primary_signal)
                    drift_event = self._drift_guard.record(
                        stats.strategy,
                        sim_effectiveness_for_record,
                    )
                    if drift_event is not None:
                        events.append({
                            "event_type": EventType.LEARNING_DRIFT_DETECTED.value,
                            "fault_type": drift_event.fault_type,
                            "signal_type": drift_event.signal_type,
                            "metric_value": drift_event.metric_value,
                            "threshold": drift_event.threshold,
                            "details": dict(drift_event.details),
                        })

                events.append({
                    "event_type": EventType.MITIGATION_EVALUATED.value,
                    "learning_id": learning_record.learning_id,
                    "fault_id": fault_id,
                    "fault_type": fault_type,
                    "signal_type": learning_record.signal_type,
                    "strategy": learning_record.strategy,
                    "effectiveness_score": learning_record.effectiveness_score,
                    "success": learning_record.success,
                })

                if stats is not None:
                    events.append({
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
                    })

                    if self._policy_store is not None:
                        policy = self._policy_store.update_if_needed(
                            fault_type,
                            self._learning_engine.stats,
                        )
                        if policy is not None:
                            events.append({
                                "event_type": EventType.POLICY_IMPROVED.value,
                                "fault_type": policy.fault_type,
                                "version": policy.version,
                                "created_at": policy.created_at,
                                "disabled_strategies": sorted(policy.disabled_strategies),
                                "strategy_preferences": dict(policy.strategy_preferences),
                                "urgency_multipliers": dict(policy.urgency_multipliers),
                            })

                            # 6.5 Self-repair: snapshot + validate + health check
                            if self._snapshot_manager is not None:
                                drift_count = (
                                    self._health_monitor.get_anomaly_count(fault_type)
                                    if self._health_monitor is not None else 0
                                )
                                safety_count = (
                                    self._health_monitor.get_safety_violations(fault_type)
                                    if self._health_monitor is not None else 0
                                )
                                stability = None
                                if self._validation_gate is not None:
                                    stability = self._validation_gate.compute_stability(
                                        fault_type=fault_type,
                                        version=policy.version,
                                        all_stats=self._learning_engine.stats,
                                        drift_events_recent=drift_count,
                                        safety_violations=safety_count,
                                    )
                                    val_result = self._validation_gate.validate(
                                        fault_type=fault_type,
                                        version=policy.version,
                                        all_stats=self._learning_engine.stats,
                                        drift_events_recent=drift_count,
                                        safety_violations=safety_count,
                                    )
                                    if not val_result.accepted:
                                        events.append({
                                            "event_type": EventType.POLICY_VALIDATION_FAILED.value,
                                            "fault_type": fault_type,
                                            "policy_version": policy.version,
                                            "stability_score": val_result.stability_score,
                                            "failure_reasons": list(val_result.failure_reasons),
                                        })

                                self._snapshot_manager.take_snapshot(
                                    fault_type=fault_type,
                                    version=policy.version,
                                    stability_score=(
                                        stability.stability_score if stability is not None
                                        else 0.5
                                    ),
                                    stats_snapshot=policy.stats_snapshot,
                                )
                                events.append({
                                    "event_type": EventType.POLICY_SNAPSHOTTED.value,
                                    "snapshot_id": (
                                        self._snapshot_manager.get_history(fault_type)[-1].snapshot_id
                                    ),
                                    "fault_type": fault_type,
                                    "policy_version": policy.version,
                                    "stability_score": (
                                        stability.stability_score if stability is not None
                                        else 0.5
                                    ),
                                })

                            if self._health_monitor is not None and stability is not None:
                                anomaly = self._health_monitor.check(
                                    fault_type, stability,
                                )
                                if anomaly:
                                    history = (
                                        self._snapshot_manager.get_history(fault_type)
                                        if self._snapshot_manager is not None else []
                                    )
                                    plan = None
                                    if self._rollback_engine is not None:
                                        plan = self._rollback_engine.plan_rollback(
                                            fault_type=fault_type,
                                            current_version=policy.version,
                                            history=history,
                                            stability=stability,
                                        )
                                    if plan is not None:
                                        events.append({
                                            "event_type": EventType.ROLLBACK_TRIGGERED.value,
                                            "rollback_id": plan.rollback_id,
                                            "fault_type": plan.fault_type,
                                            "from_version": plan.from_version,
                                            "to_version": plan.to_version,
                                            "strategy": plan.strategy,
                                            "triggered_by": plan.triggered_by,
                                        })
                                        if self._rollback_engine is not None:
                                            self._rollback_engine.execute(
                                                plan, self._policy_store,
                                            )
                                        events.append({
                                            "event_type": EventType.ROLLBACK_COMPLETED.value,
                                            "rollback_id": plan.rollback_id,
                                            "fault_type": plan.fault_type,
                                            "from_version": plan.from_version,
                                            "to_version": plan.to_version,
                                            "success": True,
                                        })
                                        if self._recovery_executor is not None:
                                            recovery = self._recovery_executor.stabilize(
                                                fault_type=fault_type,
                                                plan=plan,
                                                health_monitor=self._health_monitor,
                                                drift_guard=self._drift_guard,
                                            )
                                            events.append({
                                                "event_type": EventType.SYSTEM_RECOVERED.value,
                                                "recovery_id": recovery.recovery_id,
                                                "rollback_id": recovery.rollback_id,
                                                "fault_type": recovery.fault_type,
                                                "stabilized": recovery.stabilized,
                                                "post_recovery_stability": recovery.post_recovery_stability,
                                                "cycles_to_stable": recovery.cycles_to_stable,
                                            })

                if self._rollback_engine is not None:
                    self._rollback_engine.advance_cycle()
        if action is not None and action.success:
            avoided = True
            events.append({
                "event_type": EventType.FAILURE_AVOIDED.value,
                "fault_id": fault_id,
                "original_probability": prediction.probability,
                "mitigation_strategy": mitigation.strategy,
                "snapshot_id": action.snapshot_id,
            })
            if self._drift_detector is not None:
                self._drift_detector.clear(fault_type)

        return {
            "fault_id": fault_id,
            "fault_type": fault_type,
            "risk_score": risk_score,
            "prediction": prediction,
            "mitigation": mitigation,
            "action": action,
            "avoided": avoided,
            "events": events,
        }