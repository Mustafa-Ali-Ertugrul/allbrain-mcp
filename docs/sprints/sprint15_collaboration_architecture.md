# Sprint 15 Multi-Agent Collaboration & Negotiation Architecture

Sprint 15 makes agents first-class collaborators instead of isolated task executors. Collaboration remains event-sourced: teams, delegations, negotiations, proposals, votes, consensus decisions, and supervisor interventions are derived from events.

## Event Flow

```text
collaboration_started
  -> delegation_created
  -> negotiation_started
  -> proposal_created / proposal_rejected / proposal_accepted
  -> vote_cast
  -> consensus_reached
  -> supervisor_intervention
  -> delegation_completed
  -> collaboration_completed
```

## State Machines

Delegation:

```text
created -> completed
created -> failed
```

Negotiation:

```text
started -> proposal_created -> proposal_rejected -> proposal_created -> proposal_accepted -> completed
started -> timeout
```

Consensus:

```text
vote_cast* -> consensus_reached
vote_cast* -> consensus_failed
```

## Integration

- Replay exposes derived `collaboration` state.
- Graph builder adds collaboration, delegation, negotiation, proposal, vote, consensus, and supervisor action nodes.
- Memory builder stores collaboration outcomes.
- Dashboard data includes collaboration metrics.
- Existing workflow/runtime APIs remain unchanged.
