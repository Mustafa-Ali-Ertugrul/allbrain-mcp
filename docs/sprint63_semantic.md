# Sprint 63 — Semantic Memory Layer

## Goal

Episodic memory (Sprint 62) stores specific experiences; Sprint 63 **abstracts**
recurring episodes into reusable **concepts** — generalized patterns with a
confidence that grows with reinforcement and decays with disuse. Retrieved
concepts are surfaced to the decision engine as *informational* context. This is
the layer that lets the system move from "I remember this exact case" to "I know
this *kind* of case." The system can now say:

- "Episodes #418, #455, #470 share a pattern → form concept `retry-on-timeout`
  (confidence 0.66)."
- "Concept `retry-on-timeout` matches the current situation → surface it; its
  confidence rose to 0.71 after this reinforcement."

## Architecture

```
episodes (Sprint 62)
  ↓
extract_pattern_from_episode() / generalize_signature() / pattern_overlap()
find_matching_concept() / should_create_concept()  → CONCEPT_CREATED
compute_concept_confidence() (reinforce)            → CONCEPT_UPDATED
apply_decay_to_all() / should_forget_concept() / trim_to_capacity()
                                                    → CONCEPT_FORGOTTEN
retrieve_semantic()
  ↓
SemanticReducer → state["semantic"]  (SemanticState)
  ↓
DecisionEngine (concepts = informational, backward compat)
```

> Source marker (`decision/engine.py:30`): *"Sprint 63: concepts added as
> informational (backward compat)."*

## Scope

### In

1. New module `src/allbrain/semantic/` (`abstraction`, `consolidation`,
   `retrieval`, `events`, `model`, `manager`, `reducer`).
2. `extract_pattern_from_episode()` / `generalize_signature()` /
   `pattern_overlap()` — abstraction from episodes to concepts.
3. `find_matching_concept()` / `should_create_concept()` /
   `compute_concept_confidence()` — concept matching, creation, reinforcement.
4. `should_forget_concept()` / `apply_decay_to_all()` / `trim_to_capacity()` —
   confidence decay and capacity management.
5. `retrieve_semantic()` — concept retrieval for the current situation.
6. Models: `SemanticConcept`, `SemanticState`.
7. Events: `CONCEPT_CREATED`, `CONCEPT_UPDATED`, `CONCEPT_FORGOTTEN`.
8. `DecisionEngine` integration: `concepts` passed as informational only.

### Out of scope (Sprint 64+)

- Failure-specific memory (storing/retrieving failure patterns) — Sprint 64.
- Letting concepts change the decision score (Sprint 63 is display-only /
  backward-compatible).
- Cross-agent concept sharing (concepts are local to the event stream).
