from allbrain.domains.analysis.contradiction.detector import (
    CONTRADICTION_TEMPLATE_VERSION,
    INCOMPATIBLE_LIFECYCLE,
    SEVERITY_GOAL_DIVERGENCE,
    SEVERITY_LIFECYCLE_INCOMPATIBLE_SAME_GOAL,
    SEVERITY_LIFECYCLE_INCOMPATIBLE_SHARED,
    ContradictionDetector,
    dedup_contradictions,
)
from allbrain.domains.analysis.contradiction.manager import ContradictionManager
from allbrain.domains.analysis.contradiction.models import ContradictionState
from allbrain.domains.analysis.contradiction.reducer import ContradictionReducer

__all__ = [
    "ContradictionDetector",
    "ContradictionManager",
    "ContradictionReducer",
    "ContradictionState",
    "INCOMPATIBLE_LIFECYCLE",
    "SEVERITY_GOAL_DIVERGENCE",
    "SEVERITY_LIFECYCLE_INCOMPATIBLE_SAME_GOAL",
    "SEVERITY_LIFECYCLE_INCOMPATIBLE_SHARED",
    "CONTRADICTION_TEMPLATE_VERSION",
    "dedup_contradictions",
]
