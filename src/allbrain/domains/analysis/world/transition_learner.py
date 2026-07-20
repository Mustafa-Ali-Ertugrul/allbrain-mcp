from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from allbrain.domains.analysis.world.models import WorldState

MIN_SAMPLES = 3
SIMILARITY_THRESHOLD = 0.3


def _state_signature(environment_state: dict[str, str]) -> str:
    """Deterministic hash of environment_state for transition pattern matching.

    Only hashes environment_state (not resources or system_state) because
    environment_state captures the domain-relevant conditions (tests passed,
    deployment running, etc.) while resources are hard preconditions and
    system_state is runtime-dependent noise.
    """
    canonical = json.dumps(environment_state, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _infer_action(obs_env: dict[str, str], next_env: dict[str, str]) -> str:
    """Infer the action from the environment_state diff between observation and next_state.

    This is a heuristic for event logs that don't store the action directly.
    It mirrors the hardcoded _ACTION_ENV mapping in StateTransitionBridge.
    Checks for key presence rather than specific values — e.g. any change to
    the ``tests`` key (passed OR failed) is inferred as ``run_tests``.
    """
    changed: dict[str, str] = {}
    for k, v in next_env.items():
        if obs_env.get(k) != v:
            changed[k] = v

    if "deployment" in changed:
        value = changed["deployment"]
        if value == "rolled_back":
            return "rollback"
        if value == "scaled":
            return "scale"
        return "deploy"
    if "tests" in changed:
        return "run_tests"
    return "unknown"


class TransitionLearner:
    """Learns transition patterns from the event log.

    Scans WORLD_STATE_OBSERVED → WORLD_SIMULATION_RUN pairs (linked via
    caused_by) and builds a frequency table of (state, action) → next_state
    transitions.  The action is inferred from the environment_state diff
    between observation and simulation next_state.
    """

    def __init__(self) -> None:
        # (state_sig, action) → {next_state_sig: count}
        self._transitions: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # action → total count
        self._action_counts: dict[str, int] = defaultdict(int)
        # state_sig → representative environment_state dict
        self._state_samples: dict[str, dict[str, str]] = {}
        # next_state_sig → representative environment_state dict
        self._next_state_samples: dict[str, dict[str, str]] = {}
        # all known actions seen during learning
        self._known_actions: set[str] = set()

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def learn(self, events: list[Any]) -> None:
        """Extract transition patterns from the event log.

        For each WORLD_SIMULATION_RUN event, follows caused_by to the
        preceding WORLD_STATE_OBSERVED, infers the action from the
        environment_state diff, and records the transition.
        """
        event_index: dict[str, Any] = {}
        simulations: list[Any] = []

        for event in events:
            eid = getattr(event, "id", None)
            etype = str(getattr(event, "type", ""))
            if eid:
                event_index[eid] = event
            if etype == "world_simulation_run":
                simulations.append(event)

        for sim in simulations:
            payload = getattr(sim, "payload", None)
            if not isinstance(payload, dict):
                continue

            caused_by = getattr(sim, "caused_by", None)
            if not caused_by or caused_by not in event_index:
                continue

            obs = event_index[caused_by]
            obs_payload = getattr(obs, "payload", None)
            if not isinstance(obs_payload, dict):
                continue

            obs_env = obs_payload.get("environment_state")
            if not isinstance(obs_env, dict):
                continue

            next_state = payload.get("next_state")
            if not isinstance(next_state, dict):
                continue

            next_env = next_state.get("environment_state")
            if not isinstance(next_env, dict):
                continue

            # Use stored action when available; fall back to env-diff inference
            action = payload.get("action") or _infer_action(obs_env, next_env)
            state_sig = _state_signature(obs_env)
            next_sig = _state_signature(next_env)

            self._transitions[(state_sig, action)][next_sig] += 1
            self._action_counts[action] += 1
            self._known_actions.add(action)

            if state_sig not in self._state_samples:
                self._state_samples[state_sig] = dict(obs_env)
            if next_sig not in self._next_state_samples:
                self._next_state_samples[next_sig] = dict(next_env)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def predict_distribution(self, state: WorldState, action: str) -> list[tuple[dict[str, str], float]]:
        """Return the probability distribution over next environment_states.

        Each entry is (environment_state_dict, probability).
        Returns an empty list when fewer than MIN_SAMPLES transitions exist
        for the given (state, action) pair.
        """
        state_sig = _state_signature(state.environment_state)
        key = (state_sig, action)
        transitions = self._transitions.get(key)
        if not transitions:
            return []

        total = sum(transitions.values())
        if total < MIN_SAMPLES:
            return []

        result: list[tuple[dict[str, str], float]] = []
        for next_sig, count in transitions.items():
            env = self._next_state_samples.get(next_sig)
            if env is not None:
                result.append((dict(env), count / total))
        return result

    def find_similar_action(self, action: str) -> str | None:
        """Find the most similar known action using Gestalt pattern matching.

        Returns None if no action exceeds SIMILARITY_THRESHOLD.
        """
        best_action: str | None = None
        best_score = 0.0
        for known in self._known_actions:
            score = SequenceMatcher(None, action, known).ratio()
            if score > best_score and score >= SIMILARITY_THRESHOLD:
                best_score = score
                best_action = known
        return best_action

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def known_actions(self) -> set[str]:
        return set(self._known_actions)

    @property
    def total_transitions(self) -> int:
        return sum(sum(d.values()) for d in self._transitions.values())

    @property
    def state_count(self) -> int:
        return len(self._state_samples)
