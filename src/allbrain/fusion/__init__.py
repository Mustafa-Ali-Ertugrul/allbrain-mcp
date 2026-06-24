from allbrain.fusion.model import (
    FUSION_TEMPLATE_VERSION,
    FUSION_DEFAULT_WEIGHT,
    FUSION_MIN_VARIANCE_EPSILON,
    FUSION_OVERLAP_THRESHOLD,
    FUSION_OVERLAP_PENALTY,
    FUSION_MIN_WEIGHT,
    FUSION_HYSTERESIS,
    FUSION_SOFT_SCALING_FACTOR,
    SignalChannel,
    SignalVector,
    SignalWeights,
    UnifiedScoreState,
)
from allbrain.fusion.calibration import calibrate_signals, normalize_signal, signal_stats
from allbrain.fusion.analyzer import compute_overlap_matrix, detect_overlap_violations, overlap_violation_score
from allbrain.fusion.weights import calibrate_weights, default_weights
from allbrain.fusion.fusion import build_signal_vector, unified_decision_score
from allbrain.fusion.events import make_fusion_payload, make_calibration_payload, validate_fusion, validate_calibration
from allbrain.fusion.reducer import FusionReducer
from allbrain.fusion.manager import FusionManager

__all__ = [
    "FusionManager",
    "FusionReducer",
    "FUSION_TEMPLATE_VERSION",
    "FUSION_DEFAULT_WEIGHT",
    "FUSION_MIN_VARIANCE_EPSILON",
    "FUSION_OVERLAP_THRESHOLD",
    "FUSION_OVERLAP_PENALTY",
    "FUSION_MIN_WEIGHT",
    "FUSION_HYSTERESIS",
    "FUSION_SOFT_SCALING_FACTOR",
    "SignalChannel",
    "SignalVector",
    "SignalWeights",
    "UnifiedScoreState",
    "build_signal_vector",
    "calibrate_signals",
    "calibrate_weights",
    "compute_overlap_matrix",
    "default_weights",
    "detect_overlap_violations",
    "make_calibration_payload",
    "make_fusion_payload",
    "normalize_signal",
    "overlap_violation_score",
    "signal_stats",
    "unified_decision_score",
    "validate_calibration",
    "validate_fusion",
]