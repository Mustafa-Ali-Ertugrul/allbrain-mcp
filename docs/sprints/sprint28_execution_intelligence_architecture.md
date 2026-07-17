# Sprint 28 Execution Intelligence Layer Architecture

Sprint 28 introduces the Execution Intelligence Layer: the optimization layer that decides how feasible, worthwhile, policy-compliant work should be executed.

It sits between Resource Management and Scheduler:

```text
Strategic Planning
  -> Economic Layer
  -> Goal Decomposition
  -> Policy Engine
  -> Resource Management
  -> Execution Intelligence
  -> Scheduler
  -> Runtime / Agents
```

Sprint 28 turns AllBrain from a system that can execute plans into a system that can reason about execution strategy, optimize execution plans, adapt during runtime, and learn which execution strategies work best.

```text
Feasibility -> Execution Strategy -> Execution Plan -> Adaptive Execution
```

Planning decides what to do. Execution Intelligence decides how to do it best and changes that plan when reality disagrees.

## Architecture

```text
goal_ready
  -> Execution Intelligence Layer
       -> ExecutionIntelligenceCoordinator
       -> StrategySelector
       -> PlanOptimizer
       -> ExecutionGraphOptimizer
       -> ParallelizationPlanner
       -> BottleneckAnalyzer
       -> ExecutionSimulator
       -> AdaptiveController
       -> RetryPolicyEngine
       -> RuntimeFeedbackProcessor
  -> optimized execution strategy
  -> scheduler execution start
```

Core components:

- `ExecutionIntelligenceCoordinator`: orchestrates strategy generation, plan creation, simulation, bottleneck analysis, strategy selection, adaptive execution, and post-execution evaluation.
- `StrategySelector`: chooses an execution strategy based on objective, risk, policy, economics, resources, memory, agent performance, and runtime feedback.
- `PlanOptimizer`: optimizes execution plans before scheduler handoff.
- `ExecutionGraphOptimizer`: reorders DAG nodes when dependencies allow and preserves graph correctness.
- `ParallelizationPlanner`: identifies safe parallel expansion, max-parallel recommendations, and concurrency tradeoffs.
- `BottleneckAnalyzer`: detects critical path, slow nodes, overloaded agents, dependency chokepoints, provider latency, and resource bottlenecks.
- `ExecutionSimulator`: estimates latency, cost, risk, failure probability, and tradeoffs before execution starts.
- `AdaptiveController`: changes strategy during execution when actual runtime signals diverge from plan assumptions.
- `RetryPolicyEngine`: decides retry vs replan vs agent swap vs provider switch vs scope reduction.
- `RuntimeFeedbackProcessor`: consumes runtime metrics, failures, retry counts, resource signals, and observability spans.

Execution Intelligence does not directly execute tasks. It produces optimized execution guidance for the Scheduler and Runtime.

## Strategy Types

Execution Intelligence selects strategies, not just agents.

Supported strategy types:

- `fast_path_execution`: optimize for shortest latency when risk and confidence allow.
- `safe_execution`: optimize for review, supervision, lower risk, and conservative sequencing.
- `parallel_maximization`: maximize safe parallelism across independent DAG nodes.
- `cost_minimized_execution`: prefer cheaper agents, providers, retries, and graph paths.
- `risk_averse_execution`: avoid brittle agents, risky providers, deep retry chains, and uncertain adaptations.
- `research_first_execution`: run discovery or validation before committing to expensive execution.
- `retry_tolerant_execution`: accept bounded retry cost when retries historically succeed.
- `adaptive_hybrid_execution`: begin with a balanced strategy and switch dynamically as feedback arrives.

Strategy selection inputs:

- economic ROI and cost-performance tradeoffs
- policy constraints and approval requirements
- resource budget, throttling, and concurrency state
- goal decomposition graph shape
- scheduler candidate agents
- organizational ownership and supervision requirements
- memory of similar execution plans
- meta evaluation of past execution failures
- runtime feedback from active or recent executions

## Data Models

```text
ExecutionStrategy
  strategy_id
  type
  agent_allocation_strategy
  parallelism_level
  retry_behavior
  decomposition_hint
  cost_bias
  speed_bias
  risk_bias
  confidence
  evidence_refs
```

`ExecutionStrategy` describes the high-level execution posture that guides plan optimization and scheduler routing.

```text
ExecutionPlan
  plan_id
  objective_id
  workflow_id
  task_graph_id
  strategy_id
  strategy_type
  execution_graph
  estimated_latency
  estimated_cost
  risk_score
  confidence
  alternative_plans
  status
```

`ExecutionPlan` is the optimized execution representation handed to the scheduler. It may reference the original DAG, but can add execution hints such as preferred ordering, parallelism limits, candidate alternatives, retry behavior, and adaptation thresholds.

```text
ExecutionSimulationResult
  simulation_id
  plan_id
  expected_latency
  expected_cost
  failure_probability
  risk_delta
  resource_pressure
  confidence
  assumptions
  alternative_comparisons
```

`ExecutionSimulationResult` estimates what is likely to happen before execution begins.

```text
BottleneckAnalysis
  analysis_id
  plan_id
  critical_path
  slow_nodes
  dependency_chokepoints
  overloaded_agents
  provider_bottlenecks
  resource_bottlenecks
  parallel_candidates
  reorder_suggestions
  confidence
```

`BottleneckAnalysis` explains where execution is likely to slow down and how the plan can reduce that risk.

```text
ExecutionFeedback
  feedback_id
  plan_id
  step_id
  workflow_id
  task_id
  agent_id
  actual_latency
  actual_cost
  failure_flag
  retry_count
  bottleneck_detected
  resource_pressure
  observed_at
```

`ExecutionFeedback` is the runtime signal stream used by the Adaptive Controller.

```text
ExecutionAdaptationEvent
  event_id
  plan_id
  trigger
  change_type
  before_state
  after_state
  reason
  confidence
  policy_refs
  resource_refs
```

`ExecutionAdaptationEvent` records dynamic execution changes such as agent swap, provider switch, parallelism expansion, retry policy change, replan request, or scope reduction.

```text
ExecutionPerformanceEvaluation
  evaluation_id
  plan_id
  strategy_id
  planned_latency
  actual_latency
  planned_cost
  actual_cost
  planned_risk
  observed_risk
  strategy_success
  adaptation_usefulness
  lessons
```

`ExecutionPerformanceEvaluation` feeds Memory, Meta Evaluation, and Self-Evolution.

## Execution Lifecycle

```text
goal_ready
  -> execution_strategy_generated
  -> execution_plan_created
  -> execution_plan_simulated
  -> execution_bottleneck_analyzed
  -> execution_strategy_selected
  -> scheduler_execution_start
  -> execution_feedback_received
  -> execution_adaptation_triggered
  -> execution_completed
  -> execution_performance_evaluated
```

Detailed flow:

1. Goal Decomposition emits a ready graph or milestone-ready task graph.
2. Policy and Resource Management determine that execution is allowed and feasible.
3. StrategySelector generates candidate execution strategies.
4. PlanOptimizer creates alternative execution plans.
5. ExecutionSimulator estimates latency, cost, risk, and failure probability.
6. BottleneckAnalyzer identifies critical path and likely slowdowns.
7. StrategySelector chooses the best strategy using simulation, policy, economics, resources, and historical evidence.
8. Scheduler consumes execution hints and assigns agents.
9. Runtime emits execution feedback.
10. AdaptiveController reacts to divergence.
11. Execution completes or triggers replan.
12. ExecutionPerformanceEvaluation compares planned vs actual outcomes.

## Dynamic Replanning

Sprint 28's central capability is adaptive execution. Execution can change while the workflow is running.

Examples:

```text
agent slowdown
  -> increase parallelization or swap agent

provider latency spike
  -> provider switch or throttle

cost spike
  -> downgrade agent/model or reduce scope

recurring failure pattern
  -> change retry policy or request DAG replan

critical-path delay
  -> reorder ready nodes or allocate stronger agent
```

Adaptation triggers:

- actual latency exceeds simulated latency threshold
- actual cost exceeds expected cost threshold
- retry count exceeds strategy budget
- resource pressure rises during execution
- provider health degrades
- agent performance diverges from expectation
- bottleneck appears on critical path
- policy or resource constraint changes mid-execution
- memory identifies a known failure pattern

Adaptation actions:

- `retry`
- `stop_retrying`
- `agent_swap`
- `provider_switch`
- `parallel_expansion`
- `parallel_reduction`
- `dag_reorder`
- `scope_reduction`
- `resource_throttle`
- `request_replan`
- `request_deliberation`
- `escalate_to_supervisor`

Every adaptation must be event-sourced, policy-governed, resource-aware, and replayable.

## Bottleneck Analysis

The BottleneckAnalyzer estimates and observes:

- which DAG path is critical
- which node is slow
- which dependency chain blocks progress
- which agent is overloaded
- which provider is slow or degraded
- which resource pool is saturated
- which tasks can be parallelized safely
- which ready nodes should be reordered

Outputs:

```text
critical_path
slow_nodes
dependency_chokepoints
overloaded_agents
provider_bottlenecks
resource_bottlenecks
parallel_candidates
reorder_suggestions
```

The analyzer should distinguish structural bottlenecks from runtime bottlenecks:

- structural bottleneck: caused by DAG shape or dependency design.
- runtime bottleneck: caused by agent, provider, resource, retry, or execution behavior.

Structural bottlenecks may require Goal Decomposition replanning. Runtime bottlenecks may be handled by adaptive execution.

## Execution Simulation

Execution simulation runs before execution starts.

```text
simulate(plan)
  -> expected_latency
  -> expected_cost
  -> failure_probability
  -> risk_delta
  -> resource_pressure
  -> confidence
```

Simulation comparisons:

- expensive-fast vs cheap-slow agents
- high parallelism vs conservative sequencing
- retry-heavy vs replan-first
- single provider vs fallback provider
- safe execution vs fast path
- research-first vs direct execution
- scope-reduced vs full execution

Simulation outputs should preserve assumptions. If assumptions later prove wrong, Self-Evolution can recalibrate strategy selection and simulation models.

## Retry and Recovery Strategy

The RetryPolicyEngine decides whether failure should produce retry, replan, agent swap, provider switch, or escalation.

Decision inputs:

- error type
- retry count
- retry cost
- failure history
- resource pressure
- policy constraints
- task criticality
- memory of similar failures
- agent/provider health
- critical path impact

Decision examples:

```text
transient provider error + low retry cost
  -> retry

same failure repeated across agents
  -> replan DAG

agent-specific timeout
  -> agent swap

provider outage
  -> provider switch

high-risk task failure
  -> deliberate or escalate
```

Retry decisions should be recorded separately from workflow state transitions so replay can explain why a retry was chosen or rejected.

## Integration Points

- Economic Layer: supplies cost-performance and ROI tradeoffs; receives execution efficiency and planned-vs-actual evidence.
- Policy Engine: enforces constraints on adaptive switching, retries, risky execution, scope changes, supervision, and escalation.
- Resource Management: supplies live budget pressure, capacity, throttling, and concurrency state; receives downgrade, throttle, and replan signals.
- Goal Decomposition: receives replan requests when execution graph structure is the root problem.
- Scheduler: consumes selected strategy, optimized graph hints, candidate-agent constraints, max-parallel guidance, and retry posture.
- Runtime / Agents: emits feedback stream for latency, failures, retry count, cost, provider state, and resource usage.
- Deliberation: resolves high-impact strategy disputes, low-confidence adaptations, or repeated failure diagnosis.
- Organizational Memory: retrieves similar execution strategies and stores successful or failed execution patterns.
- Meta Evaluation: evaluates whether selected strategies, adaptations, and retry decisions were correct.
- Self-Evolution: improves strategy selection, retry policy, bottleneck heuristics, parallelization rules, and simulator calibration.
- Observability: traces every strategy, simulation, adaptation, and performance outcome.
- Replay: reconstructs selected strategy, plan changes, feedback, adaptations, and final performance.

## Observability

Trace hierarchy:

```text
execution_intelligence.strategy.generate
execution_intelligence.plan.create
execution_intelligence.simulation.run
execution_intelligence.bottleneck.analyze
execution_intelligence.strategy.select
execution_intelligence.feedback.process
execution_intelligence.adaptation.apply
execution_intelligence.performance.evaluate
```

Metrics:

- execution latency delta
- planned vs actual cost
- planned vs actual risk
- plan efficiency score
- adaptation frequency
- retry vs success ratio
- retry vs replan ratio
- bottleneck frequency
- critical path reduction
- parallelization gain
- agent swap success rate
- provider switch success rate
- simulator accuracy
- strategy success rate by type
- adaptation usefulness

Replay should answer:

- Why was this execution strategy selected?
- Which alternatives were considered?
- What did simulation predict?
- What bottleneck was expected?
- Why did the plan change during execution?
- Why was retry chosen instead of replan?
- Why was the agent or provider switched?
- Did adaptation improve the outcome?
- Which execution strategy should be preferred next time?

## Recommended Events

```text
execution_strategy_generated
execution_plan_created
execution_plan_simulated
execution_bottleneck_analyzed
execution_strategy_selected
execution_feedback_received
execution_adaptation_triggered
execution_plan_revised
execution_retry_decision_recorded
execution_agent_swap_recommended
execution_provider_switch_recommended
execution_parallelization_changed
execution_scope_reduction_recommended
execution_replan_requested
execution_completed
execution_performance_evaluated
```

Event payloads should include stable identifiers when available:

- `objective_id`
- `workflow_id`
- `task_id`
- `node_id`
- `plan_id`
- `strategy_id`
- `simulation_id`
- `analysis_id`
- `agent_id`
- `provider`
- `policy_refs`
- `resource_refs`
- `evidence_refs`

## Acceptance Scenarios

- Expensive-fast vs cheap-slow strategies are compared before execution.
- DAG critical path is identified and reordered where safe.
- Runtime feedback triggers agent swap after slowdown.
- Provider latency spike triggers adaptive provider switch.
- Cost spike triggers downgrade or scope reduction.
- Repeated failure triggers retry-vs-replan decision.
- Critical-path delay causes safe parallel expansion.
- Execution outcomes feed Organizational Memory and Self-Evolution.
- Replay explains why the selected strategy changed during execution.

## Scalability Considerations

- Keep execution plans and adaptations immutable; build current execution state through projections.
- Run expensive simulations asynchronously or only for high-risk/high-cost workflows.
- Cache strategy evaluations for similar task graph shapes.
- Use incremental bottleneck analysis when only part of a DAG changes.
- Limit adaptation frequency to prevent oscillation.
- Require policy approval for high-impact adaptations.
- Keep feedback processing streaming-friendly and idempotent.
- Separate strategic execution decisions from low-level runtime retries.
- Store compact plan summaries with references to full graph snapshots.
- Calibrate simulator models using planned-vs-actual outcomes over time.

## Design Principle

```text
Planning decides what to do.
Execution Intelligence decides how to do it best,
and changes it when reality disagrees.
```

Sprint 28 makes AllBrain an execution optimizer, not merely an executor. It gives the system a runtime-aware execution brain that can choose strategies, simulate outcomes, reduce bottlenecks, adapt to feedback, and improve future execution through memory and self-evolution.
