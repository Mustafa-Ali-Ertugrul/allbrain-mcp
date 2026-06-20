# Sprint 22 Organization Layer Architecture

Sprint 22 turns agents from individual executors into an explicit organization. The Organization Layer models teams, departments, managers, specialists, supervisors, escalation chains, delegation, workload, and collaboration patterns.

## Organization Model

```text
Organization
  Department
    Team
      Role
        Agent
```

Core entities:

- `Organization`: top-level operating structure for a project or workspace.
- `Department`: a functional area such as Engineering, Research, Operations, Safety, or Executive.
- `Team`: a group of agents with shared responsibility.
- `Role`: a responsibility slot such as Architect, Reviewer, Test Runner, Supervisor, Analyst, Coordinator.
- `AgentMembership`: binds an agent to a role, team, and effective period.
- `Manager`: an agent or policy-controlled role responsible for delegation and escalation.
- `EscalationChain`: ordered chain for unresolved, risky, or blocked work.

Example:

```text
Executive Team
  Coordinator

Engineering Team
  Architect
  Builder
  Reviewer
  Test Runner

Research Team
  Explorer
  Analyst

Operations Team
  Supervisor
  Release Manager
```

## Hierarchy Design

The hierarchy should be explicit but not rigid. Agents may belong to multiple teams with different weights or scopes.

Relationship types:

- `manages`
- `supervises`
- `delegates_to`
- `reports_to`
- `collaborates_with`
- `reviews`
- `backs_up`
- `escalates_to`

Hierarchy should support:

- functional teams
- temporary mission teams
- specialist pools
- supervisor chains
- review authority
- policy-controlled approvals
- workload balancing across agents and teams

Important rule: organization structure influences decisions but does not replace event-sourced workflow state. Team assignments, delegations, and supervision are derived from immutable events.

## Delegation Flow

```text
task_ready
  -> organization_context_built
  -> responsible_department_selected
  -> team_selected
  -> role_requirements_matched
  -> delegation_created
  -> agent_assignment_requested
  -> supervisor_review_requested? 
  -> delegation_accepted | delegation_rejected | delegation_escalated
  -> delegation_completed | delegation_failed
```

Delegation decisions should consider:

- task domain and required capabilities
- team ownership
- current workload
- agent historical performance
- policy requirements
- memory of similar tasks
- need for review or supervision
- risk and criticality
- active blockers or escalations

Delegation outputs:

- selected team
- required roles
- candidate agents per role
- manager or supervisor
- review requirements
- escalation path
- workload impact

## Communication Flow

Communication is also event-sourced.

```text
message_created
  -> message_routed
  -> acknowledgement_recorded
  -> response_recorded
  -> decision_recorded
```

Communication types:

- task handoff
- delegation request
- status update
- review request
- blocker report
- escalation
- decision memo
- deliberation invitation
- supervisor instruction

The communication layer should preserve:

- sender
- recipient role/team/agent
- subject
- required response
- deadline
- linked task, milestone, debate, policy, or evaluation
- acknowledgement status
- decision outcome

This allows replay to show not only what happened, but how responsibility moved through the organization.

## Team Lifecycle

```text
team_proposed
  -> team_created
  -> role_defined
  -> agent_assigned_to_role
  -> team_activated
  -> workload_assigned
  -> team_performance_evaluated
  -> team_rebalanced | team_restructured | team_retired
```

Team types:

- `standing_team`: long-lived department team.
- `mission_team`: created for a goal or milestone.
- `review_panel`: temporary team for critique, policy, or release approval.
- `incident_team`: formed around failures, blockers, or high-risk recovery.
- `specialist_pool`: agents available for narrow expertise.

Team health metrics:

- workload balance
- task throughput
- failure rate
- review latency
- escalation rate
- collaboration success
- disagreement resolution rate
- supervisor intervention rate
- confidence calibration

## Supervision and Escalation

Escalation should be structured:

```text
agent
  -> role lead
  -> team manager
  -> department supervisor
  -> executive coordinator
  -> human approval, if required
```

Escalation triggers:

- blocked task
- repeated failure
- low confidence
- policy violation
- unresolved deliberation disagreement
- critical deployment
- memory indicates prior high-risk failure
- manager unavailable

Escalation outputs:

- decision
- reassignment
- replan request
- deliberation request
- approval requirement
- cancellation
- policy exception request

## Integration Points

- Goal Decomposition: maps milestones and tasks to departments, teams, and roles.
- Policy Engine: determines required supervision, approvals, escalation chains, and authority.
- Scheduler: chooses agents within organizational constraints and workload limits.
- Deliberation: selects panels, specialists, critics, arbiters, and moderators.
- Organizational Memory: stores successful team compositions and delegation patterns.
- Meta Evaluation: evaluates team fit, manager effectiveness, and supervision quality.
- Evolution: proposes restructuring, role weighting, or team strategy improvements.
- Observability: tracks delegation latency, team load, escalation paths, and communication delays.
- Replay: reconstructs who owned what, who delegated to whom, and why escalation happened.

## Event Flow

```text
organization_created
department_created
team_created
role_defined
agent_assigned_to_role
delegation_created
delegation_accepted
delegation_rejected
supervision_requested
supervisor_intervention
escalation_started
escalation_resolved
team_rebalanced
team_restructured
team_retired
```

## Scalability Considerations

- Keep organization structure as projections over immutable membership events.
- Support multiple concurrent organizations per project or workspace.
- Use role-based assignment before agent-level assignment to reduce scheduling complexity.
- Cache team capability summaries and workload projections.
- Allow temporary mission teams without restructuring permanent departments.
- Track team-level metrics separately from agent-level metrics.
- Use escalation chain templates for common domains.
- Avoid central manager bottlenecks with delegated authority and backup roles.
- Support organization versioning so historical decisions replay against the correct structure.

## Design Principle

```text
Agents execute tasks.
Organizations assign responsibility.
```

The Organization Layer gives AllBrain durable structure: who owns work, who supervises risk, who reviews outcomes, and how responsibility escalates when autonomous execution is not enough.
