# Sprint 25 Resource Management Architecture

Sprint 25 introduces the Resource Management Layer: the governance-grade capacity and budget system for AllBrain. It unifies token budgets, cost limits, wall-clock time, GPU capacity, provider quotas, retry budgets, and concurrency limits behind an event-sourced reservation ledger.

Resource Management does not replace the scheduler, policy engine, or runtime. It answers a narrower question:

```text
Scheduling decides who should run.
Policy decides whether it may run.
Resource Management decides whether capacity and budget exist to run it now.
```

The design is reservation-first. Work estimates required resources before execution, reserves capacity before admission, records actual usage during and after execution, reconciles estimates against reality, and releases or expires unused reservations through immutable events.

## Architecture

```text
goal_decomposition / scheduler / policy / runtime
  -> resource_estimation_requested
  -> Resource Manager
       -> Budget Registry
       -> Resource Pool Catalog
       -> Admission Controller
       -> Reservation Ledger
       -> Usage Collector
       -> Quota Evaluator
       -> Resource Projector
  -> allow | deny | defer | throttle | downgrade_agent | require_approval | replan
```

Core components:

- `ResourceManager`: central coordinator for estimates, reservations, admission, consumption, reconciliation, and release.
- `BudgetRegistry`: stores versioned budgets by project, goal, workflow, team, agent, provider, task, and policy scope.
- `ResourcePoolCatalog`: describes available resource pools such as tokens, cost, wall-clock time, GPU slots, provider calls, and concurrency.
- `AdmissionController`: decides whether a task may start based on budget, quota, policy, current reservations, and projected usage.
- `ReservationLedger`: append-only ledger of reservation, consumption, release, expiration, violation, and reconciliation records.
- `UsageCollector`: consumes runtime and observability metrics for actual token, cost, time, GPU, retry, and concurrency usage.
- `QuotaEvaluator`: evaluates hard limits, soft limits, rolling windows, over-budget conditions, and override eligibility.
- `ResourceProjector`: builds current available, reserved, consumed, saturated, and violated projections for scheduler and dashboards.

Existing `SafetyWrapper`, `Bulkhead`, lease management, and runtime concurrency remain useful lower-level mechanisms. Sprint 25 elevates them into a coordinated resource governance model.

## Resource Types

The v1 resource taxonomy should be explicit and extensible:

- `tokens.input`
- `tokens.output`
- `cost.usd`
- `time.wall_clock_seconds`
- `gpu.seconds`
- `gpu.slots`
- `concurrency.global`
- `concurrency.agent`
- `concurrency.provider`
- `provider.calls_per_minute`
- `workflow.retry_budget`

Resource scopes:

- global
- project
- goal
- workflow
- milestone
- task
- department
- team
- agent
- provider
- model
- policy scope

Resource windows:

- per call
- per task
- per workflow
- per goal
- per rolling minute
- per rolling hour
- per day
- per billing period
- until manually reset

## Data Models

```text
ResourceBudget
  budget_id
  resource_type
  scope_type
  scope_id
  limit_amount
  reserved_amount
  consumed_amount
  window
  priority
  owner
  policy_refs
  version
  status
```

`ResourceBudget` defines how much of a resource may be used within a scope and time window. Budgets are versioned; historical executions replay against the budget version active at the time.

```text
ResourcePool
  pool_id
  resource_type
  provider
  region
  scope
  capacity
  reserved
  consumed
  available
  saturation
  status
```

`ResourcePool` represents available capacity. Pools may be logical, such as workflow token budget, or physical, such as GPU slots.

```text
ResourceReservation
  reservation_id
  subject_type
  subject_id
  workflow_id
  task_id
  agent_id
  provider
  resource_type
  estimated_amount
  reserved_amount
  ttl_seconds
  expires_at
  status
  decision_id
```

`ResourceReservation` is created before execution. It may be consumed, partially released, expired, denied, or reconciled.

```text
ResourceUsage
  usage_id
  reservation_id
  subject_type
  subject_id
  resource_type
  estimated_amount
  actual_amount
  source
  observed_at
  evidence_refs
```

`ResourceUsage` records observed consumption from runtime, adapter metadata, execution metrics, or observability spans.

```text
ResourceDecision
  decision_id
  subject_type
  subject_id
  requested_resources
  available_resources
  decision
  reason
  confidence
  policy_refs
  alternatives
```

Allowed decisions:

- `allow`
- `deny`
- `defer`
- `throttle`
- `downgrade_agent`
- `require_approval`
- `replan`

```text
ResourceViolation
  violation_id
  subject_type
  subject_id
  reservation_id
  resource_type
  violation_type
  estimated_amount
  actual_amount
  limit_amount
  severity
  policy_refs
  evidence_refs
```

Violation types:

- `limit_exceeded`
- `reservation_expired`
- `unreserved_usage`
- `underestimated_usage`
- `unreconciled_reservation`
- `concurrency_saturation`
- `quota_window_exceeded`

## Lifecycle

```text
resource_estimation_requested
  -> resource_estimated
  -> resource_reservation_requested
  -> resource_reserved
  -> resource_admission_granted | resource_admission_denied
  -> resource_consumed
  -> resource_reconciled
  -> resource_released | resource_reservation_expired
  -> resource_limit_exceeded
```

Normal task execution:

```text
task_ready
  -> estimate tokens/cost/time/provider calls
  -> reserve required resources
  -> admission granted
  -> runtime executes
  -> usage collected
  -> reservation reconciled
  -> unused reservation released
```

Insufficient budget:

```text
resource_reservation_requested
  -> quota evaluator detects insufficient budget
  -> admission denied
  -> policy decides approval, downgrade, defer, or replan
```

Concurrency saturation:

```text
task_ready
  -> concurrency.provider unavailable
  -> admission deferred
  -> scheduler keeps task pending or selects alternate provider/agent
```

GPU slot contention:

```text
gpu.slots requested
  -> no pool capacity available
  -> task deferred or queued behind active reservation
```

Timeout or abandoned reservation:

```text
resource_reserved
  -> no consumption before expires_at
  -> resource_reservation_expired
  -> reserved capacity released
```

Actual usage exceeds estimate:

```text
resource_consumed
  -> actual > reserved
  -> resource_limit_exceeded
  -> violation recorded
  -> meta evaluation reviews estimate quality
```

Downgrade flow:

```text
preferred agent exceeds cost budget
  -> resource decision: downgrade_agent
  -> scheduler chooses cheaper eligible agent
  -> budget saved recorded
```

Budget-aware replanning:

```text
task graph estimate exceeds available goal budget
  -> resource decision: replan
  -> goal decomposition produces cheaper graph or reduced scope
```

## Enforcement

Resource enforcement should happen at every boundary where capacity can be consumed:

- before scheduling finalization
- before task execution starts
- before external provider calls
- before GPU allocation
- before retry
- before high-cost deliberation or self-evolution simulation
- before deployment workflows with multi-step cost and time budgets

Enforcement modes:

- `advisory`: report budget risk without blocking.
- `defer`: delay until capacity is available.
- `throttle`: reduce concurrency or call rate.
- `hard_block`: stop execution until budget changes.
- `approval_gate`: require explicit approval for override.
- `downgrade`: force cheaper model, provider, or agent class.
- `replan`: ask Goal Decomposition to produce a lower-cost graph.

The layer should prefer explicit reservation over implicit consumption. Unreserved usage is always recorded as a violation, even when allowed by emergency policy.

## Integration Points

- Scheduler: consumes resource projections before final assignment, prefers cheaper or faster agents when budget is tight, and defers ready tasks when capacity is unavailable.
- Policy Engine: defines hard limits, approval thresholds, override permissions, autonomy constraints, and budget escalation rules.
- Agent Runtime: requests reservations before execution and reports actual usage afterward. Existing per-call safety checks become a local enforcement mechanism under central resource admission.
- Observability: traces estimate, reserve, admit, consume, reconcile, release, throttle, and violation operations.
- Goal Decomposition: estimates milestone and task graph resource needs; triggers budget-aware replanning when the graph cannot fit available budgets.
- Organization Layer: supports department, team, manager, and specialist pool budgets.
- Meta Evaluation: evaluates over-budget work, poor estimates, wasteful agent choices, and resource policy effectiveness.
- Organizational Memory: retrieves historical resource profiles for similar tasks and improves estimates.
- Self-Evolution: proposes better budget thresholds, cheaper routing, concurrency changes, and estimation model updates.
- Reliability: uses leases and reservation expiration to recover abandoned resources after worker crashes.
- Resilience: uses bulkheads and circuit breakers as enforcement tools for provider or partition-level limits.

## Observability Requirements

Trace shape:

```text
resource.estimate
resource.reserve
resource.admission
resource.consume
resource.reconcile
resource.release
resource.violation
```

Recommended nested trace:

```text
resource.admission
  resource.context.build
  resource.estimate
  resource.quota.evaluate
  resource.pool.check
  resource.reservation.write
  resource.decision.record
```

Metrics:

- reserved vs consumed cost
- token budget utilization
- time budget utilization
- GPU slot utilization
- GPU seconds consumed
- global concurrency saturation
- provider concurrency saturation
- denied task count
- deferred task count
- throttled task count
- over-budget incident count
- reservation expiration count
- unreconciled reservation count
- estimate accuracy
- budget saved by downgrade
- budget saved by replan

Replay should answer:

- Why was this task denied or deferred?
- Which budget or pool was saturated?
- Which resources were reserved before execution?
- How did actual usage compare to estimate?
- Why was an agent downgraded?
- Which unused resources were released after failure?
- Did a resource policy prevent an over-budget execution?

## Acceptance Scenarios

- A high-cost task is denied or routed to approval before execution.
- A low-confidence expensive task triggers deliberation or supervisor approval through policy.
- A ready DAG node waits because provider concurrency is saturated.
- A workflow exceeds estimated output tokens and records a `resource_limit_exceeded` violation.
- A failed task releases unused reservations.
- A deployment workflow reserves time and cost budget across multiple sequential tasks.
- The scheduler chooses a cheaper capable agent when the preferred agent would exceed budget.
- A GPU-backed task reserves a GPU slot before execution and releases it after completion.
- An abandoned reservation expires after worker failure and returns capacity to the pool.

## Scalability Considerations

- Keep the reservation ledger append-only and build fast projections for current availability.
- Partition resource projections by project, provider, team, and resource type.
- Cache active budgets and pool snapshots for high-volume scheduler decisions.
- Use rolling-window counters for provider calls and token budgets.
- Make reservation reconciliation idempotent so retries do not double-count usage.
- Support distributed workers by treating reservations like leases with TTL and recovery.
- Keep physical resource pools, such as GPU slots, separate from logical budgets, such as cost or token limits.
- Allow approximate estimates before execution but require exact observed usage when providers report it.
- Preserve historical budget versions for replay and audit.
- Prefer small local decisions, such as defer or downgrade, before expensive global replanning.

## Design Principle

```text
Resources are not incidental runtime details.
They are first-class organizational constraints.
```

The Resource Management Layer makes AllBrain budget-aware, capacity-aware, and audit-ready. It prevents autonomous execution from silently consuming scarce or expensive resources while still giving the scheduler, policy engine, and evolution layer enough flexibility to choose cheaper, safer, or better-timed alternatives.
