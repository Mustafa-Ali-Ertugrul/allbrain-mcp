# Sprint 33 World Model Layer

Sprint 33 turns AllBrain from a system that **plans and decides** into a system that also **asks "what if I do this?"** before committing.

The runtime core in Sprint 32 produced a `final_decision` and immediately moved to scheduler execution. The world model layer adds a deterministic what-if simulation step in between, gated by a configurable risk threshold, and feeds the resulting success prediction into the closed-loop learning engine.

## What the world model does

- Represents the current state of the world as a `WorldState` snapshot (user, system, environment, resources).
- Captures a fresh state via `EnvironmentTracker`.
- Predicts the next state of a hypothetical action through `StateTransitionBridge`.
- Scores the action through `PredictionBridge` (success probability, risk, cost, confidence).
- Combines transition and prediction into a `SimulationResult` with a unique `simulation_id`.
- Reconstructs history from the event log through `WorldStateBuilder` and `WorldHistory` (the event log is the only source of truth).

## Architecture

```text
EnvironmentTracker.capture()
        |
        v
    WorldState
        |
        +--> StateTransitionBridge.predict(state, action) --> WorldState (immutable)
        |
        +--> PredictionBridge.evaluate(state, action)    --> Prediction
        |
        v
    SimulationBridge.simulate(state, action) --> SimulationResult
        |
        v
    WorldModel facade
        |
        +--> observe()   -> emits world_state_observed event
        +--> simulate()  -> emits world_simulation_run event
```

## Pipeline integration

The world model plugs into `SystemDecisionPipeline` between the `final_decision` and the scheduler. The new step is gated by two new parameters on `run(...)`:

- `simulate_before_execute: bool = False` (off by default for backward compatibility)
- `risk_threshold: float = 0.7`

When enabled, the pipeline:

1. Captures the current `WorldState` via `world_model.observe()` and emits `world_state_observed`.
2. Derives the world action from `objective["kind"]` (default `"execute"`).
3. Runs `world_model.simulate(action, state)` and emits `world_simulation_run` with `impact_score = prediction.risk`.
4. If `prediction.risk >= risk_threshold`, transitions the runtime state machine to `BLOCKED` with reason `world_simulation_high_risk` and emits `pipeline_run_completed` with `status="BLOCKED"`.
5. Otherwise overrides `execution_plan["predicted_success"]` with `world_simulation["prediction"]["success_probability"]` so the closed-loop learning engine compares the **world model's prediction** against the actual outcome.

This is the first time the world model and the learning engine talk to each other. Future sprints can use `confidence` to weight the `error_delta` and the `model_update_proposal`.

## Event-sourced replay

`WorldStateBuilder` is the projection for world events. It produces:

```python
{
    "observations": [...],     # payload of each world_state_observed event
    "simulations": [...],      # payload of each world_simulation_run event
    "latest_state": {...},     # last observation's payload
    "observation_count": N,
    "simulation_count": M,
}
```

`EventReplayEngine._apply()` routes `world_state_observed` and `world_simulation_run` events into a new `state["world"]` key. The replay equivalence test asserts that `replay(events)["final_state"]["world"]` matches `WorldStateBuilder().build(events)` exactly.

`WorldHistory` is an event-derived query helper. `latest_state()` and `latest_simulation()` re-read the event log and validate the latest payload back into a `WorldState` or `SimulationResult`. No in-memory cache, no drift.

## Components

- `WorldState`, `Prediction`, `SimulationResult`: pydantic `BaseModel(extra="forbid")` with strict `Field(ge=0.0, le=1.0)` bounds on numeric fields and on `confidence` (new in Sprint 33).
- `EnvironmentTracker`: deterministic baseline capture with `datetime.now(timezone.utc)`.
- `StateTransitionBridge`: immutable `model_copy(update=...)` transitions. Input is never mutated. `model_dump(mode="json")` round-trip preserves structure.
- `PredictionBridge`: deterministic rules. `deploy` without `tests` is high risk; with tests is low risk; `run_tests` is well-understood; unknown actions get a default moderate prediction.
- `SimulationBridge`: combines transition and prediction, mints a `uuid7` `simulation_id`.
- `WorldModel` facade: `observe()` and `simulate(action, state)`. Pure compute — no event writing. The pipeline and MCP tool implementations own the event writing.
- `WorldStateBuilder`: projection from event list to world state.
- `WorldHistory`: event-derived query helper.

## New event types

- `world_state_observed` — emitted on every `observe()` call.
- `world_simulation_run` — emitted on every `simulate()` call. `impact_score` is the prediction's `risk`.

Both are added to `EventType` StrEnum and `SemanticEventType` set.

## New MCP tools

- `observe_world(project_path, limit)` — captures a fresh `WorldState` and emits `world_state_observed`.
- `simulate_action(action, project_path, limit)` — captures a fresh state, simulates `action`, emits `world_state_observed` + `world_simulation_run`.

`run_decision_pipeline` gains `simulate_before_execute: bool` and `risk_threshold: float` parameters.

## Test coverage

11 new tests in `tests/test_world.py`:

1. `test_observe_emits_world_state_observed_event` — event is written with the expected payload shape.
2. `test_simulate_emits_world_simulation_run_event` — both observation and simulation events are emitted, payload contains `simulation_id`, `prediction`, `next_state`.
3. `test_prediction_high_risk_for_untested_deploy` — `deploy` on a fresh state yields high risk.
4. `test_simulation_returns_full_simulation_result` — `run_tests` mutates `environment_state["tests"]` to `"passed"`.
5. `test_history_latest_derived_from_events` — `WorldHistory.latest_state()` and `latest_simulation()` round-trip through the event log.
6. `test_transition_immutability` — input `WorldState` is not mutated.
7. `test_replay_world_state_equivalence` — `replay(events)["final_state"]["world"]` matches `WorldStateBuilder().build(events)`.
8. `test_observe_world_impl_stable_json` — MCP impl returns `ToolResult` with `ok=True`.
9. `test_pipeline_simulation_blocks_high_risk` — `simulate_before_execute=True` + `kind="deploy"` + `risk_threshold=0.5` ends the run as `BLOCKED`.
10. `test_pipeline_simulation_feeds_learning_with_world_prediction` — the world `success_probability` overrides `execution_plan["predicted_success"]`.
11. `test_pipeline_default_unchanged_without_simulation` — backward compatibility: no simulation events emitted when `simulate_before_execute=False`.

## Deferral notes

Sprint 34-35 candidates (raised during planning, not implemented in this sprint):

- `action.metadata: dict[str, Any]` for richer action descriptors (target, environment, etc.).
- `payload_version: int` on world events for forward-compatible migrations.
- `test_replay_simulation_prediction_equivalence` for stricter replay parity beyond the builder-level equivalence.

## Sprint 33 outcome

- ✅ World state represented and versioned through events.
- ✅ Environment captured deterministically.
- ✅ Action consequences predicted.
- ✅ Risk analysis with explicit confidence.
- ✅ Future states simulated with a stable `simulation_id`.
- ✅ "What if" runs before execution through `simulate_before_execute`.
- ✅ World model predictions feed the closed-loop learning engine.
- ✅ Replay equivalence: world state derivable from events alone.

The next layer is **counterfactual reasoning**: "what if I had not done this?" and "which alternative is best?".
