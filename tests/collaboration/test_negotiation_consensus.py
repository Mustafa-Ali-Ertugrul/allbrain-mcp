from __future__ import annotations

from allbrain.domains.collaboration.collaboration import ConsensusEngine, NegotiationEngine, Vote


def test_negotiation_success_with_counter_proposal() -> None:
    engine = NegotiationEngine()
    state = engine.start(["architect", "reviewer"])
    first = engine.propose(state, agent_id="architect", content="Plan A")
    state.reject(first.proposal_id)
    second = engine.counter(state, agent_id="reviewer", content="Plan B")
    state.accept(second.proposal_id)

    assert state.status == "accepted"
    assert state.proposals[0]["status"] == "rejected"
    assert state.proposals[1]["status"] == "accepted"


def test_negotiation_timeout() -> None:
    state = NegotiationEngine().start(["a", "b"])
    state.timeout()
    assert state.status == "timeout"


def test_consensus_modes() -> None:
    engine = ConsensusEngine()
    votes = [Vote("a", True), Vote("b", True), Vote("c", False)]

    assert engine.majority(votes).approved
    assert engine.weighted([Vote("a", True, 0.7), Vote("b", False, 0.3)], threshold=0.6).approved
    assert not engine.unanimous(votes).approved
    assert engine.unanimous([Vote("a", True), Vote("b", True)]).approved
