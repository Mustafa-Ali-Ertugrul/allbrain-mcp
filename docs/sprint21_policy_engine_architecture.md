# Sprint 21 Policy Engine Architecture

Sprint 21 introduces the Policy Engine: the governance layer that decides whether work may proceed, which constraints apply, when approvals are required, and when execution must escalate. Policies do not execute work. They govern scheduling, deliberation, execution, replanning, and autonomous evolution through auditable decisions.

## Architecture

```text
goal_decomposition / scheduler / execution / evolution
  -> policy_evaluation_requested
  -> Policy Engine
       -> Policy Registry
       -> Context Builder
       -> Rule Evaluator
       -> Decision Aggregator
       -> Enforcement Planner
  -> policy_decision_recorded
  -> allow | deny | require_approval | require_deliberation | escalate | constrain | replan
```

Core components:

- `PolicyRegistry`: stores active and historical policy versions.
- `PolicyContextBuilder`: builds an evaluation context from task risk, confidence, agent profile, memory, meta evaluation, graph state, and requested action.
- `PolicyEvaluator`: evaluates declarative rules against the context.
- `PolicyDecisionAggregator`: resolves multiple matching policies into one decision.
- `EnforcementPlanner`: converts decisions into required actions.
- `PolicyAuditProjector`: exposes policy decisions for replay, dashboards, and compliance.

The event store remains the source of truth. Active policy state is a projection from versioned policy events.

## Policy Model

A policy is a versioned declarative rule set.

```text
Policy
  id
  name
  version
  scope
  status
  priority
  conditions
  actions
  exceptions
  enforcement_mode
  owner
  created_from
  effective_from
  expires_at
```

Policy scopes:

- `task_execution`
- `agent_assignment`
- `scheduler_decision`
- `approval`
- `deployment`
- `replanning`
- `deliberation`
- `self_evolution`
- `autonomous_action`

Condition inputs:

- task risk, priority, type, domain, criticality
- scheduler confidence
- agent suitability and historical performance
- meta evaluation findings
- memory similarity and prior failures
- deliberation disagreement level
- required artifacts, tests, approvals, or reviewers
- policy change risk
- autonomy level requested

Actions:

- `allow`
- `deny`
- `require_approval`
- `require_reviewer`
- `require_supervisor`
- `require_deliberation`
- `require_tests`
- `require_replan`
- `escalate`
- `limit_autonomy`
- `force_manual_gate`
- `apply_scheduler_constraint`

Example policies:

```text
if task.risk > 0.8
  then require_deliberation

if scheduler.confidence < 0.6
  then require_supervisor

if task.kind == deployment
  then require_tests and require_approval

if action.kind == policy_change
  then require_approval

if task.criticality == critical
  then require_reviewer
```

## Evaluation Lifecycle

```text
policy_evaluation_requested
  -> policy_context_built
  -> policy_version_selected
  -> policy_rule_evaluated
  -> policy_decision_recorded
  -> enforcement_action_planned
  -> enforcement_action_completed | enforcement_action_failed
```

Evaluation steps:

1. A system component requests a policy decision.
2. The context builder creates a read-only evaluation context.
3. The policy registry selects effective policies by scope, version, status, and project.
4. Matching policies produce candidate decisions.
5. The aggregator resolves conflicts by severity, priority, specificity, and safety bias.
6. The enforcement planner emits actions for the scheduler, runtime, deliberation, approval flow, or replanning engine.
7. The decision and enforcement outcome are persisted as immutable records.

Policy decisions must include:

- selected policy version
- matching rules
- input context hash
- decision
- required enforcement actions
- confidence
- explanation
- evidence event IDs

## Enforcement Mechanisms

Enforcement should happen at boundaries where irreversible work could start.

Enforcement points:

- before task scheduling
- before agent assignment
- before task execution
- before deployment or external side effects
- before autonomous policy/evolution changes
- after failure, before retry or replan
- before accepting low-confidence recommendations

Enforcement modes:

- `advisory`: emit warning, do not block.
- `soft_block`: require explicit override.
- `hard_block`: execution cannot proceed.
- `approval_gate`: wait for approval event.
- `escalation_gate`: route to supervisor, arbiter, or deliberation.
- `constraint`: modify allowed scheduling or execution options.

The scheduler should consume policy decisions as constraints, not as scores alone. For example, a low-confidence assignment may be eligible by score but blocked until supervision is satisfied.

## Integration Points

- Goal Decomposition: checks whether generated tasks require approvals, tests, reviewers, or deliberation.
- Scheduler: filters candidates, requires supervision, or applies routing constraints.
- Deliberation: triggered by risk, disagreement, low confidence, or policy-sensitive tasks.
- Execution Runtime: blocks unsafe actions, deployments, external writes, or autonomy violations.
- Replay: reconstructs why a task was allowed, denied, escalated, or constrained.
- Observability: traces policy evaluations and enforcement latency.
- Meta Evaluation: evaluates whether policy decisions prevented failures or caused unnecessary friction.
- Organizational Memory: retrieves prior policy outcomes and recurring risk patterns.
- Evolution: proposes policy updates, but Policy Engine governs whether those updates can apply.

## Observability Requirements

Trace shape:

```text
policy.evaluate
  policy.context.build
  policy.registry.select
  policy.rule.evaluate
  policy.decision.aggregate
  policy.enforcement.plan
  policy.enforcement.apply
```

Metrics:

- policy evaluation latency
- decision counts by action
- approval wait time
- escalation rate
- blocked execution count
- override count
- policy conflict count
- false positive policy blocks
- prevented failure count
- policy version effectiveness

Replay should answer:

- Which policy blocked this task?
- Why was deliberation required?
- Why did the scheduler exclude an agent?
- Which approval allowed execution?
- Was a policy decision later judged correct?

## Scalability Considerations

- Compile declarative policies into evaluable rule plans.
- Cache effective policy sets by project, scope, and version.
- Keep policy evaluation stateless and reconstructable.
- Store decisions append-only; use projections for active gates.
- Support policy namespaces for project, organization, department, and global scopes.
- Prefer incremental context building for high-volume scheduling decisions.
- Separate fast path policies from heavyweight evidence-driven policies.
- Use policy priority and specificity to avoid ambiguous rule explosions.
- Keep approval and enforcement state as event-derived projections.

## Design Principle

```text
Policy is the constitutional layer:
it governs autonomy without hiding decisions.
```

The Policy Engine should make AllBrain safer by making every permission, restriction, escalation, and approval explainable, versioned, and replayable.
