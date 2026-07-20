from __future__ import annotations

from allbrain.domains.reasoning.decision.model import DecisionContext, DecisionContract, DecisionMode


def resolve_mode(ctx: DecisionContext) -> DecisionMode:
    """Strict priority order using versioned contract.

    Refinement #2: mode selection depends only on explicit contract,
    NOT on presence-based None checks on context fields.
    """
    contract = ctx.contract
    if contract.is_debug():
        return DecisionMode.DEBUG
    if contract.has_signal("fusion"):
        return DecisionMode.FUSION
    if contract.has_signal("causal"):
        return DecisionMode.CAUSAL
    if contract.has_signal("dynamics"):
        return DecisionMode.DYNAMIC
    return DecisionMode.LEGACY


def make_contract(
    *,
    debug: bool = False,
    fusion: bool = False,
    causal: bool = False,
    dynamics: bool = False,
    version: int = 1,
) -> DecisionContract:
    signals: set[str] = set()
    if fusion:
        signals.add("fusion")
    if causal:
        signals.add("causal")
    if dynamics:
        signals.add("dynamics")
    return DecisionContract(version=version, active_signals=frozenset(signals), debug=debug)
