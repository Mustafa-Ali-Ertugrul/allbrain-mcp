from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.predictive_failure.model import (
    RiskSignal,
    SIGNAL_TO_FAULT_TYPE,
    LEVEL_FAILURE,
)
from allbrain.predictive_failure.risk_engine import RiskEngine
from allbrain.predictive_failure.predictor import Predictor
from allbrain.predictive_failure.mitigation_planner import MitigationPlanner
from allbrain.predictive_failure.proactive_executor import ProactiveExecutor


class PredictiveFailureManager:
    """Orchestrates the predictive failure pipeline.

    Flow:
      1. Emit PREDICTIVE_SIGNAL_DETECTED per signal
      2. Compute risk via RiskEngine → emit FAILURE_RISK_COMPUTED
      3. Predict via Predictor → emit FAILURE_PREDICTED
      4. If FAILURE level: plan mitigation → emit PROACTIVE_MITIGATION_PLANNED
      5. Execute mitigation → emit PROACTIVE_RECOVERY_EXECUTED
      6. If successful: emit FAILURE_AVOIDED

    Accepts an optional drift_detector for early-warning risk trend analysis.
    """

    def __init__(self, drift_detector: Any = None) -> None:
        self._risk_engine = RiskEngine()
        self._predictor = Predictor()
        self._planner = MitigationPlanner()
        self._executor = ProactiveExecutor()
        self._drift_detector = drift_detector

    def run_cycle(
        self,
        *,
        fault_id: str,
        fault_type: str,
        signals: list[RiskSignal],
    ) -> dict[str, Any]:
        """Run one predictive failure cycle for a fault.

        Args:
            fault_id: The fault identifier.
            fault_type: The fault type string.
            signals: List of observed RiskSignal objects.

        Returns:
            Dict with fields: fault_id, fault_type, risk_score,
            prediction, mitigation, action, avoided, events.
        """
        events: list[dict[str, Any]] = []
        avoided = False

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
        mitigation = self._planner.plan(prediction)
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

        # 6. Failure avoided?
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
