# Sprint 23 Self-Evolution Architecture

Sprint 23 introduces the Self-Evolution Layer. This layer analyzes historical performance, identifies weaknesses, proposes improvements, simulates changes, evaluates risk, and recommends modifications to AllBrain's policies, scheduler, strategies, confidence models, and organizational structure.

Self-Evolution is advisory-first. It may propose changes, run experiments, and recommend rollouts, but policy and approval gates govern whether changes become active.

## Architecture

```text
events / memory / meta evaluation / observability / policy / scheduler
  -> Evolution Analyzer
  -> Weakness Detector
  -> Improvement Generator
  -> Simulation Engine
  -> Risk Evaluator
  -> Experiment Manager
  -> Approval Workflow
  -> Rollout Manager
  -> Monitoring and Rollback
```

Core components:

- `EvolutionAnalyzer`: scans history for trends, regressions, repeated failures, and improvement opportunities.
- `WeaknessDetector`: identifies weak agents, brittle policies, poor decompositions, low-confidence scheduling, ineffective deliberation, and bad team structures.
- `ImprovementGenerator`: proposes concrete modifications.
- `SimulationEngine`: replays historical cases under proposed changes.
- `RiskEvaluator`: estimates downside, blast radius, confidence, and policy implications.
- `ExperimentManager`: runs shadow, canary, or A/B experiments.
- `ApprovalCoordinator`: requests required approvals through the Policy Engine.
- `RolloutManager`: applies approved changes gradually.
- `RollbackController`: restores previous versions if metrics degrade.

## Evolution Targets

Self-Evolution may propose changes to:

- scheduler weights and eligibility rules
- policy thresholds and enforcement modes
- debate strategies
- goal decomposition strategies
- agent capability weights
- confidence calibration
- memory expiration policies
- team structures and delegation rules
- retry and recovery strategies
- supervision and approval thresholds

Every target must be versioned and rollback-capable.

## Evolution Lifecycle

```text
evolution_cycle_started
  -> historical_performance_analyzed
  -> weakness_identified
  -> improvement_proposed
  -> simulation_started
  -> simulation_completed
  -> risk_evaluated
  -> approval_requested
  -> approval_granted | approval_rejected
  -> experiment_started
  -> experiment_completed
  -> rollout_started
  -> rollout_completed | rollback_started
  -> evolution_cycle_completed
```

Evolution proposal states:

```text
draft
  -> simulated
  -> risk_scored
  -> awaiting_approval
  -> approved | rejected
  -> experimental
  -> rolled_out | rolled_back | retired
```

## Improvement Model

```text
EvolutionProposal
  proposal_id
  target_type
  target_id
  proposed_change
  rationale
  supporting_evidence
  expected_benefit
  risk_score
  confidence
  simulation_result_id
  approval_status
  rollout_plan
  rollback_plan
```

Target types:

- `scheduler_config`
- `policy`
- `debate_strategy`
- `decomposition_strategy`
- `agent_capability`
- `team_structure`
- `memory_policy`
- `confidence_model`
- `recovery_strategy`

Expected benefits:

- higher task success rate
- fewer blocked tasks
- lower retry count
- faster consensus
- better confidence calibration
- reduced policy violations
- improved deployment safety
- better agent utilization

## Simulation Flow

Simulation should replay historical decisions with proposed changes without mutating production state.

```text
proposal_created
  -> simulation_dataset_selected
  -> baseline_replay_run
  -> candidate_replay_run
  -> outcomes_compared
  -> confidence_interval_estimated
  -> simulation_report_recorded
```

Simulation inputs:

- historical task graphs
- scheduler decisions
- policy evaluations
- deliberation sessions
- failure and recovery traces
- memory recommendations
- meta evaluation records
- agent and team performance

Simulation outputs:

- predicted success rate delta
- predicted failure rate delta
- blocked task delta
- escalation delta
- cost and latency impact
- risk change
- confidence calibration impact
- affected domains and agents
- cases where proposed change performs worse

Simulation must preserve counterexamples. A proposal with strong average benefit but critical failures in a narrow domain should not roll out blindly.

## Approval Process

All evolution proposals pass through the Policy Engine.

Approval gates:

- low-risk advisory changes may auto-approve in advisory mode
- scheduler changes require policy approval above a threshold
- policy changes require explicit approval
- autonomy-expanding changes require supervisor or human approval
- deployment-impacting changes require tests and review
- organization restructuring requires manager or executive approval

Approval record:

```text
approval_id
proposal_id
required_by_policy_id
approver_type
approver_id
decision
conditions
expires_at
evidence_refs
```

Rejected proposals should remain in memory as evidence. They may become useful later if conditions change.

## Safety Mechanisms

Required safety controls:

- versioned configurations
- immutable proposal and approval records
- shadow mode before active mode
- canary rollout before broad rollout
- rollback plan before activation
- policy-gated autonomy
- confidence thresholds
- blast radius limits
- domain allowlists
- monitoring windows
- automatic rollback triggers
- human approval for high-risk changes

Rollback triggers:

- success rate regression
- failure rate increase
- policy violation increase
- high-severity incident
- confidence miscalibration
- excessive escalation
- unexpected cost increase
- user or supervisor rejection

Rollback must emit events and restore the prior active version through projections, not by deleting history.

## Experimentation Modes

- `shadow`: evaluate proposed changes without affecting decisions.
- `recommendation_only`: show what would change, but do not enforce.
- `canary`: apply to a small scope, domain, team, or percentage of tasks.
- `parallel_policy`: compare old and new policy decisions side by side.
- `active`: fully applied after approval and successful experiment.

Experiment records should include:

- scope
- start and end conditions
- control version
- candidate version
- metrics tracked
- success criteria
- rollback criteria

## Integration Points

- Scheduler: candidate for weight tuning, eligibility changes, and exploration policy.
- Policy Engine: governs all evolution changes and receives policy improvement proposals.
- Goal Decomposition: learns which decomposition patterns produce successful DAGs.
- Deliberation: learns which debate strategies resolve disagreement effectively.
- Organization Layer: proposes team restructuring, role changes, workload balancing, and escalation chain updates.
- Meta Evaluation: supplies quality judgments, root causes, confidence calibration, and suitability findings.
- Organizational Memory: stores recurring weaknesses, successful improvements, rejected proposals, and rollout outcomes.
- Replay: powers simulations and counterfactual comparisons.
- Observability: monitors experiment health, regressions, and rollback triggers.

## Observability

Trace shape:

```text
self_evolution.cycle
  evolution.history.analyze
  evolution.weakness.detect
  evolution.proposal.generate
  evolution.simulation.run
  evolution.risk.evaluate
  evolution.approval.request
  evolution.experiment.run
  evolution.rollout.apply
  evolution.rollback.apply
```

Metrics:

- proposal count by target
- approval rate
- simulation accuracy
- experiment success rate
- rollout success rate
- rollback rate
- performance delta after rollout
- confidence calibration delta
- prevented failure count
- regressions introduced
- time to improvement

Replay should answer:

- Why was this change proposed?
- What evidence supported it?
- What did simulation predict?
- Who or what approved it?
- How was it rolled out?
- Why was it rolled back?

## Scalability Considerations

- Run heavy simulations asynchronously.
- Use stratified historical samples by domain, risk, and task kind.
- Cache baseline replay results.
- Limit active experiments per domain to avoid attribution confusion.
- Track proposal lineage and supersession.
- Maintain separate control and candidate projections.
- Bound blast radius by project, team, agent, or task class.
- Prefer small, reversible changes over large opaque updates.
- Use organizational memory to avoid rediscovering rejected or harmful proposals.

## Design Principle

```text
Self-evolution is controlled adaptation:
learn from history, simulate before change, approve before rollout, monitor after rollout, rollback when reality disagrees.
```

This layer makes AllBrain capable of improving itself without becoming ungoverned. The Policy Engine defines the boundary of autonomy; Self-Evolution works inside that boundary.
