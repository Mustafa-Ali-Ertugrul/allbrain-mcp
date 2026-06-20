# Sprint 32 System Integration & Runtime Core

Sprint 32 turns the Sprint 27-31 control-plane stack into one working decision pipeline.

The goal is not to replace the existing event log, scheduler, replay, memory, workflow, or governance pieces. The goal is to connect them through a deterministic runtime core that can be tested without external agents.

## Runtime Pipeline

```text
input_objective
  -> governance_precheck
  -> economic_evaluation
  -> strategic_planning
  -> goal_decomposition
  -> execution_planning
  -> arbitration_if_needed
  -> final_decision
  -> scheduler_execution
  -> runtime_feedback
  -> closed_loop_learning
```

## Runtime State Machine

```text
INIT
  -> PLANNING
  -> EVALUATION
  -> DECISION
  -> EXECUTION
  -> FEEDBACK
  -> EVOLUTION
  -> COMPLETED
```

Blocked or unsafe decisions transition to `BLOCKED`. Unexpected runtime failures transition to `FAILED`.

## Event-Driven Core

Sprint 32 uses the existing immutable event log as the source of truth. `RuntimeEventBus` is a thin adapter over `BrainRepository.append_event`; it gives the runtime a single publish interface while preserving replayability.

Core runtime events:

- `pipeline_run_started`
- `pipeline_state_changed`
- `objective_received`
- `governance_precheck_completed`
- `economic_evaluation_completed`
- `strategic_plan_created`
- `goal_decomposition_completed`
- `execution_plan_created`
- `arbitration_completed`
- `final_decision_recorded`
- `scheduler_execution_started`
- `runtime_feedback_recorded`
- `prediction_error_detected`
- `model_update_proposed`
- `pipeline_run_completed`
- `pipeline_run_failed`

## Integration Strategy

- Governance uses Sprint 31 `AutonomousGovernanceCoordinator`.
- Economics, strategic planning, decomposition, execution planning, and arbitration are deterministic bridge classes until the Sprint 27-30 architecture layers receive full executable engines.
- Scheduling uses the existing `DeterministicScheduler`.
- Memory fusion wraps the existing `MemoryBuilder` output and groups workflow, economic, execution, arbitration, and governance experience.
- Closed-loop learning compares prediction against outcome and emits proposal events when error is meaningful.

## Execution Modes

- `event_only`: no external agent execution; records planned runtime feedback.
- `mock_runtime`: records deterministic mock execution feedback for tests and local simulation.

## Design Principle

Sprint 27-31 designed the brain. Sprint 32 adds the first working nervous system: event-driven pipeline, runtime state, global memory, and feedback loop.
