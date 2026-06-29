from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from allbrain.world.models import Prediction, WorldState
from allbrain.world.prediction import PredictionBridge

SIMILARITY_THRESHOLD = 0.3


def _action_from_events(obs_env: dict[str, str], next_env: dict[str, str]) -> str:
    """Infer the action from the environment_state diff.

    Mirrors transition_learner._infer_action; duplicated here to keep
    prediction_learner self-contained with no cross-module coupling.
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


class BetaPredictor:
    """Per-action Bayesian Beta-distribution predictor.

    Maintains a Beta(α, β) posterior per action, starting from a
    Beta(prior_alpha, prior_beta) prior.  Call ``update`` to register
    observed outcomes (success/failure weights).  Call ``predict`` to
    retrieve the posterior mean, risk, average cost, and confidence.

    Confidence asymptotically approaches 1.0 as total observations grow:
        confidence = (α + β) / (α + β + 10)
    """

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        self._prior_alpha = prior_alpha
        self._prior_beta = prior_beta
        self._alphas: dict[str, float] = {}
        self._betas: dict[str, float] = {}
        self._costs: dict[str, list[float]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def update(
        self,
        action: str,
        success_weight: float = 1.0,
        failure_weight: float = 0.0,
        cost: float | None = None,
    ) -> None:
        """Update the Beta posterior for *action*.

        Parameters
        ----------
        action:
            The action key.
        success_weight:
            Evidence weight for "success" (added to α).
        failure_weight:
            Evidence weight for "failure" (added to β).
        cost:
            Observed cost for this outcome.  Stored for averaging.
        """
        if action not in self._alphas:
            self._alphas[action] = self._prior_alpha
            self._betas[action] = self._prior_beta
        self._alphas[action] += success_weight
        self._betas[action] += failure_weight
        if cost is not None:
            self._costs[action].append(cost)

    def learn_from_events(self, events: list[Any]) -> None:
        """Scan the event log and update the Beta posterior for each action.

        For each WORLD_SIMULATION_RUN event linked via ``caused_by`` to a
        preceding WORLD_STATE_OBSERVED, the action is inferred from the
        environment-state diff.  The event's ``impact_score`` (stored risk)
        is used as failure weight, and ``1 - impact_score`` as success
        weight.  Cost is read from the prediction payload.
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

            # Use stored action when available (preferred — no inference needed)
            action = payload.get("action")

            if action is None:
                # Fall back to env-diff inference via caused_by chain
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

                action = _action_from_events(obs_env, next_env)

            # Impact score (stored risk) as failure signal
            impact_score = getattr(sim, "impact_score", None)
            if isinstance(impact_score, (int, float)):
                failure_weight = float(impact_score)
                success_weight = 1.0 - failure_weight
            else:
                failure_weight = 0.0
                success_weight = 1.0

            # Cost from prediction payload
            pred = payload.get("prediction")
            cost = None
            if isinstance(pred, dict):
                cost = pred.get("cost")

            self.update(action, success_weight, failure_weight, cost)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def predict(self, action: str) -> tuple[float, float, float, float] | None:
        """Return (success_probability, risk, avg_cost, confidence) for *action*.

        Returns None when no data has been recorded for *action*.
        """
        if action not in self._alphas:
            return None
        a = self._alphas[action]
        b = self._betas[action]
        total = a + b
        success_prob = a / total
        risk = 1.0 - success_prob
        confidence = total / (total + 10.0)
        costs = self._costs.get(action)
        avg_cost = sum(costs) / len(costs) if costs else 0.25
        return (success_prob, risk, avg_cost, confidence)

    def find_similar_action(self, action: str) -> str | None:
        """Find the most similar known action via Gestalt pattern matching.

        Returns None if no action exceeds SIMILARITY_THRESHOLD.
        """
        best_action: str | None = None
        best_score = 0.0
        for known in self._alphas:
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
        return set(self._alphas.keys())

    @property
    def total_observations(self) -> int:
        _sum = 0
        for action in self._alphas:
            _sum += (
                self._alphas[action]
                + self._betas[action]
                - self._prior_alpha
                - self._prior_beta
            )
        return int(_sum)


class LearnedPredictionBridge:
    """Stochastic prediction bridge using a BetaPredictor.

    Delegates to the BetaPredictor for data-backed predictions and
    falls back to the hardcoded ``PredictionBridge`` for unknown
    actions or cold-start conditions.
    """

    def __init__(
        self,
        predictor: BetaPredictor,
        fallback: PredictionBridge | None = None,
    ) -> None:
        self._predictor = predictor
        self._fallback = fallback or PredictionBridge()

    def evaluate(self, state: WorldState, action: str) -> Prediction:
        """Return a Prediction for *action* given *state*.

        Resolution order:
        1. Exact action match in BetaPredictor.
        2. Similar known action (string similarity).
        3. Hardcoded fallback PredictionBridge.
        """
        # 1. Exact match
        result = self._predictor.predict(action)

        # 2. Similar action
        if result is None:
            similar = self._predictor.find_similar_action(action)
            if similar is not None:
                result = self._predictor.predict(similar)

        # 3. Fallback
        if result is None:
            return self._fallback.evaluate(state, action)

        success_prob, risk, cost, confidence = result
        return Prediction(
            success_probability=success_prob,
            risk=risk,
            cost=cost,
            confidence=confidence,
            explanation=self._explanation(action, confidence),
        )

    @staticmethod
    def _explanation(action: str, confidence: float) -> str:
        obs = "sufficient" if confidence >= 0.4 else "limited"
        return (
            f"Beta-predicted {action}: posterior mean estimate "
            f"with {obs} observations (confidence={confidence:.2f})."
        )
