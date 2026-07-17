# AllBrain Documentation

AllBrain MCP is an event-sourced memory and orchestration server for multi-agent work. See [README](../README.md) for a high-level introduction.

## Quick start

- [Installation & MCP setup](setup.md)
- [README — example flow and status](../README.md)

## Architecture

| Document | What it covers |
|---|---|
| [System Architecture](ARCHITECTURE.md) | Central architecture map — bounded contexts, event model, pipeline, storage, security |
| [Code quality audit](code-quality-audit.md) | Dated, reproducible architecture and quality verification |
| [Domain boundaries & import rules](domain_boundaries.md) | CI-enforced ownership rules across allbrain packages |
| [Database scaling policy](database_scaling_policy.md) | SQLite defaults, Postgres CI target, migration guidance |
| [Custom-agent integration](custom-agent-integration.md) | Python and TypeScript clients over MCP stdio |
| [Two-agent SQLite pilot](two-agent-pilot.md) | Code/security collaboration checks and extracted SDK patterns |
| [Repository context-aware API](repository_context_aware_api.md) | Multi-repository API design and usage |

## Security & operations

| Document | What it covers |
|---|---|
| [Security hardening summary](../SUMMARY.md) | Historical security-hardening sprint record |

## Historical design records (sprints)

These sprint documents record the design decisions and architecture evolution for each subsystem. They are kept for reference under [sprints/](sprints/README.md); the [System Architecture](ARCHITECTURE.md) and [package maturity](package-maturity.md) documents are the current sources of truth.

### Foundations & Runtime Core

| Sprint | Topic |
|---|---|
| [sprint41](sprints/sprint41_foundations_hardening.md) | Foundations hardening |
| [sprint41_1](sprints/sprint41_1_hotfix.md) | Hotfix round |
| [sprint41_2](sprints/sprint41_2_projection_ordering.md) | Projection ordering |
| [sprint32](sprints/sprint32_system_integration_runtime_core_architecture.md) | System integration & runtime core architecture |
| [sprint28](sprints/sprint28_execution_intelligence_architecture.md) | Execution intelligence architecture |
| [sprint27](sprints/sprint27_economic_layer_architecture.md) | Economic layer architecture |
| [sprint25](sprints/sprint25_resource_management_architecture.md) | Resource management architecture |

### Governance & Policy

| Sprint | Topic |
|---|---|
| [sprint31](sprints/sprint31_autonomous_governance_alignment_architecture.md) | Autonomous governance & alignment |
| [sprint30](sprints/sprint30_meta_optimization_architecture.md) | Meta-optimization |
| [sprint29](sprints/sprint29_decision_arbitration_self_reflection_architecture.md) | Decision arbitration & self-reflection |
| [sprint23](sprints/sprint23_self_evolution_architecture.md) | Self-evolution architecture |
| [sprint22](sprints/sprint22_organization_layer_architecture.md) | Organization layer |
| [sprint21](sprints/sprint21_policy_engine_architecture.md) | Policy engine architecture |

### World Model & Reasoning Layers

| Sprint | Topic |
|---|---|
| [sprint33](sprints/sprint33_world_model.md) | World model |
| [sprint34](sprints/sprint34_counterfactual_reasoning.md) | Counterfactual reasoning |
| [sprint35](sprints/sprint35_scenario_planning.md) | Scenario planning |
| [sprint36](sprints/sprint36_strategic_foresight.md) | Strategic foresight |
| [sprint37](sprints/sprint37_meta_reasoning.md) | Meta-reasoning |
| [sprint38](sprints/sprint38_uncertainty_epistemic_reasoning.md) | Uncertainty & epistemic reasoning |
| [sprint39](sprints/sprint39_information_seeking.md) | Information seeking |

### Memory & State Projections

| Sprint | Topic |
|---|---|
| [sprint43](sprints/sprint43_contradiction_event_sourcing.md) | Contradiction & event sourcing |
| [sprint44](sprints/sprint44_belief_revision.md) | Belief revision |
| [sprint45](sprints/sprint45_uncertainty_integration.md) | Uncertainty integration |
| [sprint46](sprints/sprint46_evidence_trust_layer.md) | Evidence & trust layer |
| [sprint47](sprints/sprint47_calibration_drift.md) | Calibration & drift |
| [sprint60](sprints/sprint60_attention.md) | Attention mechanism |
| [sprint61](sprints/sprint61_workspace.md) | Workspace |
| [sprint62](sprints/sprint62_episodic.md) | Episodic memory |
| [sprint63](sprints/sprint63_semantic.md) | Semantic memory |

### Learning & Capability Signals

| Sprint | Topic |
|---|---|
| [sprint15](sprints/sprint15_collaboration_architecture.md) | Collaboration architecture |
| [sprint16](sprints/sprint16_organizational_learning_architecture.md) | Organizational learning |
| [sprint52](sprints/sprint52_capabilities.md) | Capabilities |
| [sprint53](sprints/sprint53_capability_learning.md) | Capability learning |
| [sprint54](sprints/sprint54_dynamics.md) | Dynamics |
| [sprint55](sprints/sprint55_attribution.md) | Attribution |
| [sprint56](sprints/sprint56_fusion.md) | Fusion |
| [sprint57](sprints/sprint57_drift.md) | Drift |
| [sprint58](sprints/sprint58_meta_policy.md) | Meta-policy |
| [sprint59](sprints/sprint59_signal_rewards.md) | Signal & rewards |

### Recovery & Reliability

| Sprint | Topic |
|---|---|
| [sprint13](sprints/sprint13_reliability_architecture.md) | Reliability architecture |
| [sprint14](sprints/sprint14_distributed_resilience_architecture.md) | Distributed resilience |
| [sprint64](sprints/sprint64_failure_memory.md) | Failure memory |
| [sprint65](sprints/sprint65_recovery_consensus.md) | Recovery consensus |
| [sprint66](sprints/sprint66_adaptive_recovery.md) | Adaptive recovery |
| [sprint67](sprints/sprint67_learning_safety.md) | Learning safety |
| [sprint68](sprints/sprint68_predictive_failure.md) | Predictive failure |
| [sprint69](sprints/sprint69_mitigation_learning.md) | Mitigation learning |

### Routing, Telemetry & Coordination

| Sprint | Topic |
|---|---|
| [sprint48](sprints/sprint48_reputation.md) | Reputation |
| [sprint49](sprints/sprint49_arbitration.md) | Arbitration |
| [sprint50](sprints/sprint50_telemetry.md) | Telemetry |
| [sprint51](sprints/sprint51_routing.md) | Routing |
