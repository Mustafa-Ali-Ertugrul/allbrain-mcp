from allbrain.attribution.model import (
    ATTRIBUTION_TEMPLATE_VERSION,
    ATTRIBUTION_MIN_CONTRIBUTION,
    ATTRIBUTION_CONFIDENCE_ALPHA,
    ATTRIBUTION_COUNTERFACTUAL_WEIGHT,
    ATTRIBUTION_PROPORTIONAL_WEIGHT,
    ATTRIBUTION_CF_CONFIDENCE,
    ATTRIBUTION_COUNTERFACTUAL_INTERVAL,
    ATTRIBUTION_IMPORTANCE_THRESHOLD,
    ATTRIBUTION_HYSTERESIS,
    ATTRIBUTION_DECAY,
    AttributionSignal,
    CreditAllocation,
    AttributionResult,
    AttributionState,
)
from allbrain.attribution.allocator import allocate_credit, redistribute_below_min
from allbrain.attribution.counterfactual import estimate_signal_impact
from allbrain.attribution.estimator import update_signal_reward, update_signal_count, initial_signal_rewards, initial_signal_counts
from allbrain.attribution.matrix import build_signal_matrix, detect_importance_change
from allbrain.attribution.events import (
    make_credit_payload, make_attribution_update_payload, make_importance_payload,
    validate_credit, validate_attribution_update, validate_importance,
)
from allbrain.attribution.reducer import AttributionReducer
from allbrain.attribution.manager import AttributionManager

__all__ = [
    "AttributionManager",
    "AttributionReducer",
    "ATTRIBUTION_TEMPLATE_VERSION",
    "ATTRIBUTION_MIN_CONTRIBUTION",
    "ATTRIBUTION_CONFIDENCE_ALPHA",
    "ATTRIBUTION_COUNTERFACTUAL_WEIGHT",
    "ATTRIBUTION_PROPORTIONAL_WEIGHT",
    "ATTRIBUTION_CF_CONFIDENCE",
    "ATTRIBUTION_COUNTERFACTUAL_INTERVAL",
    "ATTRIBUTION_IMPORTANCE_THRESHOLD",
    "ATTRIBUTION_HYSTERESIS",
    "ATTRIBUTION_DECAY",
    "AttributionSignal",
    "CreditAllocation",
    "AttributionResult",
    "AttributionState",
    "allocate_credit",
    "build_signal_matrix",
    "detect_importance_change",
    "estimate_signal_impact",
    "initial_signal_counts",
    "initial_signal_rewards",
    "make_attribution_update_payload",
    "make_credit_payload",
    "make_importance_payload",
    "redistribute_below_min",
    "update_signal_count",
    "update_signal_reward",
    "validate_attribution_update",
    "validate_credit",
    "validate_importance",
]