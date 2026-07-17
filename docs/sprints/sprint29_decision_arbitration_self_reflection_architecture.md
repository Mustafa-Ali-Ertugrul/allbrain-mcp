# Sprint 29 Decision Arbitration & Self-Reflection Architecture

Sprint 29 introduces the Decision Arbitration & Self-Reflection Layer: the system that resolves cross-layer decision conflicts, interprets policies under ambiguity, and continuously improves AllBrain's decision quality.

This layer acts as a referee, teacher, and reflex system across Strategic Planning, Economic Layer, Policy Engine, Resource Management, Execution Intelligence, Deliberation, and Self-Evolution.

```text
Strategic Planning
  -> Economic Layer
  -> Goal Decomposition
  -> Policy Engine
  -> Resource Management
  -> Execution Intelligence
  -> Scheduler
  -> Runtime

            ^
            |
 Sprint 29 Decision Arbitration & Self-Reflection
 Deliberation + Self-Evolution Feedback Loop
```

Sprint 29 is not a replacement for policy, economics, or execution intelligence. It exists for the moments when their outputs conflict:

```text
Economics says high value.
Policy says risky.
Resource Management says feasible but expensive.
Execution Intelligence says possible but fragile.

Decision Arbitration decides what truth to act on under conflict.
```

## Architecture

```text
decision_conflict_detected
  -> DeliberationCoordinator
       -> PolicyConflictResolver
       -> EconomicPolicyBalancer
       -> ExecutionFeasibilityJudge
       -> RiskTradeoffAnalyzer
       -> SelfReflectionEngine
       -> DecisionSynthesizer
       -> LearningSignalGenerator
  -> final_decision
  -> policy_update_suggestions
  -> self_evolution_pipeline
```

Core components:

- `DeliberationCoordinator`: collects conflicting decisions and orchestrates multi-layer evaluation.
- `PolicyConflictResolver`: resolves policy-vs-policy conflicts, hard vs soft constraints, override chains, and ambiguous policy interpretation.
- `EconomicPolicyBalancer`: balances ROI, expected value, opportunity cost, risk, policy constraints, and strategic urgency.
- `ExecutionFeasibilityJudge`: evaluates whether the proposed execution path is likely to work given bottlenecks, adaptation risk, resource pressure, and runtime history.
- `RiskTradeoffAnalyzer`: synthesizes value, risk, feasibility, uncertainty, and organizational constraints.
- `SelfReflectionEngine`: compares similar historical decisions against outcomes and identifies prediction errors.
- `DecisionSynthesizer`: combines economic, policy, execution, memory, risk, and reflection signals into a final action.
- `LearningSignalGenerator`: emits improvement signals for Self-Evolution, policy updates, economic model tuning, and execution strategy calibration.

## Core Responsibilities

Sprint 29 has three primary responsibilities.

### 1. Deliberation: Decision Conflict Resolution

The layer resolves cases such as:

```text
Economic Layer: high ROI
Policy Engine: high risk
Resource Management: feasible but expensive
Execution Intelligence: runnable but fragile
```

Possible outcomes:

- `accept`
- `modify`
- `reject`
- `delay`
- `research`
- `scope_reduction`
- `require_approval`
- `require_deliberation`
- `escalate`

### 2. Policy Arbitration

Policy arbitration is more than rule checking. It interprets policies when rules conflict or become ambiguous.

The resolver should handle:

- policy A vs policy B conflict
- hard block vs soft constraint
- override chain analysis
- policy exception eligibility
- gray-area interpretation
- risk-based escalation
- advisory vs enforceable policy distinction

Policy arbitration must remain auditable. It can recommend overrides or exceptions, but policy authority remains event-sourced and replayable.

### 3. Self-Evolution Feedback Loop

The layer learns from decision outcomes:

- Which decisions later proved wrong?
- Which economic predictions drifted from actual value?
- Which policy overrides were accurate?
- Which policies overreacted?
- Which execution strategies repeatedly failed?
- Which risk tradeoffs were miscalibrated?

The goal is:

```text
Why did we make the wrong decision,
and how do we avoid that mistake next time?
```

## Data Models

```text
DecisionConflict
  conflict_id
  objective_id
  workflow_id
  task_id
  economic_signal
  policy_signal
  resource_signal
  execution_signal
  risk_signal
  memory_signal
  severity
  status
  detected_at
```

`DecisionConflict` captures incompatible or uncertain signals from multiple AllBrain layers.

```text
PolicyConflict
  policy_conflict_id
  conflict_id
  policy_ids
  conflict_type
  hard_constraints
  soft_constraints
  override_chain
  interpretation
  confidence
```

`PolicyConflict` explains which policies conflict and how their authority should be interpreted.

```text
TradeoffAnalysis
  tradeoff_id
  conflict_id
  value_score
  risk_score
  feasibility_score
  opportunity_cost
  uncertainty
  recommended_action
  accepted_risks
  rejected_options
  confidence
```

`TradeoffAnalysis` balances value, risk, feasibility, and uncertainty.

```text
DeliberationResult
  decision_id
  conflict_id
  final_action
  confidence
  rationale
  tradeoffs
  overridden_policies
  accepted_risks
  required_approvals
  evidence_refs
```

`DeliberationResult` is the final decision record produced under conflict.

```text
PolicyUpdateProposal
  proposal_id
  source_decision_id
  policy_id
  suggested_change
  reason
  evidence
  confidence
  expected_impact
```

`PolicyUpdateProposal` is advisory and must pass through the normal Policy Engine approval flow.

```text
SelfEvolutionSignal
  signal_id
  source_decision_id
  type
  source_layer
  error_delta
  impact_score
  recommendation
  evidence_refs
```

`SelfEvolutionSignal` feeds the Self-Evolution pipeline with decision-quality lessons.

Signal types:

- `wrong_decision`
- `policy_overreaction`
- `policy_underreaction`
- `roi_misprediction`
- `execution_mismatch`
- `risk_miscalibration`
- `resource_estimation_error`
- `successful_override`
- `failed_override`

## Conflict Types

Supported conflict classes:

- `economic_vs_policy_conflict`: high value conflicts with risk or governance rules.
- `execution_vs_feasibility_conflict`: plan is possible in theory but likely fragile in practice.
- `risk_vs_roi_conflict`: high ROI requires accepting meaningful risk.
- `short_term_vs_long_term_value_conflict`: immediate work blocks long-term strategic value.
- `resource_constraint_vs_strategic_urgency`: scarce resources conflict with urgent objectives.
- `policy_vs_policy_conflict`: two policies imply incompatible actions.
- `memory_vs_current_plan_conflict`: history suggests the current plan is likely to fail.
- `self_evolution_vs_policy_conflict`: proposed adaptation improves performance but exceeds autonomy boundaries.

Severity inputs:

- expected value at stake
- policy criticality
- safety or compliance exposure
- reversibility
- resource burn
- confidence disagreement
- number of affected objectives
- historical failure similarity

## Decision Lifecycle

```text
conflict_detected
  -> context_aggregation
  -> multi_layer_evaluation
  -> policy_conflict_resolution
  -> economic_tradeoff_analysis
  -> execution_feasibility_check
  -> risk_synthesis
  -> decision_synthesis
  -> decision_commit
  -> learning_signal_emission
  -> optional_policy_update_proposal
```

Detailed flow:

1. A conflict is detected between economic, policy, resource, execution, memory, or strategic signals.
2. DeliberationCoordinator builds an immutable context bundle.
3. PolicyConflictResolver determines hard constraints, soft constraints, override options, and ambiguous areas.
4. EconomicPolicyBalancer compares value, ROI, opportunity cost, and policy risk.
5. ExecutionFeasibilityJudge evaluates whether the execution plan is realistically likely to succeed.
6. RiskTradeoffAnalyzer balances value, risk, feasibility, and uncertainty.
7. SelfReflectionEngine retrieves similar historical decisions and outcome gaps.
8. DecisionSynthesizer produces the final action.
9. LearningSignalGenerator emits self-evolution signals.
10. Policy update proposals are emitted when patterns indicate policy drift.

## Decision Synthesis

Decision synthesis combines layer signals into one actionable result.

```text
final_decision =
  f(
    economic_signal,
    policy_signal,
    execution_signal,
    resource_signal,
    memory_signal,
    risk_signal,
    reflection_signal
  )
```

Decision actions:

- `accept`: proceed as planned.
- `modify`: proceed with constraints or adaptation.
- `reject`: do not pursue.
- `delay`: defer until conditions improve.
- `research`: reduce uncertainty before commitment.
- `scope_reduction`: pursue a smaller or safer version.
- `require_approval`: request supervisor or human approval.
- `escalate`: send to higher authority or arbitration.
- `veto`: block when hard constraints dominate.

Decision records should include:

- final action
- confidence
- rationale
- tradeoffs
- rejected alternatives
- accepted risks
- overridden or interpreted policies
- required approvals
- evidence references

## Self-Reflection Loop

The SelfReflectionEngine compares expected decisions with actual outcomes.

```text
decision outcome
  -> real-world result
  -> expected vs actual gap
  -> error classification
  -> policy adjustment suggestion
  -> economic model tuning
  -> execution strategy tuning
```

Reflection inputs:

- economic expected value vs actual value
- policy decision vs later incident or false block
- execution strategy prediction vs actual runtime
- resource estimate vs actual usage
- memory recommendation vs outcome
- meta evaluation of task or objective result

Reflection outputs:

- wrong decision labels
- policy overreaction detection
- policy underreaction detection
- ROI misprediction signal
- execution mismatch signal
- simulator calibration signal
- memory case update
- self-evolution recommendation

This turns conflict resolution into a learning system rather than a one-time judgment.

## Policy Arbitration

Policy arbitration classifies constraints before resolving them.

Constraint classes:

- `hard_block`: cannot proceed without approved policy update or explicit override authority.
- `approval_required`: may proceed after approval.
- `soft_constraint`: should influence decision but does not block.
- `advisory_warning`: informs but does not constrain.
- `ambiguous`: requires interpretation or deliberation.

Override analysis:

```text
policy_conflict_detected
  -> classify constraints
  -> inspect override chain
  -> evaluate risk and precedent
  -> propose interpretation
  -> require approval if authority is insufficient
```

Policy arbitration must preserve the difference between:

- interpreting a policy
- proposing a policy update
- approving an override
- silently ignoring a policy

The last option is never allowed.

## Integration Points

- Economic Layer: provides ROI, expected value, opportunity cost, and prediction confidence; receives economic prediction error feedback.
- Execution Intelligence: provides feasibility, bottleneck, adaptation, and execution mismatch signals; receives strategy correction feedback.
- Policy Engine: provides rules, constraints, overrides, and policy conflicts; receives policy update proposals and arbitration outcomes.
- Resource Management: provides affordability, budget pressure, and resource violations; receives decision outcomes for budget override or scope reduction.
- Strategic Planning: receives accept, delay, reject, research, and scope-reduction decisions for objectives.
- Goal Decomposition: receives replan or scope-reduction instructions when conflict resolution changes execution shape.
- Scheduler: consumes final decisions and constraints before assignment.
- Deliberation: supplies debate mechanisms for high-severity or low-confidence conflicts.
- Organizational Memory: retrieves similar conflict cases and stores decision outcomes.
- Meta Evaluation: scores decision accuracy and detects false accept, false reject, and bad override patterns.
- Self-Evolution: consumes learning signals and proposes model, policy, strategy, or organization improvements.
- Replay: reconstructs conflicts, interpretations, tradeoffs, decisions, and outcomes.
- Observability: traces conflict detection, analysis, arbitration, decision, and learning.

## Observability

Trace hierarchy:

```text
decision_arbitration.conflict_detected
decision_arbitration.context.aggregate
decision_arbitration.policy.resolve
decision_arbitration.economic.balance
decision_arbitration.execution.check
decision_arbitration.risk.analyze
decision_arbitration.reflection.run
decision_arbitration.decision.synthesize
decision_arbitration.learning_signal.emit
```

Metrics:

- decision accuracy rate
- policy override frequency
- conflict resolution time
- false reject rate
- false accept rate
- economic prediction error
- execution mismatch rate
- policy overreaction count
- policy underreaction count
- arbitration escalation rate
- accepted risk incident rate
- decision confidence calibration
- learning signal volume by type

Dashboards should show:

- active conflicts
- resolved conflicts by final action
- policy conflicts by policy
- economic-vs-policy disagreement trends
- accepted risks and outcomes
- decision accuracy over time
- false accept and false reject cases
- policy update suggestions
- self-evolution signals awaiting review

Replay must answer:

- Why was this decision conflicted?
- Which layers disagreed?
- Which policies were hard vs soft?
- Why was a policy overridden or not overridden?
- Why was scope reduced instead of rejected?
- Why was research requested?
- Did the final decision prove correct?
- What did the system learn from this decision?

## Recommended Events

```text
decision_conflict_detected
decision_context_aggregated
decision_multilayer_evaluation_started
policy_conflict_detected
policy_conflict_resolved
economic_policy_tradeoff_analyzed
execution_feasibility_judged
risk_tradeoff_analyzed
self_reflection_completed
decision_synthesized
decision_committed
decision_vetoed
decision_scope_reduction_recommended
decision_research_recommended
decision_escalated
learning_signal_generated
policy_update_suggested
decision_outcome_measured
decision_accuracy_evaluated
```

Event payloads should include stable identifiers when available:

- `conflict_id`
- `decision_id`
- `objective_id`
- `workflow_id`
- `task_id`
- `policy_ids`
- `review_id`
- `execution_plan_id`
- `resource_decision_id`
- `memory_case_ids`
- `evidence_refs`

## Acceptance Scenarios

- Economic Layer recommends pursuing a high-ROI objective, but Policy Engine flags high risk; Sprint 29 selects approval, scope reduction, research, or veto with explanation.
- Two policies conflict; PolicyConflictResolver classifies hard and soft constraints and emits an auditable interpretation.
- Execution Intelligence marks a plan feasible but fragile; RiskTradeoffAnalyzer recommends research or safer execution.
- Resource Management says execution is feasible but expensive; EconomicPolicyBalancer recommends scope reduction or budget approval.
- A policy override later proves successful; LearningSignalGenerator emits a successful override signal.
- A rejected objective later appears to have been valuable; SelfReflectionEngine emits a false reject signal.
- An approved high-risk decision fails; SelfReflectionEngine emits policy underreaction or risk miscalibration signals.
- Replay explains why the final decision was accept, modify, reject, delay, or research.

## Scalability Considerations

- Keep conflict and decision records immutable; build active conflict projections.
- Trigger full arbitration only for high-severity or multi-layer conflicts.
- Cache policy interpretation and precedent lookups.
- Use memory retrieval to avoid re-litigating repeated conflicts.
- Bound deliberation rounds for low-confidence conflicts.
- Partition decision history by organization, project, policy domain, and objective type.
- Run reflection asynchronously after outcomes are available.
- Track recurring conflict patterns for policy simplification.
- Keep learning signals compact and evidence-linked.
- Preserve model and policy versions so old decisions remain replayable.

## Design Principle

```text
Economics estimates value.
Execution tests feasibility.
Policy enforces boundaries.
Deliberation decides truth under conflict.
Self-Evolution improves the judge.
```

Sprint 29 gives AllBrain judgment under disagreement. It makes the system capable of resolving conflicts between value, risk, feasibility, and policy while learning from whether those judgments were correct.
