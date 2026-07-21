from __future__ import annotations

from types import SimpleNamespace
import pytest

from allbrain.events.schemas import EventType
from allbrain.meta_policy.estimator import (
    _stable_meta_id,
    compute_reward,
    estimate_mode_reward,
)
from allbrain.meta_policy.evaluator import (
    _to_prob_distribution,
    compute_kl_divergence,
    detect_policy_drift,
    should_snapshot,
)
from allbrain.meta_policy.events import (
    make_policy_drift_payload,
    make_policy_eval_payload,
    make_policy_update_payload,
    validate_policy_drift,
    validate_policy_eval,
    validate_policy_update,
)
from allbrain.meta_policy.learner import (
    _default_mode_stats,
    default_mode_stats,
    update_exploration_rate,
    update_mode_stats,
    update_temperature,
)
from allbrain.meta_policy.manager import MetaPolicyManager
from allbrain.meta_policy.model import ModeStats, PolicyMode, PolicyState
from allbrain.meta_policy.reducer import MetaPolicyReducer


class FakeEvent(SimpleNamespace):
    id: str
    type: str
    payload: dict | None
    created_at: str | None = None
    caused_by: str | None = None


def test_meta_policy_manager_select_update_query():
    manager = MetaPolicyManager()
    events = [
        FakeEvent(
            id="evt_tc1",
            type=EventType.TASK_COMPLETED.value,
            payload={"decision_id": "dec_1", "outcome_score": 0.9, "decision_score": 0.8},
        ),
        FakeEvent(id="evt_other", type="other", payload={"agent_id": "agent_1"}),
    ]

    mode = manager.select(events, agent_id="agent_1", task_type="coding", enable_drift_detection=True)
    assert isinstance(mode, str)

    # Update mode stats with matching decision_id
    reward = manager.update(
        events, agent_id="agent_1", mode=mode, decision_id="dec_1", task_type="coding"
    )
    assert reward is not None

    # Update with non-matching decision_id
    reward_none = manager.update(
        events, agent_id="agent_1", mode=mode, decision_id="dec_non_existent", task_type="coding"
    )
    assert reward_none is None

    # Query manager
    q = manager.query(events, agent_id="agent_1", task_type="coding")
    assert "mode" in q
    assert "exploration_rate" in q
    assert "temperature" in q
    assert q["decision_count"] >= 1

    keys = manager.known_keys(events)
    assert keys == {"agent_1"}


def test_meta_policy_estimator_functions():
    assert _stable_meta_id("key", None).startswith("meta-")
    r = compute_reward(decision_score=0.8, outcome_quality=0.9, stability_penalty=0.1)
    assert isinstance(r, float)

    events = [
        FakeEvent(
            id="evt_1",
            type=EventType.TASK_COMPLETED.value,
            payload={"decision_id": "dec_x", "success_score": 0.85, "decision_score": 0.75},
        ),
        FakeEvent(id="evt_2", type=EventType.TASK_COMPLETED.value, payload="invalid"),
    ]

    sig = estimate_mode_reward(
        mode=PolicyMode.FUSION.value,
        agent_id="a1",
        task_type="tt",
        decision_id="dec_x",
        events=events,
    )
    assert sig is not None
    assert sig.decision_id == "dec_x"
    assert sig.outcome_quality == 0.85

    sig_none = estimate_mode_reward(
        mode=PolicyMode.FUSION.value,
        agent_id="a1",
        task_type="tt",
        decision_id="missing",
        events=events,
    )
    assert sig_none is None


def test_meta_policy_evaluator_functions():
    stats_map = {
        "fusion": ModeStats(mode="fusion", count=1, avg_reward=0.8, ema_reward=0.8, variance=0.1),
        "causal": ModeStats(mode="causal", count=1, avg_reward=0.5, ema_reward=0.5, variance=0.1),
    }
    dist = _to_prob_distribution(stats_map)
    assert abs(sum(dist.values()) - 1.0) < 1e-6

    # Empty stats distribution
    empty_dist = _to_prob_distribution({})
    assert empty_dist == {}

    dist_old = {"fusion": 0.5, "causal": 0.5}
    dist_new = {"fusion": 0.9, "causal": 0.1}
    kl = compute_kl_divergence(dist_old, dist_new)
    assert kl > 0.0

    state_old = PolicyState(mode_stats=stats_map, exploration_rate=0.5, temperature=1.0, last_updated="", decision_count=10)
    state_new = PolicyState(mode_stats=stats_map, exploration_rate=0.5, temperature=1.0, last_updated="", decision_count=20)
    assert detect_policy_drift(state_old, state_new, threshold=10.0) is False
    assert should_snapshot(state_old) is True  # 10 % 10 == 0


def test_meta_policy_learner_functions():
    stats = ModeStats(mode="fusion", count=1, avg_reward=0.5, ema_reward=0.5, variance=0.1)
    updated = update_mode_stats(stats, reward=0.8)
    assert updated.count == 2
    assert updated.avg_reward == 0.65
    assert updated.ema_reward > 0.5

    t = update_temperature(1.0, 5)
    assert 0.1 <= t <= 1.0

    exp = update_exploration_rate(0.8, 5)
    assert 0.01 <= exp <= 1.0

    d1 = default_mode_stats()
    d2 = _default_mode_stats()
    assert len(d1) == 4
    assert len(d2) == 4


def test_meta_policy_reducer_and_events_validators():
    reducer = MetaPolicyReducer()
    eval_evt = FakeEvent(
        id="evt_1",
        type=EventType.POLICY_EVALUATED.value,
        payload=make_policy_eval_payload(agent_id="agent_1", task_type="coding", mode="fusion", exploration_rate=0.5),
    )
    update_evt = FakeEvent(
        id="evt_2",
        type=EventType.POLICY_UPDATED.value,
        payload=make_policy_update_payload(agent_id="agent_1", mode="fusion", reward=0.8, ema_reward=0.7, count=5),
    )
    drift_evt = FakeEvent(
        id="evt_3",
        type=EventType.POLICY_DIVERGENCE_DETECTED.value,
        payload=make_policy_drift_payload(agent_id="agent_1", kl_divergence=0.5, threshold=0.1, snapshot_id="snap_1"),
    )

    reducer.apply(eval_evt)
    reducer.apply(eval_evt)  # deduplication
    reducer.apply(update_evt)
    reducer.apply(drift_evt)

    # Invalid events
    reducer.apply(FakeEvent(id="inv_1", type=EventType.POLICY_EVALUATED.value, payload={"agent_id": ""}))
    reducer.apply(FakeEvent(id="inv_2", type=EventType.POLICY_UPDATED.value, payload={"reward": "nan"}))
    reducer.apply(FakeEvent(id="inv_3", type=EventType.POLICY_DIVERGENCE_DETECTED.value, payload={"kl_divergence": "nan"}))
    reducer.apply(FakeEvent(id="inv_4", type="other", payload=None))

    snap = reducer.snapshot(agent_id="agent_1")
    assert "eval" in snap
    assert "updates" in snap
    assert "drift" in snap

    all_snaps = reducer.all_snapshots()
    assert "agent_1" in all_snaps
    assert reducer.known_keys() == {"agent_1"}

    with pytest.raises(ValueError):
        validate_policy_eval({"agent_id": "a"})

    with pytest.raises(ValueError):
        validate_policy_update({"agent_id": "a", "reward": "bad"})

    with pytest.raises(ValueError):
        validate_policy_drift({"agent_id": "a", "kl_divergence": "bad"})
