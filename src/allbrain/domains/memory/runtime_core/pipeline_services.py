from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from uuid6 import uuid7

from allbrain.domains.analysis.world import WorldModel
from allbrain.domains.governance.governance import AutonomousGovernanceCoordinator
from allbrain.domains.memory.runtime_core.arbitration import ArbitrationBridge
from allbrain.domains.memory.runtime_core.contracts import EconomicEvaluator, StrategicPlanner
from allbrain.domains.memory.runtime_core.economics import EconomicEvaluationBridge
from allbrain.domains.memory.runtime_core.execution import ExecutionPlanningBridge
from allbrain.domains.memory.runtime_core.learning import ClosedLoopLearningEngine
from allbrain.domains.memory.runtime_core.planning import GoalDecompositionBridge, StrategicPlanningBridge
from allbrain.domains.memory.runtime_core.simulation import SimulationOrchestrator
from allbrain.domains.reasoning.counterfactual import CounterfactualEngine
from allbrain.domains.reasoning.foresight import ForesightEngine
from allbrain.domains.reasoning.information_seeking import InformationSeekingManager
from allbrain.domains.reasoning.meta_reasoning import MetaReasoningManager
from allbrain.domains.reasoning.scenarios import ScenarioEngine
from allbrain.domains.reasoning.uncertainty import UncertaintyManager


@dataclass
class PipelineServices:
    """Injectable services used by the live decision pipeline."""

    uuid7_generator: Callable[[], Any]
    governance: AutonomousGovernanceCoordinator
    economics: EconomicEvaluator
    fallback_economics: EconomicEvaluationBridge
    strategy: StrategicPlanner
    fallback_strategy: StrategicPlanningBridge
    decomposition: GoalDecompositionBridge
    execution: ExecutionPlanningBridge
    arbitration: ArbitrationBridge
    learning: ClosedLoopLearningEngine
    simulation: SimulationOrchestrator
    meta_reasoning: MetaReasoningManager
    uncertainty: UncertaintyManager
    information_seeking: InformationSeekingManager
    bridge_timeout_ms: int = 500

    @classmethod
    def defaults(
        cls,
        *,
        economic_evaluator: EconomicEvaluator | None = None,
        strategic_planner: StrategicPlanner | None = None,
        bridge_timeout_ms: int = 500,
    ) -> PipelineServices:
        if bridge_timeout_ms <= 0:
            raise ValueError("bridge_timeout_ms must be positive")
        fallback_economics = EconomicEvaluationBridge()
        fallback_strategy = StrategicPlanningBridge()
        world = WorldModel()
        counterfactual = CounterfactualEngine()
        scenarios = ScenarioEngine()
        foresight = ForesightEngine()
        return cls(
            uuid7_generator=uuid7,
            governance=AutonomousGovernanceCoordinator(),
            economics=economic_evaluator or fallback_economics,
            fallback_economics=fallback_economics,
            strategy=strategic_planner or fallback_strategy,
            fallback_strategy=fallback_strategy,
            decomposition=GoalDecompositionBridge(),
            execution=ExecutionPlanningBridge(),
            arbitration=ArbitrationBridge(),
            learning=ClosedLoopLearningEngine(),
            simulation=SimulationOrchestrator(
                world=world,
                counterfactual=counterfactual,
                scenarios=scenarios,
                foresight=foresight,
                uuid7_generator=uuid7,
            ),
            meta_reasoning=MetaReasoningManager(),
            uncertainty=UncertaintyManager(),
            information_seeking=InformationSeekingManager(),
            bridge_timeout_ms=bridge_timeout_ms,
        )
