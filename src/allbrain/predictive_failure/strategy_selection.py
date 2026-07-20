from __future__ import annotations

import hashlib
from typing import Any

import allbrain.predictive_failure.mitigation_planner as mitigation_planner
from allbrain.domains.reasoning.objective_system.events import make_objective_updated_payload
from allbrain.domains.reasoning.objective_system.model import FAULT_TYPE_SAFETY_THRESHOLDS
from allbrain.domains.reasoning.objective_system.objective import Objective
from allbrain.domains.reasoning.objective_system.objective_store import ObjectiveStore
from allbrain.domains.reasoning.tradeoff_engine import (
    ParetoAnalyzer,
    UtilityFunction,
    make_tradeoff_analyzed_payload,
    make_utility_computed_payload,
)
from allbrain.events.schemas import EventType
from allbrain.meta_meta_scoring import make_evaluator_profile_updated_payload
from allbrain.policy_competition import PolicyCandidate
from allbrain.predictive_failure.model import STRATEGY_URGENCY, MitigationPlan
from allbrain.value_alignment import AlignmentResult, make_alignment_failed_payload


class ObjectiveTradeoffCoordinator:
    """Evaluate objective trade-offs and value alignment for candidates."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def evaluate(self, fault_type: str, candidates: list[str], events: list[dict[str, Any]]) -> None:
        owner = self.owner
        if not (
            owner._competition_engine is not None
            and owner._objective_evaluator is not None
            and owner._tradeoff_engine is not None
            and owner._tradeoff_selector is not None
            and candidates
        ):
            return
        weights = owner._objective_store.get(fault_type) if owner._objective_store is not None else None
        if weights is None:
            weights = ObjectiveStore().get(fault_type)
        policy_candidates = [
            PolicyCandidate(
                policy_id=f"policy::{fault_type}::{strategy}",
                fault_type=fault_type,
                strategy=strategy,
                policy_data={},
                version=1,
            )
            for strategy in candidates
        ]
        results = [self._evaluate_candidate(fault_type, candidate, weights, events) for candidate in policy_candidates]
        frontier = ParetoAnalyzer.analyze(results)
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
        tradeoff = owner._tradeoff_selector.select(results, frontier)
        self._check_alignment(fault_type, tradeoff.winner, events)

    def _evaluate_candidate(self, fault_type: str, candidate: Any, weights: Any, events: list[dict[str, Any]]) -> Any:
        owner = self.owner
        stats = owner._learning_engine.stats.get((fault_type, fault_type, candidate.strategy))
        objective = Objective.compute(fault_type, candidate.strategy, stats, 0.5, 1)
        owner._objective_evaluator.evaluate(objective)
        events.append(
            {
                "event_type": EventType.OBJECTIVE_UPDATED.value,
                **make_objective_updated_payload(
                    fault_type=fault_type,
                    safety=objective.safety,
                    stability=objective.stability,
                    success=objective.success,
                    efficiency=objective.efficiency,
                    safety_pass=objective.safety_pass,
                ),
            }
        )
        utility = UtilityFunction.compute(objective, weights, candidate.policy_id, candidate.strategy)
        events.append(
            {
                "event_type": EventType.UTILITY_COMPUTED.value,
                **make_utility_computed_payload(
                    policy_id=candidate.policy_id,
                    fault_type=fault_type,
                    utility=utility.utility,
                    safety_pass=utility.safety_pass,
                ),
            }
        )
        return utility

    def _check_alignment(self, fault_type: str, winner: Any, events: list[dict[str, Any]]) -> None:
        owner = self.owner
        if owner._constraint_engine is None or winner is None:
            return
        threshold = FAULT_TYPE_SAFETY_THRESHOLDS.get(fault_type, 0.50)
        score = owner._constraint_engine.check(
            fault_type,
            {"safety": winner.safety, "stability": winner.stability},
            threshold,
        )
        if owner._alignment_tracker is not None:
            owner._alignment_tracker.record(AlignmentResult(score=score, blocked=not score.passed))
        if not score.passed:
            events.append(
                {
                    "event_type": EventType.ALIGNMENT_FAILED.value,
                    **make_alignment_failed_payload(
                        fault_type=fault_type,
                        overall_score=score.overall_score,
                        hard_violations=score.hard_violations,
                        soft_penalties=score.soft_penalties,
                    ),
                }
            )


class StrategySelectionCoordinator:
    """Select, compete, and validate mitigation strategies."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.objectives = ObjectiveTradeoffCoordinator(owner)

    def select(
        self,
        fault_id: str,
        fault_type: str,
        prediction: Any,
        top_signals: tuple[str, ...],
        events: list[dict[str, Any]],
    ) -> tuple[Any | None, list[str]]:
        owner = self.owner
        mitigation = owner._planner.plan(prediction)
        if mitigation is None:
            return None, []
        if owner._strategy_optimizer is None or not (
            owner._learning_engine is not None and hasattr(owner._learning_engine, "stats")
        ):
            self._emit_plan(fault_id, fault_type, mitigation, events)
            return mitigation, []
        primary_signal = top_signals[0] if top_signals else "unknown"
        default_strategy = mitigation.strategy
        selected = owner._strategy_optimizer.recommend(
            fault_type=fault_type,
            signal_type=primary_signal,
            default_strategy=default_strategy,
            all_stats=owner._learning_engine.stats,
        )
        candidates: list[str] = []
        if owner._explorer is not None:
            selected, candidates = self._explore(fault_type, primary_signal, selected, default_strategy, events)
        self.objectives.evaluate(fault_type, candidates, events)
        if selected != default_strategy:
            mitigation = self._replace_mitigation(prediction, selected)
        self._emit_plan(fault_id, fault_type, mitigation, events)
        return mitigation, candidates

    def _explore(
        self,
        fault_type: str,
        signal_type: str,
        recommended: str,
        default_strategy: str,
        events: list[dict[str, Any]],
    ) -> tuple[str, list[str]]:
        owner = self.owner
        candidates = sorted(
            {
                stats.strategy
                for stats in owner._learning_engine.stats.values()
                if stats.fault_type == fault_type and stats.signal_type == signal_type
            }
        ) or [recommended, default_strategy]
        if owner._meta_router is not None:
            route, candidates = owner._meta_router.route(
                fault_type=fault_type,
                signal_type=signal_type,
                all_candidates=candidates,
            )
            events.append(
                {
                    "event_type": EventType.POLICY_FAMILY_SELECTED.value,
                    "family": route.family.name.value,
                    "strategies": list(route.family.strategies),
                    "fault_type": route.fault_type,
                    "signal_type": route.signal_type,
                    "confidence": route.confidence,
                }
            )
        decision = owner._explorer.select(
            fault_type=fault_type,
            signal_type=signal_type,
            candidates=candidates,
            recommended=recommended,
            all_stats=owner._learning_engine.stats,
        )
        events.append(
            {
                "event_type": EventType.EXPLORATION_TRIGGERED.value,
                "fault_type": fault_type,
                "signal_type": signal_type,
                "epsilon": decision.epsilon,
                "selected_strategy": decision.selected_strategy,
                "was_exploration": decision.was_exploration,
            }
        )
        owner._explorer.advance_cycle()
        return self._compete(fault_type, candidates, decision.selected_strategy, events), candidates

    def _compete(self, fault_type: str, candidates: list[str], selected: str, events: list[dict[str, Any]]) -> str:
        owner = self.owner
        if owner._competition_engine is None:
            return selected
        policies = [
            PolicyCandidate(
                policy_id=f"policy::{fault_type}::{strategy}",
                fault_type=fault_type,
                strategy=strategy,
                policy_data={},
                version=1,
            )
            for strategy in candidates
        ]
        result = owner._competition_engine.compete(policies, owner._learning_engine.stats) if policies else None
        if result is None:
            return selected
        events.append(
            {
                "event_type": EventType.COMPETITION_HELD.value,
                "fault_type": fault_type,
                "winner_policy_id": result.winner.candidate.policy_id,
                "winner_strategy": result.winner.candidate.strategy,
                "winner_score": result.winner.score,
                "confidence": result.confidence,
                "candidate_count": len(policies),
            }
        )
        self._score_winner(fault_type, result.winner, events)
        return result.winner.candidate.strategy

    def _score_winner(self, fault_type: str, winner: Any, events: list[dict[str, Any]]) -> None:
        owner = self.owner
        if owner._meta_scorer is None:
            return
        result = owner._meta_scorer.score(
            fault_type=fault_type,
            static_score=winner.score,
            success_rate=winner.success_rate,
            risk_estimate=1.0 - winner.risk_penalty,
            stability_estimate=winner.stability_bonus,
            drift_estimate=winner.drift_penalty,
        )
        if result.override_applied:
            events.append(
                {
                    "event_type": EventType.SCORING_PROFILE_UPDATED.value,
                    **owner._meta_scorer.to_event_payload(result, fault_type),
                }
            )
        if owner._meta_evaluator is None:
            return
        evaluation = owner._meta_evaluator.evaluate(
            evaluator_id=f"meta_scorer::{fault_type}",
            fault_type=fault_type,
            meta_score=result.meta_score,
            outcome_delta=result.meta_score - result.static_score,
        )
        if evaluation.version >= 1:
            events.append(
                {
                    "event_type": EventType.EVALUATOR_PROFILE_UPDATED.value,
                    **make_evaluator_profile_updated_payload(
                        evaluator_id=f"meta_scorer::{fault_type}",
                        fault_type=fault_type,
                        accuracy=evaluation.accuracy,
                        bias=evaluation.bias,
                        stability=0.5,
                        drift_sensitivity=0.1,
                        version=evaluation.version,
                    ),
                }
            )

    @staticmethod
    def _replace_mitigation(prediction: Any, strategy: str) -> MitigationPlan:
        urgency = STRATEGY_URGENCY.get(strategy, 0.30)
        reduction = mitigation_planner._clamp(urgency * prediction.probability)
        plan_id = hashlib.sha256(f"{prediction.fault_id}::{strategy}".encode()).hexdigest()[:16]
        return MitigationPlan(
            plan_id=plan_id,
            fault_id=prediction.fault_id,
            fault_type=prediction.fault_type,
            strategy=strategy,
            urgency=urgency,
            expected_risk_reduction=reduction,
        )

    @staticmethod
    def _emit_plan(fault_id: str, fault_type: str, mitigation: Any, events: list[dict[str, Any]]) -> None:
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

