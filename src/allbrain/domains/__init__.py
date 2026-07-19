"""Bounded context namespaces for AllBrain domain modules.

Six contexts consolidate 73 top-level packages (target: v0.4.0):

- ``domains.reasoning``     — decision-making and forward thinking (10 modules)
- ``domains.governance``    — safety, alignment, self-repair (12 modules)
- ``domains.learning``      — meta-learning and adaptation (12 modules)
- ``domains.collaboration`` — multi-agent coordination (10 modules)
- ``domains.analysis``      — situation understanding and anomaly detection (17 modules)
- ``domains.memory``        — persistence, recall, observability (12 modules)

Infrastructure (untouched): core, storage, security, events, models,
server, snapshot, orchestrator, reducers, config, cli, install, ops.

In Phase 1 the context packages are scaffold-only. Modules still live at
their original ``allbrain.<name>`` paths; this namespace is a forward-
compatible import surface. Mass moves happen in v0.4.0.
"""
