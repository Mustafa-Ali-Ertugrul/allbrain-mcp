from __future__ import annotations

from typing import Any

from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.domains.learning.meta_policy.estimator import estimate_mode_reward
from allbrain.domains.learning.meta_policy.evaluator import detect_policy_drift, should_snapshot
from allbrain.domains.learning.meta_policy.learner import _default_mode_stats, update_mode_stats
from allbrain.domains.learning.meta_policy.model import (
    META_POLICY_EXPLORATION_MAX,
    META_POLICY_TEMPERATURE_INIT,
    ModeStats,
    PolicyState,
)
from allbrain.domains.learning.meta_policy.selector import select_mode


class MetaPolicyManager:
    def __init__(self) -> None:
        self._snapshot: PolicyState | None = None
        self._policy_state: PolicyState | None = None

    def select(
        self,
        events: list[Any],
        *,
        agent_id: str = "default",
        task_type: str = "default",
        enable_drift_detection: bool = False,
    ) -> str:
        ordered = canonical_event_sort(events)

        if self._policy_state is None:
            self._policy_state = self._build_policy_state(ordered, agent_id=agent_id)

        mode = select_mode(self._policy_state, agent_id=agent_id, task_type=task_type)

        self._policy_state = PolicyState(
            mode_stats=self._policy_state.mode_stats,
            exploration_rate=self._policy_state.exploration_rate,
            temperature=self._policy_state.temperature,
            last_updated=ordered[-1].id if ordered else "",
            decision_count=self._policy_state.decision_count + 1,
        )

        if enable_drift_detection and should_snapshot(self._policy_state):
            if self._snapshot and detect_policy_drift(self._snapshot, self._policy_state):
                self._policy_state = PolicyState(
                    mode_stats=self._snapshot.mode_stats,
                    exploration_rate=self._snapshot.exploration_rate,
                    temperature=self._snapshot.temperature,
                    last_updated=self._policy_state.last_updated,
                    decision_count=self._policy_state.decision_count,
                    drift_detected=True,
                    snapshot_id=str(self._snapshot.decision_count),
                )
            self._snapshot = self._policy_state

        return mode

    def update(
        self,
        events: list[Any],
        *,
        agent_id: str,
        mode: str,
        decision_id: str,
        task_type: str,
    ) -> float | None:
        ordered = canonical_event_sort(events)
        reward_signal = estimate_mode_reward(
            mode=mode,
            agent_id=agent_id,
            task_type=task_type,
            decision_id=decision_id,
            events=ordered,
        )

        if reward_signal is None:
            return None

        if self._policy_state is None:
            self._policy_state = self._build_policy_state(ordered, agent_id=agent_id)

        stats = self._policy_state.mode_stats.get(mode)
        if stats is None:
            stats = ModeStats(mode=mode, count=0, avg_reward=0.0, ema_reward=0.0, variance=0.0)

        updated = update_mode_stats(stats, reward_signal.reward)
        new_stats = dict(self._policy_state.mode_stats)
        new_stats[mode] = updated

        self._policy_state = PolicyState(
            mode_stats=new_stats,
            exploration_rate=self._policy_state.exploration_rate,
            temperature=self._policy_state.temperature,
            last_updated=ordered[-1].id if ordered else "",
            decision_count=self._policy_state.decision_count,
        )

        return reward_signal.reward

    def _build_policy_state(self, events: list[Any], *, agent_id: str) -> PolicyState:
        stats = _default_mode_stats()
        return PolicyState(
            mode_stats=stats,
            exploration_rate=META_POLICY_EXPLORATION_MAX,
            temperature=META_POLICY_TEMPERATURE_INIT,
            last_updated=events[-1].id if events else "",
            decision_count=0,
        )

    def query(self, events: list[Any], *, agent_id: str, task_type: str) -> dict[str, Any]:
        mode = self.select(events, agent_id=agent_id, task_type=task_type)
        state = self._policy_state
        return {
            "mode": mode,
            "exploration_rate": state.exploration_rate if state else 0.0,
            "temperature": state.temperature if state else 1.0,
            "decision_count": state.decision_count if state else 0,
        }

    def known_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                aid = payload.get("agent_id")
                if isinstance(aid, str) and aid:
                    keys.add(aid)
        return keys
