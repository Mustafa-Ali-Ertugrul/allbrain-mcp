from __future__ import annotations

from allbrain.arbitration.reducer import ArbitrationReducer
from allbrain.domains.learning.calibration.reducer import CalibrationReducer
from allbrain.domains.analysis.belief.reducer import BeliefReducer
from allbrain.domains.analysis.contradiction.reducer import ContradictionReducer
from allbrain.domains.reasoning.decision.reducer import DecisionReducer
from allbrain.domains.reasoning.objective_system.reducer import ObjectiveSystemReducer
from allbrain.value_alignment.reducer import ValueAlignmentReducer

__all__ = [
    "ArbitrationReducer",
    "BeliefReducer",
    "CalibrationReducer",
    "ContradictionReducer",
    "DecisionReducer",
    "ObjectiveSystemReducer",
    "ValueAlignmentReducer",
]
