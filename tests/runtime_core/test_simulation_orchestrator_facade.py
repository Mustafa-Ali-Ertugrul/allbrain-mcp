"""Unit tests for SimulationOrchestrator facade delegation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from allbrain.runtime_core.simulation import SimulationOrchestrator


def _make_orchestrator() -> SimulationOrchestrator:
    """Create a SimulationOrchestrator with all mocked engines."""
    return SimulationOrchestrator(
        world=MagicMock(),
        counterfactual=MagicMock(),
        scenarios=MagicMock(),
        foresight=MagicMock(),
        uuid7_generator=MagicMock(return_value="uuid-001"),
    )


class TestSimulationOrchestratorConstruction:
    """Verify the constructor stores all dependencies."""

    def test_constructor_stores_dependencies(self) -> None:
        world = MagicMock()
        cf = MagicMock()
        scenarios = MagicMock()
        foresight = MagicMock()
        uuid7 = MagicMock()

        orchestrator = SimulationOrchestrator(
            world=world,
            counterfactual=cf,
            scenarios=scenarios,
            foresight=foresight,
            uuid7_generator=uuid7,
        )

        assert orchestrator.world is world
        assert orchestrator.counterfactual is cf
        assert orchestrator.scenarios is scenarios
        assert orchestrator.foresight is foresight
        assert orchestrator._uuid7 is uuid7


class TestSimulationOrchestratorSimulationStep:
    """Verify simulation_step exists and delegates through internal dependencies."""

    @patch.object(SimulationOrchestrator, "simulation_step")
    def test_delegates(self, mock_step: MagicMock) -> None:
        orchestrator = _make_orchestrator()
        bus = MagicMock()
        context = MagicMock()

        result = orchestrator.simulation_step(
            bus=bus,
            context=context,
            project_path="/test",
            objective={"action": "test"},
            caused_by="root",
            risk_threshold=0.7,
            limit=500,
        )

        mock_step.assert_called_once_with(
            bus=bus,
            context=context,
            project_path="/test",
            objective={"action": "test"},
            caused_by="root",
            risk_threshold=0.7,
            limit=500,
        )
        assert result == mock_step.return_value


class TestSimulationOrchestratorCounterfactualStep:
    """Verify counterfactual_step exists and delegates through internal dependencies."""

    @patch.object(SimulationOrchestrator, "counterfactual_step")
    def test_delegates(self, mock_step: MagicMock) -> None:
        orchestrator = _make_orchestrator()
        bus = MagicMock()

        result = orchestrator.counterfactual_step(
            bus=bus,
            action="test_action",
            caused_by="root",
            regret_threshold=0.5,
            counterfactual_limit=10,
        )

        mock_step.assert_called_once_with(
            bus=bus,
            action="test_action",
            caused_by="root",
            regret_threshold=0.5,
            counterfactual_limit=10,
        )
        assert result == mock_step.return_value


class TestSimulationOrchestratorForesightStep:
    """Verify foresight_step exists and delegates through internal dependencies."""

    @patch.object(SimulationOrchestrator, "foresight_step")
    def test_delegates(self, mock_step: MagicMock) -> None:
        orchestrator = _make_orchestrator()
        bus = MagicMock()

        result = orchestrator.foresight_step(
            bus=bus,
            action="test_action",
            caused_by="root",
            foresight_limit=5,
            max_horizon=3,
        )

        mock_step.assert_called_once_with(
            bus=bus,
            action="test_action",
            caused_by="root",
            foresight_limit=5,
            max_horizon=3,
        )
        assert result == mock_step.return_value


class TestSimulationOrchestratorScenarioStep:
    """Verify scenario_step exists and delegates through internal dependencies."""

    @patch.object(SimulationOrchestrator, "scenario_step")
    def test_delegates(self, mock_step: MagicMock) -> None:
        orchestrator = _make_orchestrator()
        bus = MagicMock()

        result = orchestrator.scenario_step(
            bus=bus,
            action="test_action",
            caused_by="root",
            scenarios_limit=5,
        )

        mock_step.assert_called_once_with(
            bus=bus,
            action="test_action",
            caused_by="root",
            scenarios_limit=5,
        )
        assert result == mock_step.return_value
