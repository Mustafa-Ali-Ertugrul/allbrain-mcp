from allbrain.domains.analysis.attribution.allocator import allocate_credit, redistribute_below_min
from allbrain.domains.analysis.attribution.counterfactual import estimate_signal_impact
from allbrain.domains.analysis.attribution.estimator import (
    initial_signal_counts,
    initial_signal_rewards,
    update_signal_count,
    update_signal_reward,
)
from allbrain.domains.analysis.attribution.events import (
    make_attribution_update_payload,
    make_credit_payload,
    make_importance_payload,
    validate_attribution_update,
    validate_credit,
    validate_importance,
)
from allbrain.domains.analysis.attribution.manager import AttributionManager
from allbrain.domains.analysis.attribution.matrix import build_signal_matrix, detect_importance_change
from allbrain.domains.analysis.attribution.model import (
    ATTRIBUTION_CF_CONFIDENCE,
    ATTRIBUTION_CONFIDENCE_ALPHA,
    ATTRIBUTION_COUNTERFACTUAL_INTERVAL,
    ATTRIBUTION_COUNTERFACTUAL_WEIGHT,
    ATTRIBUTION_DECAY,
    ATTRIBUTION_HYSTERESIS,
    ATTRIBUTION_IMPORTANCE_THRESHOLD,
    ATTRIBUTION_MIN_CONTRIBUTION,
    ATTRIBUTION_PROPORTIONAL_WEIGHT,
    ATTRIBUTION_TEMPLATE_VERSION,
    AttributionResult,
    AttributionSignal,
    AttributionState,
    CreditAllocation,
)
from allbrain.domains.analysis.attribution.reducer import AttributionReducer

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
