from __future__ import annotations

import time
from typing import Any

from allbrain.events.schemas import EventType
from allbrain.predictive_failure.mitigation_planner import MitigationPlanner
from allbrain.predictive_failure.model import (
    DEFAULT_MITIGATION,
    LEVEL_FAILURE,
    MITIGATION_STRATEGIES,
    SIGNAL_TO_FAULT_TYPE,
    STRATEGY_URGENCY,
    RiskSignal,
)
from allbrain.predictive_failure.predictor import Predictor
from allbrain.predictive_failure.proactive_executor import ProactiveExecutor
from allbrain.predictive_failure.risk_engine import RiskEngine


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
    Supports Sprint72 optional layers:
      - meta_router: policy_routing.MetaPolicyRouter for family-based candidate filtering
      - competition_engine: policy_competition.CompetitionEngine for multi-policy scoring
      - policy_blender: soft_repair.PolicyBlender for stability-weighted blending
      - stability_adapter: soft_repair.StabilityAdapter for blend-or-hard decision
    Supports Sprint73 optional layers:
      - meta_scorer: meta_scoring.MetaScorer for learnable scoring augmentation
      - profile_store: meta_scoring.ProfileStore for per-fault-type scoring profiles
      - match_engine: self_play.MatchEngine for self-play simulation
      - weight_optimizer: meta_optimizer.WeightOptimizer for adaptive weight updates
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
        meta_router: Any = None,
        competition_engine: Any = None,
        policy_blender: Any = None,
        stability_adapter: Any = None,
        meta_scorer: Any = None,
        profile_store: Any = None,
        match_engine: Any = None,
        weight_optimizer: Any = None,
        meta_evaluator: Any = None,
        evaluator_store: Any = None,
        learning_graph: Any = None,
        graph_rewriter: Any = None,
        coupling_matrix: Any = None,
        dynamics: Any = None,
        oscillation_detector: Any = None,
        objective_store: Any = None,
        objective_evaluator: Any = None,
        tradeoff_engine: Any = None,
        tradeoff_selector: Any = None,
        constraint_engine: Any = None,
        alignment_tracker: Any = None,
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
        self._meta_router = meta_router
        self._competition_engine = competition_engine
        self._policy_blender = policy_blender
        self._stability_adapter = stability_adapter
        self._meta_scorer = meta_scorer
        self._profile_store = profile_store
        self._match_engine = match_engine
        self._weight_optimizer = weight_optimizer
        self._meta_evaluator = meta_evaluator
        self._evaluator_store = evaluator_store
        self._learning_graph = learning_graph
        self._graph_rewriter = graph_rewriter
        self._coupling_matrix = coupling_matrix
        self._dynamics = dynamics
        self._oscillation_detector = oscillation_detector
        self._objective_store = objective_store
        self._objective_evaluator = objective_evaluator
        self._tradeoff_engine = tradeoff_engine
        self._tradeoff_selector = tradeoff_selector
        self._constraint_engine = constraint_engine
        self._alignment_tracker = alignment_tracker

    # ------------------------------------------------------------------
    # Extracted pipeline steps
    # ------------------------------------------------------------------

    def _emit_signal_events(
        self,
        fault_id: str,
        signals: list[RiskSignal],
        events: list[dict[str, Any]],
    ) -> None:
        """Emit PREDICTIVE_SIGNAL_DETECTED for each signal."""
        for signal in signals:
            events.append(
                {
                    "event_type": EventType.PREDICTIVE_SIGNAL_DETECTED.value,
                    "fault_id": fault_id,
                    "signal_type": signal.signal_type,
                    "severity": signal.severity,
                    "frequency": signal.frequency,
                }
            )

    def _compute_risk(
        self,
        fault_id: str,
        fault_type: str,
        signals: list[RiskSignal],
        events: list[dict[str, Any]],
    ) -> tuple[float, float, list[str]] | None:
        """Compute risk with optional drift boost.

        Returns (risk_score, effective_risk, contributing_types) or None
        for early exit when risk_map is empty.
        """
        risk_map = self._risk_engine.compute_risk(signals)
        if not risk_map:
            return None

        risk_score = risk_map.get(fault_type, 0.0)
        contributing_types = list(
            dict.fromkeys(SIGNAL_TO_FAULT_TYPE.get(s.signal_type, s.signal_type) for s in signals)
        )

        drift_boost = 0.0
        if self._drift_detector is not None:
            self._drift_detector.ingest(fault_type, risk_score)
            drift_boost = self._drift_detector.get_drift_boost(fault_type, risk_score)

        effective_risk = min(1.0, risk_score + drift_boost)

        events.append(
            {
                "event_type": EventType.FAILURE_RISK_COMPUTED.value,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "risk_score": risk_score,
                "contributing_signal_types": contributing_types,
                "drift_boost": drift_boost,
            }
        )
        return risk_score, effective_risk, contributing_types

    def _predict_failure(
        self,
        fault_id: str,
        fault_type: str,
        effective_risk: float,
        signals: list[RiskSignal],
        events: list[dict[str, Any]],
    ) -> tuple[Any, tuple[str, ...]]:
        """Predict failure probability and return (prediction, top_signals)."""
        top_signals = tuple(s.signal_type for s in sorted(signals, key=lambda x: x.severity, reverse=True)[:3])
        prediction = self._predictor.predict(
            fault_id=fault_id,
            fault_type=fault_type,
            risk_score=effective_risk,
            top_signals=top_signals,
        )
        events.append(
            {
                "event_type": EventType.FAILURE_PREDICTED.value,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "probability": prediction.probability,
                "confidence": prediction.confidence,
                "level": prediction.level,
            }
        )
        return prediction, top_signals

    def _select_strategy(
        self,
        fault_id: str,
        fault_type: str,
        prediction: Any,
        top_signals: tuple[str, ...],
        signals: list[RiskSignal],
        events: list[dict[str, Any]],
        risk_score: float,
    ) -> tuple[Any | None, list[str]]:
        """Plan mitigation and optionally optimise strategy.

        Returns the mitigation plan (or None when prediction is not at failure level).
        """
        mitigation = self._planner.plan(prediction)
        if mitigation is None:
            return None, []

        if self._strategy_optimizer is None:
            events.append(
                {
                    "event_type": EventType.PROACTIVE_MITIGATION_PLANNED.value,
                    "plan_id": mitigation.plan_id,
                    "fault_id": fault_id,
                    "fault_type": fault_type,
                    "strategy": mitigation.strategy,
                    "urgency": mitigation.urgency,
                    "expected_risk_reduction": mitigation.expected_risk_reduction,
                }
            )
            return mitigation, []

        # -- Strategy optimisation path --
        primary_signal = top_signals[0] if top_signals else "unknown"
        default_strategy = mitigation.strategy
        if not (hasattr(self._learning_engine, "stats") and self._learning_engine is not None):
            events.append(
                {
                    "event_type": EventType.PROACTIVE_MITIGATION_PLANNED.value,
                    "plan_id": mitigation.plan_id,
                    "fault_id": fault_id,
                    "fault_type": fault_type,
                    "strategy": mitigation.strategy,
                    "urgency": mitigation.urgency,
                    "expected_risk_reduction": mitigation.expected_risk_reduction,
                }
            )
            return mitigation, []

        optimizer_strategy = self._strategy_optimizer.recommend(
            fault_type=fault_type,
            signal_type=primary_signal,
            default_strategy=default_strategy,
            all_stats=self._learning_engine.stats,
        )
        final_strategy = optimizer_strategy
        candidates: list[str] = []

        if self._explorer is not None:
            candidates = sorted(
                {
                    s.strategy
                    for s in self._learning_engine.stats.values()
                    if s.fault_type == fault_type and s.signal_type == primary_signal
                }
            )
            if not candidates:
                candidates = [optimizer_strategy, default_strategy]

            # Sprint 72: Meta Router — filter by policy family
            if self._meta_router is not None:
                route_decision, candidates = self._meta_router.route(
                    fault_type=fault_type,
                    signal_type=primary_signal,
                    all_candidates=candidates,
                )
                events.append(
                    {
                        "event_type": EventType.POLICY_FAMILY_SELECTED.value,
                        "family": route_decision.family.name.value,
                        "strategies": list(route_decision.family.strategies),
                        "fault_type": route_decision.fault_type,
                        "signal_type": route_decision.signal_type,
                        "confidence": route_decision.confidence,
                    }
                )

            decision = self._explorer.select(
                fault_type=fault_type,
                signal_type=primary_signal,
                candidates=candidates,
                recommended=optimizer_strategy,
                all_stats=self._learning_engine.stats,
            )
            final_strategy = decision.selected_strategy
            events.append(
                {
                    "event_type": EventType.EXPLORATION_TRIGGERED.value,
                    "fault_type": fault_type,
                    "signal_type": primary_signal,
                    "epsilon": decision.epsilon,
                    "selected_strategy": decision.selected_strategy,
                    "was_exploration": decision.was_exploration,
                }
            )
            self._explorer.advance_cycle()

            # Sprint 72: Policy Competition
            if self._competition_engine is not None:
                from allbrain.policy_competition import PolicyCandidate

                comp_candidates = [
                    PolicyCandidate(
                        policy_id=f"policy::{fault_type}::{s}",
                        fault_type=fault_type,
                        strategy=s,
                        policy_data={},
                        version=1,
                    )
                    for s in candidates
                ]
                if comp_candidates:
                    comp_result = self._competition_engine.compete(comp_candidates, self._learning_engine.stats)
                    if comp_result is not None:
                        final_strategy = comp_result.winner.candidate.strategy
                        events.append(
                            {
                                "event_type": EventType.COMPETITION_HELD.value,
                                "fault_type": fault_type,
                                "winner_policy_id": comp_result.winner.candidate.policy_id,
                                "winner_strategy": comp_result.winner.candidate.strategy,
                                "winner_score": comp_result.winner.score,
                                "confidence": comp_result.confidence,
                                "candidate_count": len(comp_candidates),
                            }
                        )

                        # Sprint 73: Meta-Scoring Augmentation
                        if self._meta_scorer is not None:
                            from allbrain.meta_scoring import (
                                make_scoring_profile_updated_payload,
                            )

                            winner_scorer = comp_result.winner
                            meta_result = self._meta_scorer.score(
                                fault_type=fault_type,
                                static_score=winner_scorer.score,
                                success_rate=winner_scorer.success_rate,
                                risk_estimate=1.0 - winner_scorer.risk_penalty,
                                stability_estimate=winner_scorer.stability_bonus,
                                drift_estimate=winner_scorer.drift_penalty,
                            )
                            if meta_result.override_applied:
                                events.append(
                                    {
                                        "event_type": EventType.SCORING_PROFILE_UPDATED.value,
                                        **self._meta_scorer.to_event_payload(meta_result, fault_type),
                                    }
                                )

                            # Sprint 74: Meta-Meta Scoring
                            if self._meta_evaluator is not None:
                                from allbrain.meta_meta_scoring import (
                                    make_evaluator_profile_updated_payload,
                                )

                                mm_result = self._meta_evaluator.evaluate(
                                    evaluator_id=f"meta_scorer::{fault_type}",
                                    fault_type=fault_type,
                                    meta_score=meta_result.meta_score,
                                    outcome_delta=meta_result.meta_score - meta_result.static_score,
                                )
                                if mm_result.version >= 1:
                                    events.append(
                                        {
                                            "event_type": EventType.EVALUATOR_PROFILE_UPDATED.value,
                                            **make_evaluator_profile_updated_payload(
                                                evaluator_id=f"meta_scorer::{fault_type}",
                                                fault_type=fault_type,
                                                accuracy=mm_result.accuracy,
                                                bias=mm_result.bias,
                                                stability=0.5,
                                                drift_sensitivity=0.1,
                                                version=mm_result.version,
                                            ),
                                        }
                                    )

        # Sprint 75: Objective Governance (outside explorer, requires comp_candidates)
        if (
            self._competition_engine is not None
            and self._objective_evaluator is not None
            and self._tradeoff_engine is not None
            and self._tradeoff_selector is not None
            and candidates
        ):
            from allbrain.objective_system import Objective, make_objective_updated_payload
            from allbrain.tradeoff_engine import (
                ParetoAnalyzer,
                UtilityFunction,
                make_tradeoff_analyzed_payload,
                make_utility_computed_payload,
            )

            store = self._objective_store
            weights = store.get(fault_type) if store is not None else None
            if weights is None:
                from allbrain.objective_system import ObjectiveStore

                weights = ObjectiveStore().get(fault_type)

            comp_candidates = [
                PolicyCandidate(
                    policy_id=f"policy::{fault_type}::{s}",
                    fault_type=fault_type,
                    strategy=s,
                    policy_data={},
                    version=1,
                )
                for s in candidates
            ]
            obj_results = []
            for c in comp_candidates:
                key = (fault_type, fault_type, c.strategy)
                s = self._learning_engine.stats.get(key)
                obj = Objective.compute(fault_type, c.strategy, s, 0.5, 1)
                self._objective_evaluator.evaluate(obj)
                events.append(
                    {
                        "event_type": EventType.OBJECTIVE_UPDATED.value,
                        **make_objective_updated_payload(
                            fault_type=fault_type,
                            safety=obj.safety,
                            stability=obj.stability,
                            success=obj.success,
                            efficiency=obj.efficiency,
                            safety_pass=obj.safety_pass,
                        ),
                    }
                )
                u = UtilityFunction.compute(obj, weights, c.policy_id, c.strategy)
                events.append(
                    {
                        "event_type": EventType.UTILITY_COMPUTED.value,
                        **make_utility_computed_payload(
                            policy_id=c.policy_id,
                            fault_type=fault_type,
                            utility=u.utility,
                            safety_pass=u.safety_pass,
                        ),
                    }
                )
                obj_results.append(u)
            frontier = ParetoAnalyzer.analyze(obj_results)
            events.append(
                {
                    "event_type": EventType.TRADEOFF_ANALYZED.value,
                    **make_tradeoff_analyzed_payload(
                        fault_type=fault_type,
                        frontier_size=len(frontier.frontier),
                        dominated_count=len(frontier.dominated),
                    ),
                }
            )
            tradeoff = self._tradeoff_selector.select(obj_results, frontier)
            if tradeoff.winner is not None:
                pass

            # Sprint 75: Value Alignment
            if self._constraint_engine is not None and tradeoff.winner is not None:
                from allbrain.objective_system.model import FAULT_TYPE_SAFETY_THRESHOLDS
                from allbrain.value_alignment import make_alignment_failed_payload

                st = FAULT_TYPE_SAFETY_THRESHOLDS.get(fault_type, 0.50)
                align_score = self._constraint_engine.check(
                    fault_type,
                    {"safety": tradeoff.winner.safety, "stability": tradeoff.winner.stability},
                    st,
                )
                if self._alignment_tracker is not None:
                    from allbrain.value_alignment import AlignmentResult

                    self._alignment_tracker.record(AlignmentResult(score=align_score, blocked=not align_score.passed))
                if not align_score.passed:
                    events.append(
                        {
                            "event_type": EventType.ALIGNMENT_FAILED.value,
                            **make_alignment_failed_payload(
                                fault_type=fault_type,
                                overall_score=align_score.overall_score,
                                hard_violations=align_score.hard_violations,
                                soft_penalties=align_score.soft_penalties,
                            ),
                        }
                    )

        if final_strategy != default_strategy:
            import hashlib

            from allbrain.predictive_failure.model import MitigationPlan

            urgency = STRATEGY_URGENCY.get(final_strategy, 0.30)
            import allbrain.predictive_failure.mitigation_planner as mp

            expected_reduction = mp._clamp(urgency * prediction.probability)
            plan_id = hashlib.sha256(f"{prediction.fault_id}::{final_strategy}".encode()).hexdigest()[:16]
            mitigation = MitigationPlan(
                plan_id=plan_id,
                fault_id=prediction.fault_id,
                fault_type=prediction.fault_type,
                strategy=final_strategy,
                urgency=urgency,
                expected_risk_reduction=expected_reduction,
            )

        events.append(
            {
                "event_type": EventType.PROACTIVE_MITIGATION_PLANNED.value,
                "plan_id": mitigation.plan_id,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "strategy": mitigation.strategy,
                "urgency": mitigation.urgency,
                "expected_risk_reduction": mitigation.expected_risk_reduction,
            }
        )
        return mitigation, candidates

    def _execute_mitigation(
        self,
        mitigation: Any,
        events: list[dict[str, Any]],
    ) -> Any | None:
        """Execute the mitigation plan if one exists."""
        if mitigation is None:
            return None
        action = self._executor.execute(mitigation)
        events.append(
            {
                "event_type": EventType.PROACTIVE_RECOVERY_EXECUTED.value,
                "action_id": action.action_id,
                "plan_id": action.plan_id,
                "snapshot_id": action.snapshot_id,
                "success": action.success,
                "message": action.message,
                "rollback_possible": action.rollback_possible,
            }
        )
        return action

    def _run_learning_and_self_repair(
        self,
        fault_id: str,
        fault_type: str,
        mitigation: Any,
        action: Any,
        risk_score: float,
        prediction: Any,
        top_signals: tuple[str, ...],
        events: list[dict[str, Any]],
        now: float,
        candidates: list[str] | None = None,
    ) -> tuple[Any, Any]:
        """Measure outcome, update learning, self-repair (snapshot/validate/health/blend/graph/rebalance).

        Returns (stats, stability).
        """
        stats: Any = None
        stability: Any = None

        if not (
            mitigation is not None
            and action is not None
            and self._outcome_tracker is not None
            and self._learning_engine is not None
        ):
            return stats, stability

        outcome = self._outcome_tracker.measure(
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

        primary_signal = top_signals[0] if top_signals else "unknown"

        sim_effectiveness_for_record = None
        if self._outcome_validator is not None and outcome.pre_risk > 0:
            sim_eff = (outcome.pre_risk - outcome.post_risk) / outcome.pre_risk if outcome.pre_risk > 0 else 0.0
            real_eff: float | None = None
            real_result = self._outcome_validator.call_real_provider(
                mitigation.strategy,
                outcome.pre_risk,
                mitigation.urgency,
            )
            if real_result is not None:
                real_post, _, _ = real_result
                real_eff = (outcome.pre_risk - real_post) / outcome.pre_risk if outcome.pre_risk > 0 else 0.0

            combined_eff, was_capped = self._outcome_validator.compute_combined_effectiveness(
                sim_effectiveness=sim_eff,
                real_effectiveness=real_eff,
            )
            sim_effectiveness_for_record = combined_eff
            if was_capped:
                events.append(
                    {
                        "event_type": EventType.SIMULATION_WEIGHT_CAPPED.value,
                        "fault_type": fault_type,
                        "simulation_weight": self._outcome_validator.simulation_weight,
                        "real_weight": self._outcome_validator.real_weight,
                        "is_real_provider_set": (self._outcome_validator.is_real_provider_set()),
                    }
                )

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

        if self._drift_guard is not None and stats is not None and sim_effectiveness_for_record is not None:
            self._drift_guard.configure(fault_type, primary_signal)
            drift_event = self._drift_guard.record(
                stats.strategy,
                sim_effectiveness_for_record,
            )
            if drift_event is not None:
                events.append(
                    {
                        "event_type": EventType.LEARNING_DRIFT_DETECTED.value,
                        "fault_type": drift_event.fault_type,
                        "signal_type": drift_event.signal_type,
                        "metric_value": drift_event.metric_value,
                        "threshold": drift_event.threshold,
                        "details": dict(drift_event.details),
                    }
                )

        events.append(
            {
                "event_type": EventType.MITIGATION_EVALUATED.value,
                "learning_id": learning_record.learning_id,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "signal_type": learning_record.signal_type,
                "strategy": learning_record.strategy,
                "effectiveness_score": learning_record.effectiveness_score,
                "success": learning_record.success,
            }
        )

        if stats is None:
            return stats, stability

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

        # -- Self-Play Simulation --
        if self._match_engine is not None:
            sp_candidates = sorted(
                {
                    s.strategy
                    for s in self._learning_engine.stats.values()
                    if s.fault_type == fault_type and not s.disabled
                }
            )
            if len(sp_candidates) < 2 and candidates and len(candidates) >= 2:
                sp_candidates = sorted(set(sp_candidates) | set(candidates))
            sp_results = self._match_engine.run_simulated_round(
                fault_type=fault_type,
                candidates=sp_candidates,
                all_stats=self._learning_engine.stats,
            )
            for sp_result in sp_results:
                events.append(
                    {
                        "event_type": EventType.MATCH_PLAYED.value,
                        **sp_result.to_payload(),
                    }
                )

        if self._policy_store is None:
            if self._rollback_engine is not None:
                self._rollback_engine.advance_cycle()
            return stats, stability

        policy = self._policy_store.update_if_needed(
            fault_type,
            self._learning_engine.stats,
        )
        if policy is None:
            if self._rollback_engine is not None:
                self._rollback_engine.advance_cycle()
            return stats, stability

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

        # -- Self-repair: snapshot --
        if self._snapshot_manager is not None:
            drift_count = self._health_monitor.get_anomaly_count(fault_type) if self._health_monitor is not None else 0
            safety_count = (
                self._health_monitor.get_safety_violations(fault_type) if self._health_monitor is not None else 0
            )
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
                    events.append(
                        {
                            "event_type": EventType.POLICY_VALIDATION_FAILED.value,
                            "fault_type": fault_type,
                            "policy_version": policy.version,
                            "stability_score": val_result.stability_score,
                            "failure_reasons": list(val_result.failure_reasons),
                        }
                    )

            self._snapshot_manager.take_snapshot(
                fault_type=fault_type,
                version=policy.version,
                stability_score=(stability.stability_score if stability is not None else 0.5),
                stats_snapshot=policy.stats_snapshot,
            )
            events.append(
                {
                    "event_type": EventType.POLICY_SNAPSHOTTED.value,
                    "snapshot_id": (self._snapshot_manager.get_history(fault_type)[-1].snapshot_id),
                    "fault_type": fault_type,
                    "policy_version": policy.version,
                    "stability_score": (stability.stability_score if stability is not None else 0.5),
                }
            )

        # Sprint 72: Soft Blend
        if self._policy_blender is not None and stability is not None:
            stbl_score = stability.stability_score if hasattr(stability, "stability_score") else 0.5
            if self._policy_blender.should_blend(stbl_score):
                history = self._policy_store.get_history(fault_type)
                if len(history) >= 2:
                    old_version = history[-2]
                    old_data = {
                        **dict(old_version.strategy_preferences),
                        **dict(old_version.urgency_multipliers),
                    }
                    new_data = {
                        **dict(policy.strategy_preferences),
                        **dict(policy.urgency_multipliers),
                    }
                    blend_result = self._policy_blender.blend(
                        old_policy_id=f"v{old_version.version}",
                        new_policy_id=f"v{policy.version}",
                        fault_type=fault_type,
                        old_data=old_data,
                        new_data=new_data,
                        stability_score=stbl_score,
                    )
                    if blend_result is not None:
                        events.append(
                            {
                                "event_type": EventType.POLICY_BLENDED.value,
                                "old_policy_id": blend_result.old_policy_id,
                                "new_policy_id": blend_result.new_policy_id,
                                "fault_type": blend_result.fault_type,
                                "old_weight": blend_result.old_weight,
                                "new_weight": blend_result.new_weight,
                                "stability_score": blend_result.stability_score,
                            }
                        )

        # Sprint 74: Learning Graph
        if self._learning_graph is not None:
            perf = stats.success_rate if stats is not None else 0.5
            for nid in ["meta_scorer", "weight_optimizer", "competition_engine"]:
                node = self._learning_graph.get_node(nid)
                if node is not None:
                    self._learning_graph.update_performance(nid, perf)
                    events.append(
                        {
                            "event_type": EventType.LEARNING_NODE_UPDATED.value,
                            "node_id": nid,
                            "node_type": node.node_type,
                            "performance": node.performance,
                            "version": node.version,
                        }
                    )
            if self._graph_rewriter is not None:
                rewrite = self._graph_rewriter.maybe_rewrite()
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

        # Sprint 75: Objective Rebalancing
        if self._objective_evaluator is not None:
            osc_low = True
            if self._oscillation_detector is not None:
                osc_low = not self._oscillation_detector.is_oscillating(fault_type)
            reb = self._objective_evaluator.maybe_rebalance(fault_type, osc_low)
            if reb is not None:
                from allbrain.objective_system import (
                    make_objective_rebalanced_payload,
                )

                events.append(
                    {
                        "event_type": EventType.OBJECTIVE_REBALANCED.value,
                        **make_objective_rebalanced_payload(
                            fault_type=fault_type,
                            safety=reb.safety,
                            stability=reb.stability,
                            success=reb.success,
                            efficiency=reb.efficiency,
                            version=reb.version,
                        ),
                    }
                )

        # -- Health check + rollback --
        if self._health_monitor is not None and stability is not None:
            anomaly = self._health_monitor.check(fault_type, stability)
            if anomaly:
                history = self._snapshot_manager.get_history(fault_type) if self._snapshot_manager is not None else []
                plan = None
                if self._rollback_engine is not None:
                    plan = self._rollback_engine.plan_rollback(
                        fault_type=fault_type,
                        current_version=policy.version,
                        history=history,
                        stability=stability,
                    )
                if plan is not None:
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
                    if self._rollback_engine is not None:
                        self._rollback_engine.execute(plan, self._policy_store)
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
                    if self._recovery_executor is not None:
                        recovery = self._recovery_executor.stabilize(
                            fault_type=fault_type,
                            plan=plan,
                            health_monitor=self._health_monitor,
                            drift_guard=self._drift_guard,
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

        if self._rollback_engine is not None:
            self._rollback_engine.advance_cycle()

        return stats, stability

    def _run_weight_optimizer(
        self,
        fault_type: str,
        stats: Any,
        stability: Any,
        events: list[dict[str, Any]],
    ) -> None:
        """Sprint 73: Meta-Optimizer — adapt weights every N cycles."""
        if self._weight_optimizer is None:
            return

        optimizer_stbl = (
            stability.stability_score if (stability is not None and hasattr(stability, "stability_score")) else 0.5
        )
        from allbrain.meta_optimizer import (
            StabilityController,
            make_meta_optimizer_guarded_payload,
            make_weights_adapated_payload,
        )

        gate = StabilityController()
        if gate.allow_update(optimizer_stbl) and stats is not None:
            delta_success = stats.success_rate
            delta_risk = 1.0 - stats.avg_effectiveness if stats.avg_effectiveness > 0 else 0.5
            delta_stability = optimizer_stbl
            delta_drift = 1.0 - stats.success_rate
            updated = self._weight_optimizer.step(
                fault_type=fault_type,
                delta_success=delta_success,
                delta_risk=delta_risk,
                delta_stability=delta_stability,
                delta_drift=delta_drift,
            )
            if updated is not None:
                events.append(
                    {
                        "event_type": EventType.WEIGHTS_ADAPTED.value,
                        **make_weights_adapated_payload(
                            fault_type=fault_type,
                            success_weight=updated.success_weight,
                            risk_weight=updated.risk_weight,
                            stability_weight=updated.stability_weight,
                            drift_weight=updated.drift_weight,
                            version=updated.version,
                        ),
                    }
                )
        elif stats is not None:
            events.append(
                {
                    "event_type": EventType.META_OPTIMIZER_GUARDED.value,
                    **make_meta_optimizer_guarded_payload(
                        fault_type=fault_type,
                        reason="stability_below_threshold",
                        stability_score=optimizer_stbl,
                    ),
                }
            )

    def _run_coevolution(
        self,
        fault_type: str,
        stats: Any,
        events: list[dict[str, Any]],
    ) -> None:
        """Sprint 74: CoEvolution — alternating policy/scorer update with oscillation guard."""
        if self._coupling_matrix is None or self._dynamics is None or stats is None:
            return

        from allbrain.coevolution import CoEvolutionState

        now = time.time()
        cycle_parity = int(now * 1000) % 2 == 0
        coev_state = CoEvolutionState()
        coev_state = self._dynamics.step(coev_state, policy_update=cycle_parity)
        events.append(
            {
                "event_type": EventType.COEVOLUTION_STATE_UPDATED.value,
                "policy_strength": coev_state.policy_strength,
                "scorer_strength": coev_state.scorer_strength,
                "oscillation_index": coev_state.oscillation_index,
                "cycle": coev_state.cycle,
                "version": coev_state.version,
            }
        )
        if self._oscillation_detector is not None:
            self._oscillation_detector.record(
                fault_type,
                stats.success_rate - 0.5 if stats is not None else 0.0,
            )
            if self._oscillation_detector.is_oscillating(fault_type):
                osc_index = self._oscillation_detector.oscillation_index(fault_type)
                events.append(
                    {
                        "event_type": EventType.OSCILLATION_DETECTED.value,
                        "fault_type": fault_type,
                        "oscillation_index": osc_index,
                        "threshold": 0.30,
                        "message": "co-evolution oscillation detected, damping applied",
                    }
                )

    def _finalize(
        self,
        fault_id: str,
        fault_type: str,
        prediction: Any,
        mitigation: Any,
        action: Any,
        risk_score: float,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Emit FAILURE_AVOIDED if successful and return final result dict."""
        avoided = False
        if action is not None and action.success:
            avoided = True
            events.append(
                {
                    "event_type": EventType.FAILURE_AVOIDED.value,
                    "fault_id": fault_id,
                    "original_probability": prediction.probability,
                    "mitigation_strategy": mitigation.strategy,
                    "snapshot_id": action.snapshot_id,
                }
            )
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

    def run_cycle(
        self,
        *,
        fault_id: str,
        fault_type: str,
        signals: list[RiskSignal],
    ) -> dict[str, Any]:
        """Run one predictive failure cycle for a fault."""
        events: list[dict[str, Any]] = []
        now = time.time()

        # 1. Emit signal detected events
        self._emit_signal_events(fault_id, signals, events)

        # 2. Compute risk (may early-return if risk_map is empty)
        risk_out = self._compute_risk(fault_id, fault_type, signals, events)
        if risk_out is None:
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
        risk_score, effective_risk, _contributing_types = risk_out

        # 3. Predict
        prediction, top_signals = self._predict_failure(fault_id, fault_type, effective_risk, signals, events)

        # 4. Plan / optimise mitigation strategy
        mitigation, candidates = self._select_strategy(
            fault_id,
            fault_type,
            prediction,
            top_signals,
            signals,
            events,
            risk_score,
        )

        # 5. Execute mitigation
        action = self._execute_mitigation(mitigation, events)

        # 6. Learning + self-repair (outcome, snapshot, blend, graph, rebalance, health)
        stats, stability = self._run_learning_and_self_repair(
            fault_id,
            fault_type,
            mitigation,
            action,
            risk_score,
            prediction,
            top_signals,
            events,
            now,
            candidates,
        )

        # 7. Meta-optimizer (every N cycles)
        self._run_weight_optimizer(fault_type, stats, stability, events)

        # 8. Co-evolution
        self._run_coevolution(fault_type, stats, events)

        # 9. Finalize
        return self._finalize(fault_id, fault_type, prediction, mitigation, action, risk_score, events)
