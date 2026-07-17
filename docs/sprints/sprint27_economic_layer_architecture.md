# Sprint 27 Economic Layer Architecture

Sprint 27 introduces the Economic Layer: the decision layer that determines whether proposed work is economically worthwhile. It sits between Strategic Planning and Goal Decomposition.

Resource Management answers:

```text
Can we do this?
```

Economics answers:

```text
Should we do this?
```

The Economic Layer evaluates expected value, total cost, opportunity cost, return on investment, portfolio value, resource efficiency, strategic value, learning value, and organizational value. It influences strategic prioritization, objective activation, budget allocation, resource allocation, scheduler routing, scope reduction, investment decisions, and experimentation decisions.

## Architecture

```text
Strategic Planning
  -> economic_review_requested
  -> Economic Layer
       -> Value Estimator
       -> Cost Analyzer
       -> Opportunity Evaluator
       -> ROI Engine
       -> Investment Planner
       -> Portfolio Optimizer
       -> Economic Simulator
       -> Budget Forecaster
  -> invest | delay | abandon | reduce_scope | increase_budget | request_research
  -> Goal Decomposition
```

Core components:

- `EconomicReviewCoordinator`: orchestrates economic evaluation for objectives, roadmap changes, experiments, and major execution decisions.
- `ValueEstimator`: estimates expected value across economic, strategic, learning, reliability, safety, and organizational dimensions.
- `CostAnalyzer`: estimates token, compute, GPU, provider, human, maintenance, retry, delay, risk, and opportunity costs.
- `OpportunityEvaluator`: identifies alternatives sacrificed by choosing one objective over another.
- `ROIEngine`: computes expected ROI, net expected value, risk-adjusted value, and confidence intervals.
- `InvestmentPlanner`: recommends invest, delay, abandon, reduce scope, increase budget, or request research.
- `PortfolioOptimizer`: balances multiple active objectives under budget, risk, dependency, and strategic constraints.
- `EconomicSimulator`: compares alternative strategies such as expensive vs cheap agents, large vs small scope, immediate vs delayed execution, and provider alternatives.
- `BudgetForecaster`: projects budget burn, future budget pressure, and expected economic capacity.
- `EconomicProjector`: builds current portfolio value, expected cost, realized value, and investment outcome projections.

The Economic Layer is advisory by default, but its recommendations may become hard gates when enforced by Policy Engine rules.

## Data Models

```text
EconomicReview
  review_id
  subject_type
  subject_id
  objective_id
  roadmap_id
  requested_by
  trigger_event_id
  context_hash
  status
  decision
  confidence
  created_at
```

`EconomicReview` is the immutable parent record for a value, cost, ROI, opportunity, and portfolio analysis.

```text
ExpectedValue
  expected_value_id
  review_id
  subject_type
  subject_id
  total_expected_value
  value_unit
  confidence
  confidence_interval
  assumptions
  evidence_refs
  historical_support
  model_version
```

`ExpectedValue` represents the aggregate expected value of an objective or option. The value unit may be currency, utility points, risk reduction points, learning value, strategic score, or a normalized composite.

```text
ValueProfile
  value_profile_id
  review_id
  economic_value
  strategic_value
  learning_value
  reliability_value
  safety_value
  organizational_value
  confidence_by_dimension
  assumptions_by_dimension
```

`ValueProfile` keeps the value estimate explainable by dimension instead of collapsing everything into a single score too early.

```text
ValueEvidence
  evidence_id
  review_id
  value_dimension
  source_type
  source_id
  claim
  support_strength
  confidence
```

Evidence sources include organizational memory cases, meta evaluations, strategic objectives, prior economic reviews, resource usage history, deliberation outcomes, and actual value measurements.

```text
EconomicCost
  cost_id
  review_id
  subject_type
  subject_id
  cost_type
  estimated_amount
  actual_amount
  currency_or_unit
  window
  version
  confidence
  evidence_refs
```

Supported cost types:

- `token_cost`
- `compute_cost`
- `gpu_cost`
- `provider_cost`
- `human_cost`
- `maintenance_cost`
- `retry_cost`
- `delay_cost`
- `risk_cost`
- `opportunity_cost`

Costs must be versioned and replayable. Historical reviews replay against the cost model active at the time.

```text
ROIAnalysis
  roi_analysis_id
  review_id
  expected_value
  expected_cost
  roi_ratio
  net_expected_value
  risk_adjusted_value
  payback_horizon
  uncertainty
  confidence_interval
  historical_calibration
```

```text
OpportunityCostAnalysis
  opportunity_analysis_id
  review_id
  chosen_objective_id
  sacrificed_objective_ids
  lost_value
  delayed_value
  strategic_tradeoffs
  explanation
  confidence
```

```text
InvestmentDecision
  decision_id
  review_id
  objective_id
  decision
  rationale
  recommended_budget
  recommended_scope
  alternatives
  required_approvals
  confidence
  policy_refs
```

Allowed investment decisions:

- `invest`
- `delay`
- `abandon`
- `reduce_scope`
- `increase_budget`
- `request_research`

## Value Model

Value is multi-dimensional:

- `economic_value`: direct or estimated financial benefit, cost savings, revenue, or productivity gain.
- `strategic_value`: alignment with roadmap, mission, platform direction, or unlocking future work.
- `learning_value`: knowledge gained, uncertainty reduced, reusable research, or improved estimates.
- `reliability_value`: reduced failure rate, improved recovery, lower operational risk.
- `safety_value`: reduced harm, compliance risk, policy violation risk, or unsafe autonomy.
- `organizational_value`: improved team capacity, coordination, memory quality, capability growth, or governance.

Value estimates must include:

- confidence
- assumptions
- evidence
- historical support
- model version
- counter-evidence
- uncertainty range

Uncertain high-value objectives should not be rejected automatically. They should often become research investments:

```text
high expected value + low confidence
  -> request_research
  -> reduce uncertainty
  -> repeat economic review
```

## Cost Model

Cost is broader than Resource Management consumption. Resource Management tracks what can be afforded and consumed; the Economic Layer estimates the total economic burden of pursuing an objective.

Cost dimensions:

- `token_cost`: input and output token spend.
- `compute_cost`: CPU, memory, storage, and execution infrastructure.
- `gpu_cost`: GPU seconds, GPU slots, accelerator scarcity, and queue time.
- `provider_cost`: paid model/API/tool cost.
- `human_cost`: required review, approval, supervision, or manual intervention.
- `maintenance_cost`: future upkeep, monitoring, tests, support, and operational complexity.
- `retry_cost`: expected cost of failures, retries, replans, and recovery.
- `delay_cost`: value lost by waiting.
- `risk_cost`: expected loss from failure, policy violation, downtime, or unsafe execution.
- `opportunity_cost`: value lost by not pursuing alternatives.

Cost estimates should be tied to:

- resource budgets
- historical actual usage
- similar organizational memory cases
- provider/model cost versions
- agent performance and retry rates
- policy-required approvals or supervision
- projected maintenance horizon

## ROI and Opportunity Analysis

The ROI Engine should support several calculations:

```text
roi_ratio = expected_value / expected_cost
net_expected_value = expected_value - expected_cost
risk_adjusted_value = expected_value * success_probability - expected_cost - risk_cost
```

It should also support normalized portfolio scores when value is not purely monetary:

```text
economic_score =
  weighted_value_profile
  - expected_cost_penalty
  - risk_penalty
  - opportunity_cost_penalty
  + learning_option_value
```

Uncertainty handling:

- confidence intervals for value and cost
- low-confidence penalties
- historical calibration by objective type
- sensitivity analysis for cost overruns
- best/base/worst-case estimates

Opportunity analysis must explain tradeoffs:

```text
Objective A selected
  -> Objective B delayed
  -> lost_value estimated
  -> delayed_value recorded
  -> strategic tradeoff explained
```

Replay should be able to answer:

- Why was B delayed?
- What value was lost?
- Which objective was judged more valuable?
- Was the tradeoff correct after actual outcomes were measured?

## Portfolio Management

The Economic Layer manages multiple active and proposed objectives as an investment portfolio.

Portfolio decisions:

- `invest`: commit budget and activate the objective.
- `delay`: keep objective valid but defer execution.
- `abandon`: reject the objective as economically unjustified.
- `reduce_scope`: pursue a smaller version with better ROI or lower risk.
- `increase_budget`: expand funding when expected value justifies it.
- `request_research`: fund discovery before full commitment.

Portfolio balancing considers:

- expected value
- expected cost
- risk
- uncertainty
- dependencies
- strategic alignment
- resource pressure
- opportunity cost
- organizational capacity
- learning portfolio balance

Example portfolio allocation:

```text
60% strategic delivery
20% reliability and safety
10% research and learning
10% self-evolution and organizational improvement
```

Portfolio review should detect:

- too many active objectives
- high-value objectives starved of budget
- low-ROI objectives consuming scarce resources
- excessive risk concentration
- excessive provider or GPU dependency
- delayed objectives with rising opportunity cost
- strategic drift from roadmap priorities

## Economic Simulation

Economic simulations compare alternatives before commitment.

Supported simulations:

- expensive vs cheap agents
- large vs small scope
- immediate vs delayed execution
- alternative providers
- increased budget vs reduced scope
- research-first vs build-first
- high-autonomy vs supervised execution
- single-team vs multi-team execution
- retry-heavy vs replan-first strategies

Simulation outputs:

- expected ROI
- expected value
- expected cost
- risk delta
- budget impact
- opportunity cost
- confidence interval
- sensitivity factors
- recommended decision

Simulation flow:

```text
economic_simulation_requested
  -> alternatives_generated
  -> baseline_estimated
  -> alternative_estimated
  -> risk_and_uncertainty_compared
  -> opportunity_cost_calculated
  -> economic_simulation_completed
```

Simulations should preserve counterexamples. A cheaper agent may improve ROI on average but create unacceptable risk for safety-critical or deployment work.

## Economic Lifecycle

```text
objective_proposed
  -> value_estimated
  -> cost_estimated
  -> roi_calculated
  -> opportunity_evaluated
  -> portfolio_reviewed
  -> investment_decision
  -> execution
  -> actual_value_measured
```

Detailed lifecycle:

1. Strategic Planning proposes or revises an objective.
2. Economic review is requested.
3. Value is estimated across multiple dimensions.
4. Cost is estimated across execution, maintenance, delay, risk, and opportunity categories.
5. ROI and risk-adjusted value are calculated.
6. Opportunity cost is evaluated against competing objectives.
7. Portfolio optimizer checks balance, budget pressure, dependencies, and strategic fit.
8. Investment decision is recorded.
9. Approved objectives proceed to Goal Decomposition.
10. Actual value is measured after execution and compared with estimates.
11. Memory and Self-Evolution learn from estimate accuracy and investment outcomes.

## Integration Points

- Strategic Planning: sends proposed objectives for economic review and consumes investment decisions for roadmap prioritization.
- Goal Decomposition: receives only approved or research-scoped objectives; may receive reduced scope or budget envelope.
- Policy Engine: governs approval thresholds, high-risk investments, autonomy constraints, and budget override rules.
- Organization Layer: provides ownership, team capacity, human review cost, and organizational value signals.
- Resource Management: supplies affordability, resource availability, budget pressure, and actual consumption.
- Scheduler: uses economic signals for routing, such as cheaper eligible agents or high-value priority boosts.
- Deliberation: handles disputed value estimates, high-uncertainty investments, or strategic tradeoffs.
- Organizational Memory: retrieves historical value, cost, ROI, delay, and outcome cases.
- Meta Evaluation: assesses whether economic decisions were accurate and whether expected value was realized.
- Self-Evolution: improves cost models, value estimators, portfolio weights, and investment strategies.
- Replay: reconstructs economic decisions, assumptions, estimates, tradeoffs, and outcomes.
- Observability: tracks economic traces, dashboards, estimate accuracy, and realized value.

## Observability

Trace hierarchy:

```text
economic.review
  economic.context.build
  economic.value.estimate
  economic.cost.estimate
  economic.roi.calculate
  economic.opportunity.evaluate
  economic.portfolio.review
  economic.simulation.run
  economic.investment.decide
  economic.actual_value.measure
```

Metrics:

- expected value by objective
- realized value by objective
- expected vs actual cost
- ROI by objective
- risk-adjusted value
- opportunity cost incurred
- delayed value
- investment approval rate
- investment rejection rate
- scope reduction count
- research request count
- portfolio value
- portfolio risk concentration
- estimate accuracy
- budget efficiency
- value per token
- value per dollar
- value per GPU hour
- value per agent hour

Economic dashboards should show:

- active investment portfolio
- objective ROI ranking
- budget allocation by objective and team
- expected vs realized value
- opportunity cost ledger
- delayed or abandoned objectives
- high-uncertainty objectives
- scope reductions and their saved cost
- investment outcomes over time

Replay must answer:

- Why was this objective rejected?
- Why was a cheaper agent selected?
- Why was this investment approved?
- Why was scope reduced?
- What alternative objective was sacrificed?
- What value was expected?
- What cost was expected?
- Was the expected value realized?
- Was the investment successful?

## Recommended Events

```text
economic_review_requested
economic_review_started
value_estimated
cost_estimated
roi_calculated
opportunity_cost_evaluated
portfolio_reviewed
investment_approved
investment_rejected
investment_delayed
investment_abandoned
scope_reduction_recommended
research_investment_requested
budget_increase_recommended
budget_increased
budget_reduced
portfolio_rebalanced
economic_simulation_requested
economic_simulation_completed
actual_value_measurement_requested
actual_value_measured
economic_review_completed
economic_review_failed
```

All events should include stable identifiers where available:

- `objective_id`
- `roadmap_id`
- `review_id`
- `portfolio_id`
- `budget_id`
- `simulation_id`
- `decision_id`
- `policy_id`
- `evidence_refs`

## Scalability Considerations

- Keep economic reviews immutable and build fast portfolio projections.
- Partition portfolio projections by organization, project, department, roadmap, and objective type.
- Cache value and cost estimates for unchanged objectives.
- Use incremental portfolio optimization when only one objective changes.
- Run expensive simulations asynchronously.
- Use historical sampling for large replay-based economic analysis.
- Preserve model versions so old ROI decisions remain replayable.
- Separate objective-level economics from task-level resource accounting.
- Support multiple organizations with different value weights and budget policies.
- Track estimate calibration so unreliable models lose influence over time.
- Avoid re-review storms by debouncing frequent priority or budget changes.
- Maintain opportunity-cost summaries instead of recomputing all sacrificed alternatives on every query.

## Design Principle

```text
Strategy decides what matters.
Economics decides what is worth pursuing.
Resources decide what is affordable.
Execution decides how work happens.
```

The Economic Layer gives AllBrain an investment discipline. It prevents the system from optimizing only for feasibility or urgency by requiring every significant objective to justify its expected value, total cost, opportunity cost, and portfolio fit before work is decomposed into executable tasks.
