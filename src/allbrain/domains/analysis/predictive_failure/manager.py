from __future__ import annotations

import time
from typing import Any

from allbrain.coevolution import CoEvolutionState
from allbrain.domains.analysis.predictive_failure.learning_repair import LearningRepairCoordinator
from allbrain.domains.analysis.predictive_failure.mitigation_planner import MitigationPlanner
from allbrain.domains.analysis.predictive_failure.model import SIGNAL_TO_FAULT_TYPE, RiskSignal
from allbrain.domains.analysis.predictive_failure.predictor import Predictor
from allbrain.domains.analysis.predictive_failure.proactive_executor import ProactiveExecutor
from allbrain.domains.analysis.predictive_failure.risk_engine import RiskEngine
from allbrain.domains.analysis.predictive_failure.strategy_selection import StrategySelectionCoordinator
from allbrain.events.schemas import EventType
from allbrain.meta_optimizer import (
    StabilityController,
    make_meta_optimizer_guarded_payload,
    make_weights_adapated_payload,
)


class PredictiveFailureManager:
    """Backward-compatible facade for prediction, strategy, and repair coordinators."""

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
        dependencies = locals()
        for name, value in dependencies.items():
            if name not in {"self", "dependencies"}:
                setattr(self, f"_{name}", value)
        self._strategy_selection = StrategySelectionCoordinator(self)
        self._learning_repair = LearningRepairCoordinator(self)

    @staticmethod
    def _emit_signal_events(fault_id: str, signals: list[RiskSignal], events: list[dict[str, Any]]) -> None:
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
    ) -> tuple[float, float] | None:
        risk_map = self._risk_engine.compute_risk(signals)
        if not risk_map:
            return None
        risk_score = risk_map.get(fault_type, 0.0)
        contributing = list(
            dict.fromkeys(SIGNAL_TO_FAULT_TYPE.get(signal.signal_type, signal.signal_type) for signal in signals)
        )
        drift_boost = 0.0
        if self._drift_detector is not None:
            self._drift_detector.ingest(fault_type, risk_score)
            drift_boost = self._drift_detector.get_drift_boost(fault_type, risk_score)
        events.append(
            {
                "event_type": EventType.FAILURE_RISK_COMPUTED.value,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "risk_score": risk_score,
                "contributing_signal_types": contributing,
                "drift_boost": drift_boost,
            }
        )
        return risk_score, min(1.0, risk_score + drift_boost)

    def _predict_failure(
        self,
        fault_id: str,
        fault_type: str,
        effective_risk: float,
        signals: list[RiskSignal],
        events: list[dict[str, Any]],
    ) -> tuple[Any, tuple[str, ...]]:
        top_signals = tuple(
            signal.signal_type for signal in sorted(signals, key=lambda item: item.severity, reverse=True)[:3]
        )
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

    def _execute_mitigation(self, mitigation: Any, events: list[dict[str, Any]]) -> Any | None:
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

    def _run_weight_optimizer(self, fault_type: str, stats: Any, stability: Any, events: list[dict[str, Any]]) -> None:
        if self._weight_optimizer is None:
            return
        stability_score = stability.stability_score if stability is not None else 0.5
        gate = StabilityController()
        allowed = gate.allow_update(
            stability_score,
            oscillation_detector=self._oscillation_detector,
            fault_type=fault_type,
        )
        if allowed and stats is not None:
            updated = self._weight_optimizer.step(
                fault_type=fault_type,
                delta_success=stats.success_rate,
                delta_risk=1.0 - stats.avg_effectiveness if stats.avg_effectiveness > 0 else 0.5,
                delta_stability=stability_score,
                delta_drift=1.0 - stats.success_rate,
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
            reason = "stability_below_threshold"
            if self._oscillation_detector is not None and self._oscillation_detector.is_oscillating(fault_type):
                reason = "oscillation_detected"
            events.append(
                {
                    "event_type": EventType.META_OPTIMIZER_GUARDED.value,
                    **make_meta_optimizer_guarded_payload(
                        fault_type=fault_type,
                        reason=reason,
                        stability_score=stability_score,
                    ),
                }
            )

    def _run_coevolution(self, fault_type: str, stats: Any, events: list[dict[str, Any]]) -> None:
        if self._coupling_matrix is None or self._dynamics is None or stats is None:
            return
        state = self._dynamics.step(CoEvolutionState(), policy_update=int(time.time() * 1000) % 2 == 0)
        events.append(
            {
                "event_type": EventType.COEVOLUTION_STATE_UPDATED.value,
                "policy_strength": state.policy_strength,
                "scorer_strength": state.scorer_strength,
                "oscillation_index": state.oscillation_index,
                "cycle": state.cycle,
                "version": state.version,
            }
        )
        if self._oscillation_detector is None:
            return
        self._oscillation_detector.record(fault_type, stats.success_rate - 0.5)
        if self._oscillation_detector.is_oscillating(fault_type):
            events.append(
                {
                    "event_type": EventType.OSCILLATION_DETECTED.value,
                    "fault_type": fault_type,
                    "oscillation_index": self._oscillation_detector.oscillation_index(fault_type),
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
        avoided = action is not None and action.success
        if avoided:
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

    def run_cycle(self, *, fault_id: str, fault_type: str, signals: list[RiskSignal]) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        now = time.time()
        self._emit_signal_events(fault_id, signals, events)
        risk = self._compute_risk(fault_id, fault_type, signals, events)
        if risk is None:
            return self._empty_result(fault_id, fault_type, events)
        risk_score, effective_risk = risk
        prediction, top_signals = self._predict_failure(fault_id, fault_type, effective_risk, signals, events)
        mitigation, candidates = self._strategy_selection.select(fault_id, fault_type, prediction, top_signals, events)
        action = self._execute_mitigation(mitigation, events)
        stats, stability = self._learning_repair.run(
            fault_id,
            fault_type,
            mitigation,
            action,
            risk_score,
            top_signals,
            events,
            now,
            candidates,
        )
        self._run_weight_optimizer(fault_type, stats, stability, events)
        self._run_coevolution(fault_type, stats, events)
        return self._finalize(fault_id, fault_type, prediction, mitigation, action, risk_score, events)

    @staticmethod
    def _empty_result(fault_id: str, fault_type: str, events: list[dict[str, Any]]) -> dict[str, Any]:
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
