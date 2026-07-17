# Sprint 41.2 - Projection Ordering

## Objective
Standardize event sorting across all projections to enforce the canonical ordering contract. Replace implicit, error-prone created_at dominant sorts with the centralized canonical_event_sort.

## Architectural Decision
Projections MUST consume events through canonical_event_sort().

Direct usage of:
``python
sorted(events, key=lambda item: (item.created_at, item.id))
``
is considered a violation of the ordering contract.

The ordering contract guarantees determinism by sorting primarily by id (UUIDv7, which inherently contains a timestamp). Relying on created_at explicitly introduces fragility, especially in test environments where timestamps might be artificially manipulated.

## Changes
- Replaced 19 instances of implicit sorting across 14 projection and state files.
- Refactored 	racer.py to extract start and end times using explicit min() and max() operations instead of relying on the first and last elements of the sorted array, safeguarding against manipulated timestamps.
- Added a quality gate test to prevent future regressions of the ordering contract.
- Added a behavioral test for untime_core/projections.py to explicitly verify the contract.

## Context
See [Sprint 41.1 (Foundations Hardening)](sprint41_1_hotfix.md) for the introduction of canonical_event_sort and its application in the storage path. Sprint 41.2 completes the migration by extending it to the projection/reducer path.
