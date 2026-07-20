# ADR-004: foundations/ as Infrastructure

## Status: Accepted

## Context

`foundations/` module provides `canonical_event_sort()` and ordering helpers.
It has 37 importers across the codebase — more than most domain modules.

## Alternatives Considered

1. **Domain module:** Place in `domains.analysis/` — Rejected.
   Too many cross-context dependents would violate the Golden Rule.
2. **Infrastructure:** Place alongside `core/`, `events/`, `models/` — Selected.
3. **Inline:** Duplicate sorting logic in each consumer — Rejected.
   Violates DRY; 37 copies to maintain.

## Decision

`foundations/` is classified as infrastructure, not a domain module.
It sits alongside `core/`, `events/`, `models/`, `storage/`, `security/`,
`server/`, `snapshot/`, `orchestrator/`, `reducers/`, `config.py`, `cli/`,
`install/`, `ops/`.

## Consequences

- Bounded contexts may import from `foundations/` without violating Golden Rule
- `foundations/` must remain stable (no breaking changes without migration path)
- Future split into `foundations.sorting`, `foundations.versioning` etc. if scope grows
