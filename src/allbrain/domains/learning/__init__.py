"""Learning bounded context — meta-learning and adaptation.

Migrated in v0.4.2 from:
  allbrain.learning → allbrain.domains.learning.learning
  allbrain.learning_graph → allbrain.domains.learning.learning_graph
  allbrain.learning_safety → allbrain.domains.learning.learning_safety
  allbrain.meta_optimizer → allbrain.domains.learning.meta_optimizer
  allbrain.meta_scoring → allbrain.domains.learning.meta_scoring
  allbrain.meta_meta_scoring → allbrain.domains.learning.meta_meta_scoring
  allbrain.meta_policy → allbrain.domains.learning.meta_policy
  allbrain.calibration → allbrain.domains.learning.calibration
  allbrain.capabilities → allbrain.domains.learning.capabilities
  allbrain.evolution → allbrain.domains.learning.evolution
  allbrain.coevolution → allbrain.domains.learning.coevolution
  allbrain.self_play → allbrain.domains.learning.self_play

See docs/ARCHITECTURE.md for the full mapping.
"""

from allbrain.domains.learning.calibration import CalibrationManager, CalibrationReducer
from allbrain.domains.learning.capabilities import CapabilityManager, CapabilityReducer
from allbrain.domains.learning.coevolution import CouplingMatrix, OscillationDetector
from allbrain.domains.learning.evolution import (
    LearningMetrics,
    LearningStateBuilder,
    OrganizationalLearning,
)
from allbrain.domains.learning.learning import CapabilityLearningManager, CapabilityLearningReducer
from allbrain.domains.learning.learning_graph import LearningGraph, NodeRegistry
from allbrain.domains.learning.learning_safety import (
    DriftGuard,
    Explorer,
    LearningSafetyReducer,
)
from allbrain.domains.learning.meta_meta_scoring import (
    EvaluatorStore,
    MetaEvaluator,
    MetaMetaScoringReducer,
)
from allbrain.domains.learning.meta_optimizer import (
    GradientEstimator,
    MetaOptimizerReducer,
    StabilityController,
    WeightOptimizer,
)
from allbrain.domains.learning.meta_policy import MetaPolicyManager, MetaPolicyReducer
from allbrain.domains.learning.meta_scoring import (
    MetaScorer,
    MetaScoringReducer,
    ProfileStore,
)
from allbrain.domains.learning.self_play import MatchEngine, SelfPlayReducer

__all__ = [
    "CalibrationManager",
    "CalibrationReducer",
    "CapabilityManager",
    "CapabilityLearningManager",
    "CapabilityLearningReducer",
    "CapabilityReducer",
    "CouplingMatrix",
    "DriftGuard",
    "EvaluatorStore",
    "Explorer",
    "GradientEstimator",
    "LearningGraph",
    "LearningMetrics",
    "LearningSafetyReducer",
    "LearningStateBuilder",
    "MatchEngine",
    "MetaEvaluator",
    "MetaMetaScoringReducer",
    "MetaOptimizerReducer",
    "MetaPolicyManager",
    "MetaPolicyReducer",
    "MetaScorer",
    "MetaScoringReducer",
    "NodeRegistry",
    "OscillationDetector",
    "OrganizationalLearning",
    "ProfileStore",
    "SelfPlayReducer",
    "StabilityController",
    "WeightOptimizer",
]
