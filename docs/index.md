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

These sprint documents record the design decisions and architecture evolution for each subsystem. They are kept for reference; the [System Architecture](ARCHITECTURE.md) document is the current single source of truth.

### Foundations & Runtime Core

| Sprint | Topic |
|---|---|
| [sprint41](sprint41_foundations_hardening.md) | Foundations hardening |
| [sprint41_1](sprint41_1_hotfix.md) | Hotfix round |
| [sprint41_2](sprint41_2_projection_ordering.md) | Projection ordering |
| [sprint32](sprint32_system_integration_runtime_core_architecture.md) | System integration & runtime core architecture |
| [sprint28](sprint28_execution_intelligence_architecture.md) | Execution intelligence architecture |
| [sprint27](sprint27_economic_layer_architecture.md) | Economic layer architecture |
| [sprint25](sprint25_resource_management_architecture.md) | Resource management architecture |

### Governance & Policy

| Sprint | Topic |
|---|---|
| [sprint31](sprint31_autonomous_governance_alignment_architecture.md) | Autonomous governance & alignment |
| [sprint30](sprint30_meta_optimization_architecture.md) | Meta-optimization |
| [sprint29](sprint29_decision_arbitration_self_reflection_architecture.md) | Decision arbitration & self-reflection |
| [sprint23](sprint23_self_evolution_architecture.md) | Self-evolution architecture |
| [sprint22](sprint22_organization_layer_architecture.md) | Organization layer |
| [sprint21](sprint21_policy_engine_architecture.md) | Policy engine architecture |

### World Model & Reasoning Layers

| Sprint | Topic |
|---|---|
| [sprint33](sprint33_world_model.md) | World model |
| [sprint34](sprint34_counterfactual_reasoning.md) | Counterfactual reasoning |
| [sprint35](sprint35_scenario_planning.md) | Scenario planning |
| [sprint36](sprint36_strategic_foresight.md) | Strategic foresight |
| [sprint37](sprint37_meta_reasoning.md) | Meta-reasoning |
| [sprint38](sprint38_uncertainty_epistemic_reasoning.md) | Uncertainty & epistemic reasoning |
| [sprint39](sprint39_information_seeking.md) | Information seeking |

### Memory & State Projections

| Sprint | Topic |
|---|---|
| [sprint43](sprint43_contradiction_event_sourcing.md) | Contradiction & event sourcing |
| [sprint44](sprint44_belief_revision.md) | Belief revision |
| [sprint45](sprint45_uncertainty_integration.md) | Uncertainty integration |
| [sprint46](sprint46_evidence_trust_layer.md) | Evidence & trust layer |
| [sprint47](sprint47_calibration_drift.md) | Calibration & drift |
| [sprint60](sprint60_attention.md) | Attention mechanism |
| [sprint61](sprint61_workspace.md) | Workspace |
| [sprint62](sprint62_episodic.md) | Episodic memory |
| [sprint63](sprint63_semantic.md) | Semantic memory |

### Learning & Capability Signals

| Sprint | Topic |
|---|---|
| [sprint15](sprint15_collaboration_architecture.md) | Collaboration architecture |
| [sprint16](sprint16_organizational_learning_architecture.md) | Organizational learning |
| [sprint52](sprint52_capabilities.md) | Capabilities |
| [sprint53](sprint53_capability_learning.md) | Capability learning |
| [sprint54](sprint54_dynamics.md) | Dynamics |
| [sprint55](sprint55_attribution.md) | Attribution |
| [sprint56](sprint56_fusion.md) | Fusion |
| [sprint57](sprint57_drift.md) | Drift |
| [sprint58](sprint58_meta_policy.md) | Meta-policy |
| [sprint59](sprint59_signal_rewards.md) | Signal & rewards |

### Recovery & Reliability

| Sprint | Topic |
|---|---|
| [sprint13](sprint13_reliability_architecture.md) | Reliability architecture |
| [sprint14](sprint14_distributed_resilience_architecture.md) | Distributed resilience |
| [sprint64](sprint64_failure_memory.md) | Failure memory |
| [sprint65](sprint65_recovery_consensus.md) | Recovery consensus |
| [sprint66](sprint66_adaptive_recovery.md) | Adaptive recovery |
| [sprint67](sprint67_learning_safety.md) | Learning safety |
| [sprint68](sprint68_predictive_failure.md) | Predictive failure |
| [sprint69](sprint69_mitigation_learning.md) | Mitigation learning |

### Routing, Telemetry & Coordination

| Sprint | Topic |
|---|---|
| [sprint48](sprint48_reputation.md) | Reputation |
| [sprint49](sprint49_arbitration.md) | Arbitration |
| [sprint50](sprint50_telemetry.md) | Telemetry |
| [sprint51](sprint51_routing.md) | Routing |
