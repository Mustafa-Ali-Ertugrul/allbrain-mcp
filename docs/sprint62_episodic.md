# Sprint 62 — Episodic Memory Layer

## Goal

Sprint 62 gives the system an **episodic memory**: it stores salient experiences
(episodes), scores them by importance and novelty, retrieves similar past
episodes for the current situation, and forgets the rest. Retrieved episodes are
surfaced to the decision engine as *informational* context. The system can now
say:

- "This situation resembles episode #418 (Jaccard similarity 0.72) where
  `codex` succeeded — surface it."
- "This experience is novel and important enough to store; that stale low-value
  episode is forgotten."

## Architecture

```
situation / outcome
  ↓
compute_importance() / compute_novelty()  (jaccard_similarity vs. store)
should_store_episode()    → EPISODE_CREATED
retrieve_similar()        → EPISODE_RETRIEVED
(consolidation / capacity) → EPISODE_FORGOTTEN
  ↓
EpisodicReducer → state["episodic"]  (EpisodicState)
  ↓
DecisionEngine (episodes = informational, backward compat)
```

> Source marker (`decision/engine.py:29`): *"Sprint 62: episodes added as
> informational (backward compat)."*

## Scope

### In

1. New module `src/allbrain/episodic/` (`importance`, `novelty`/`consolidation`,
   `retrieval`, `events`, `model`, `manager`, `reducer`).
2. `compute_importance()` / `compute_novelty()` / `jaccard_similarity()` —
   salience and novelty scoring of candidate episodes.
3. `should_store_episode()` — consolidation gate (store vs. discard).
4. `retrieve_similar()` — similarity retrieval of past episodes for the current
   situation.
5. Models: `Episode`, `EpisodicState`.
6. Events: `EPISODE_CREATED`, `EPISODE_RETRIEVED`, `EPISODE_FORGOTTEN`.
7. `DecisionEngine` integration: `episodes` passed as informational only.

### Out of scope (Sprint 63+)

- Abstracting episodes into reusable concepts — Sprint 63 semantic memory.
- Importance-based forgetting policy (noted in code as a future replacement for
  the current forgetting heuristic).
- Letting retrieved episodes change the decision score (Sprint 62 is
  display-only / backward-compatible).
