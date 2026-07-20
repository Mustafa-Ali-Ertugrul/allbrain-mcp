# AllBrain Architecture — Bounded Contexts

This document maps the 73 top-level domain packages into 6 bounded
contexts. The `allbrain.domains.*` namespace was created in v0.3.0
and the first context (`reasoning/`, 10 modules) was migrated in
**v0.4.0**. Remaining contexts migrate in v0.4.1–v0.4.2.

## Design Philosophy: A Cognitive Architecture for AI Agents

AllBrain's module structure is not arbitrary. It implements a layered
cognitive model for artificial agents, drawing from Bayesian epistemology,
metacognition, world modeling, and decision theory.

### Layer 1: Bayesian Epistemology — "What does the agent believe?"

| Module | Role |
|---|---|
| `belief/` | Beta-Bernoulli posterior updates (Thompson Sampling) |
| `evidence/` | Likelihood-weighted observation accumulation |
| `contradiction/` | Posterior conflict detection |
| `calibration/` | Predicted vs. actual outcome alignment (Tetlock-style) |

### Layer 2: Metacognitive Hierarchy — "What does the agent think about its beliefs?"

| Module | Role |
|---|---|
| `meta_reasoning/` | Reasoning about reasoning quality |
| `meta_scoring/` | Scoring the scores |
| `meta_meta_scoring/` | Detecting scoring drift |
| `meta_policy/` | Policy selection over policies |

### Layer 3: World Modeling & Prediction — "What does the agent think will happen?"

| Module | Role |
|---|---|
| `world/` | `TransitionLearner` + `BetaPredictor` (event-log grounded) |
| `foresight/` | Multi-step simulation with confidence decay |
| `counterfactual/` | Intervention-based alternative evaluation |
| `scenarios/` | Best/expected/worst branching |

### Layer 4: Decision & Action — "What does the agent choose to do?"

| Module | Role |
|---|---|
| `decision/` | 4-step pipeline (Preparation → Reasoning → Feedback → Learning) |
| `tradeoff_engine/` | Multi-criteria optimization |
| `information_seeking/` | Value of Information (VOI) maximization |

### Layer 5: Memory & Identity — "What does the agent remember and how does it know itself?"

| Module | Role |
|---|---|
| `episodic/` | Event-level recall (Tulving) |
| `semantic/` | Compressed, generalized knowledge |
| `failure_memory/` | Negative-example retention |

This layered model is what distinguishes AllBrain from "tool collection"
MCP servers. Each layer builds on the previous: beliefs feed metacognition,
metacognition informs world modeling, world models drive decisions, and
decisions create memories that update beliefs — a closed cognitive loop.

## Dependency Rule (Golden Rule)

- Bounded contexts MAY depend only on **infrastructure**: `core/`, `models/`,
  `events/`, `storage/`, `security/`, `server/`, `snapshot/`, `orchestrator/`,
  `reducers/`, `config/`, `cli/`, `install/`, `ops/`.
- **Cross-context imports are FORBIDDEN.** If two contexts need to
  share logic, that logic moves into `core/` or `models/`.

> `orchestrator/` and `reducers/` are explicitly exempt from the rule:
> they are cross-cutting infrastructure layers (scheduling + reducers), not
> domains. The reducer files (`reducers/<domain>.py`) already mirror
> these context boundaries internally.

## Infrastructure (untouched)

| Package | Role |
|---|---|
| `core/` | Event-sourcing core (state_engine, state_machine, merge) |
| `storage/` | DB layer (database, repository, snapshot_repo) |
| `security/` | Redaction, rate limiting, input guard |
| `events/` | Event type definitions, domain matching |
| `models/` | SQLModel entities, Pydantic schemas |
| `server/` | MCP server (app, context, lifecycle, tools/) |
| `snapshot/` | SnapshotEngine, SnapshotBuilder |
| `orchestrator/` | Task graph, scheduling, handoff (infrastructure) |
| `reducers/` | Cross-cutting reducer layer (infrastructure) |
| `config.py` | Path validation, configuration |
| `cli/` | CLI entry point |
| `install/` | Client installer |
| `ops/` | Operational tooling |

## Migration Status (v0.4.1)

| Context | Modules | Status | Since | Path |
|---|---|---|---|---|
| `reasoning/` | 10 | ✅ **Migrated** | v0.4.0 | `allbrain.domains.reasoning.*` |
| `analysis/` | 17 | ✅ **Migrated** | v0.4.1 | `allbrain.domains.analysis.*` |
| `governance/` | 12 | ⏳ Pending | v0.4.2 | `allbrain.<mod>` (shim target: `allbrain.domains.governance.*`) |
| `learning/` | 12 | ⏳ Pending | v0.4.2 | `allbrain.<mod>` (shim target: `allbrain.domains.learning.*`) |
| `collaboration/` | 10 | ⏳ Pending | v0.4.3 | `allbrain.<mod>` (shim target: `allbrain.domains.collaboration.*`) |
| `memory/` | 12 | ⏳ Pending | v0.4.3 | `allbrain.<mod>` (shim target: `allbrain.domains.memory.*`) |

## Bounded Contexts

### `domains.reasoning/` — decision-making & forward thinking (10) [MIGRATED v0.4.0]

| Module | Canonical Path (v0.4.0+) | Legacy Shim Path (v0.4.0, removed v0.5.0) | Key Exports |
|---|---|---|---|
| counterfactual | `allbrain.domains.reasoning.counterfactual` | `allbrain.counterfactual` | `CounterfactualEngine`, `AlternativeRanker` |
| scenarios | `allbrain.domains.reasoning.scenarios` | `allbrain.scenarios` | `ScenarioEngine`, `ScenarioAnalysis` |
| foresight | `allbrain.domains.reasoning.foresight` | `allbrain.foresight` | `ForesightInput`, generation |
| meta_reasoning | `allbrain.domains.reasoning.meta_reasoning` | `allbrain.meta_reasoning` | meta-reasoning |
| uncertainty | `allbrain.domains.reasoning.uncertainty` | `allbrain.uncertainty` | `observed_success_rate` |
| decision | `allbrain.domains.reasoning.decision` | `allbrain.decision` | decision pipeline |
| information_seeking | `allbrain.domains.reasoning.information_seeking` | `allbrain.information_seeking` | `InformationSeekingManager` |
| intent | `allbrain.domains.reasoning.intent` | `allbrain.intent` | `IntentExtractor`, `IntentStore` |
| objective_system | `allbrain.domains.reasoning.objective_system` | `allbrain.objective_system` | objective mgmt |
| tradeoff_engine | `allbrain.domains.reasoning.tradeoff_engine` | `allbrain.tradeoff_engine` | tradeoff analysis |

### `domains.analysis/` — situation understanding & anomaly (17) [MIGRATED v0.4.1]

| Module | Canonical Path (v0.4.1+) | Legacy Shim Path (v0.4.1, removed v0.5.0) | Key Exports |
|---|---|---|---|
| attention | `allbrain.domains.analysis.attention` | `allbrain.attention` | attention |
| attribution | `allbrain.domains.analysis.attribution` | `allbrain.attribution` | attribution |
| belief | `allbrain.domains.analysis.belief` | `allbrain.belief` | `BeliefManager` |
| causal | `allbrain.domains.analysis.causal` | `allbrain.causal` | `simulate_intervention` |
| compression | `allbrain.domains.analysis.compression` | `allbrain.compression` | `EventCompressor` |
| context | `allbrain.domains.analysis.context` | `allbrain.context` | `ParallelContextBuilder` |
| contradiction | `allbrain.domains.analysis.contradiction` | `allbrain.contradiction` | `ContradictionDetector` |
| drift | `allbrain.domains.analysis.drift` | `allbrain.drift` | drift detection (deprecated) |
| dynamics | `allbrain.domains.analysis.dynamics` | `allbrain.dynamics` | capability dynamics |
| episodic | `allbrain.domains.analysis.episodic` | `allbrain.episodic` | episodic memory |
| evidence | `allbrain.domains.analysis.evidence` | `allbrain.evidence` | evidence |
| failure_memory | `allbrain.domains.analysis.failure_memory` | `allbrain.failure_memory` | failure memory |
| fusion | `allbrain.domains.analysis.fusion` | `allbrain.fusion` | data fusion |
| graph | `allbrain.domains.analysis.graph` | `allbrain.graph` | graph analysis |
| predictive_failure | `allbrain.domains.analysis.predictive_failure` | `allbrain.predictive_failure` | predictive failure |
| semantic | `allbrain.domains.analysis.semantic` | `allbrain.semantic` | semantic analysis |
| world | `allbrain.domains.analysis.world` | `allbrain.world` | `WorldModel` |

### `domains.governance/` — safety, alignment, self-repair (12)

| Module | Current Path | Key Exports |
|---|---|---|
| policy | `allbrain.policy` | `RoutingEngine` |
| policy_competition | `allbrain.policy_competition` | competing policies |
| policy_routing | `allbrain.policy_routing` | policy selection |
| value_alignment | `allbrain.value_alignment` | value alignment |
| governance | `allbrain.governance` | `AutonomousGovernanceCoordinator` |
| self_repair | `allbrain.self_repair` | self-repair |
| soft_repair | `allbrain.soft_repair` | soft repair |
| adaptive_recovery | `allbrain.adaptive_recovery` | adaptive recovery |
| recovery_consensus | `allbrain.recovery_consensus` | recovery consensus |
| mitigation_learning | `allbrain.mitigation_learning` | mitigation learning |
| reliability | `allbrain.reliability` | `ReliabilityMetrics` |
| resilience | `allbrain.resilience` | resilience |

### `domains.learning/` — meta-learning & adaptation (12)

| Module | Current Path | Key Exports |
|---|---|---|
| learning | `allbrain.learning` | `CapabilityLearningManager` |
| learning_graph | `allbrain.learning_graph` | learning graph |
| learning_safety | `allbrain.learning_safety` | safe learning |
| meta_optimizer | `allbrain.meta_optimizer` | meta-optimizer |
| meta_scoring | `allbrain.meta_scoring` | meta-scoring |
| meta_meta_scoring | `allbrain.meta_meta_scoring` | meta-meta-scoring |
| meta_policy | `allbrain.meta_policy` | meta-policy |
| calibration | `allbrain.calibration` | calibration |
| capabilities | `allbrain.capabilities` | capability tracking |
| evolution | `allbrain.evolution` | evolutionary strategies |
| coevolution | `allbrain.coevolution` | co-evolution |
| self_play | `allbrain.self_play` | self-play |

### `domains.collaboration/` — multi-agent coordination (10)

| Module | Current Path | Key Exports |
|---|---|---|
| collaboration | `allbrain.collaboration` | `CollaborationManager` |
| conflict | `allbrain.conflict` | `ConflictDetector`, `ConflictResolver` |
| merge | `allbrain.merge` | `EventMergeEngine`, `StateMerger` |
| arbitration | `allbrain.arbitration` | `ArbitrationManager` |
| reputation | `allbrain.reputation` | reputation |
| distributed | `allbrain.distributed` | distributed coordination |
| workflow | `allbrain.workflow` | `WorkflowSnapshotBuilder` |
| workspace | `allbrain.workspace` | shared workspace |
| agents | `allbrain.agents` | agent management |
| routing | `allbrain.routing` | routing |

### `domains.analysis/` — situation understanding & anomaly (17)

| Module | Current Path | Key Exports |
|---|---|---|
| causal | `allbrain.causal` | `simulate_intervention` |
| belief | `allbrain.belief` | `BeliefManager` |
| evidence | `allbrain.evidence` | evidence |
| contradiction | `allbrain.contradiction` | `ContradictionDetector` |
| drift | `allbrain.drift` | drift detection |
| dynamics | `allbrain.dynamics` | capability dynamics |
| attention | `allbrain.attention` | attention |
| attribution | `allbrain.attribution` | attribution |
| compression | `allbrain.compression` | `EventCompressor` |
| episodic | `allbrain.episodic` | episodic memory |
| failure_memory | `allbrain.failure_memory` | failure memory |
| predictive_failure | `allbrain.predictive_failure` | predictive failure |
| semantic | `allbrain.semantic` | semantic analysis |
| world | `allbrain.world` | `WorldModel` |
| context | `allbrain.context` | `ParallelContextBuilder` |
| graph | `allbrain.graph` | graph analysis |
| fusion | `allbrain.fusion` | data fusion |

### `domains.memory/` — persistence, recall, observability (12)

| Module | Current Path | Key Exports |
|---|---|---|
| memory | `allbrain.memory` | `MemoryBuilder`, `MemoryRetriever` |
| replay | `allbrain.replay` | deterministic replay |
| resume | `allbrain.resume` | `OrchestratedResumeEngine` |
| telemetry | `allbrain.telemetry` | telemetry |
| observability | `allbrain.observability` | `ObservabilityBuilder` |
| metrics | `allbrain.metrics` | metrics |
| foundations | `allbrain.foundations` | `canonical_event_sort` |
| runtime_core | `allbrain.runtime_core` | `SystemDecisionPipeline` |
| gitbrain | `allbrain.gitbrain` | `GitBrain` |
| revision | `allbrain.revision` | revision tracking |
| ui | `allbrain.ui` | `TraceViewer`, `GraphExplorer` |
| api | `allbrain.api` | API layer |

## Dependency Graph

```mermaid
graph TD
    subgraph Infrastructure
        core[core/]
        storage[storage/]
        security[security/]
        events[events/]
        models[models/]
        server[server/]
        snapshot[snapshot/]
        orchestrator[orchestrator/]
        reducers[reducers/]
    end

    subgraph "Bounded Contexts (v0.4.0)"
        reasoning[reasoning/<br/>10 modules]
        governance[governance/<br/>12 modules]
        learning[learning/<br/>12 modules]
        collaboration[collaboration/<br/>10 modules]
        analysis[analysis/<br/>17 modules]
        memory[memory/<br/>12 modules]
    end

    reasoning --> core
    reasoning --> models
    reasoning --> events
    governance --> core
    governance --> models
    learning --> core
    learning --> models
    collaboration --> core
    collaboration --> server
    analysis --> core
    analysis --> events
    memory --> core
    memory --> storage

    server --> reasoning
    server --> governance
    server --> learning
    server --> collaboration
    server --> analysis
    server --> memory

    style reasoning fill:#4a9eff,color:#fff
    style governance fill:#ff6b6b,color:#fff
    style learning fill:#51cf66,color:#fff
    style collaboration fill:#ffd43b,color:#333
    style analysis fill:#cc5de8,color:#fff
    style memory fill:#ff922b,color:#fff
```

> **Golden Rule:** Bounded contexts may depend ONLY on Infrastructure.
> Context-to-context imports are forbidden.

## Module Coupling Ranking (v0.3.0 baseline)

External importer counts (excluding each module's own package and the
cross-cutting `reducers/` layer), plus test importers. Modules with
the lowest coupling are the safest v0.4.0 removal candidates.

| src importers (excl. reducers) | test importers | module |
|---:|---:|---|
| 0 | 2 | `drift` |
| 0 | 3 | `learning_graph` |
| 1 | 0 | `api` |
| 1 | 1 | `compression` |
| 1 | 1 | `distributed` |
| 1 | 1 | `policy` |
| 1 | 3 | `soft_repair` |
| 1 | 4 | `reputation` |
| 1 | 4 | `self_play` |
| 1 | 4 | `semantic` |
| 1 | 4 | `workspace` |

> **Note:** A strict "unused module" analysis (zero importers outside
> `reducers/`, zero in `server/tools/`, `cli/`, `install/`, tests) found
> **zero** modules — every domain package is reachable. The table above
> lists the lowest-coupling modules; `drift` and `learning_graph` have
> no production importer outside the reducer layer and are the leading
> v0.4.0 cleanup candidates.
