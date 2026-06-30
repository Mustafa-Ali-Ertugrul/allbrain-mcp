from __future__ import annotations

import json
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from allbrain.world.models import Prediction, WorldState
from allbrain.world.prediction import PredictionBridge

SIMILARITY_THRESHOLD = 0.3
_CONFIDENCE_K: float = 10.0


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
        confidence = (α + β) / (α + β + K)
    """

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        self._prior_alpha = prior_alpha
        self._prior_beta = prior_beta
        self._alphas: dict[str, float] = {}
        self._betas: dict[str, float] = {}
        self._costs: dict[str, list[float]] = defaultdict(list)
        self._failure_contexts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def update(
        self,
        action: str,
        success_weight: float = 1.0,
        failure_weight: float = 0.0,
        cost: float | None = None,
        context: dict[str, str] | None = None,
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
        context:
            Optional environment_state snapshot for failure context tracking.
        """
        if action not in self._alphas:
            self._alphas[action] = self._prior_alpha
            self._betas[action] = self._prior_beta
        self._alphas[action] += success_weight
        self._betas[action] += failure_weight
        if cost is not None:
            self._costs[action].append(cost)
        if failure_weight > 0.0 and context is not None:
            sig = json.dumps(context, sort_keys=True, default=str)
            self._failure_contexts[action][sig] += 1

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

            # Collect observation context for failure tracking
            obs_context: dict[str, str] | None = None

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
                obs_context = obs_env
            else:
                # When action is stored, still try to capture observation context
                caused_by = getattr(sim, "caused_by", None)
                if caused_by and caused_by in event_index:
                    obs = event_index[caused_by]
                    obs_payload = getattr(obs, "payload", None)
                    if isinstance(obs_payload, dict):
                        ec = obs_payload.get("environment_state")
                        if isinstance(ec, dict):
                            obs_context = ec

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

            self.update(action, success_weight, failure_weight, cost, context=obs_context)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def posterior(self, action: str) -> tuple[float, float] | None:
        """Return raw (α, β) posterior parameters for *action*.

        Returns None when no data has been recorded for *action*.
        """
        if action not in self._alphas:
            return None
        return (self._alphas[action], self._betas[action])

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
        confidence = total / (total + _CONFIDENCE_K)
        costs = self._costs.get(action)
        avg_cost = sum(costs) / len(costs) if costs else 0.25
        return (success_prob, risk, avg_cost, confidence)

    def failure_contexts(self, action: str) -> dict[str, int]:
        """Return the failure-context frequency map for *action*.

        Keys are JSON-serialized environment_state signatures; values are
        occurrence counts.  Empty dict when no failures recorded.
        """
        return dict(self._failure_contexts.get(action, {}))

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
            _sum += self._alphas[action] + self._betas[action] - self._prior_alpha - self._prior_beta
        return int(_sum)


_INTERNET_REQUIRED_ACTIONS: frozenset[str] = frozenset({"deploy", "run_tests"})


class LearnedPredictionBridge:
    """Bayesian-calibrated prediction bridge with context modulation.

    Delegates to the BetaPredictor for data-backed predictions and
    falls back to the hardcoded ``PredictionBridge`` for unknown
    actions or cold-start conditions.

    Applies contextual modulation rules on the raw Bayesian estimate:
    - Resource constraints (internet access).
    - Git state penalties (dirty working tree).
    - Test pass rate integration.
    """

    def __init__(
        self,
        predictor: BetaPredictor,
        fallback: PredictionBridge | None = None,
    ) -> None:
        self._predictor = predictor
        self._fallback = fallback or PredictionBridge()

    # ------------------------------------------------------------------
    # Context modulation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_git_dirty(env: dict[str, str]) -> bool:
        """Return True if the environment indicates a dirty git state."""
        return env.get("git_dirty") in {True, "True", "true", "1"}

    @staticmethod
    def _parse_test_pass_rate(env: dict[str, str]) -> float | None:
        """Parse test_pass_rate from environment_state string value."""
        raw = env.get("test_pass_rate")
        if raw is None:
            return None
        try:
            value = float(raw)
        except (ValueError, TypeError):
            return None
        if 0.0 <= value <= 1.0:
            return value
        return None

    @staticmethod
    def _compute_beta_stats(alpha: float, beta: float) -> tuple[float, float, float, float]:
        """Compute (mu, risk, confidence, uncertainty) from Beta(α, β).

        mu         = α / (α + β)          (posterior mean)
        risk       = 1 - mu
        confidence = (α+β) / (α+β+K)      (asymptotic → 1.0)
        uncertainty = variance / 0.25      (normalized, 0.25 = theoretical max)
        """
        total = alpha + beta
        mu = alpha / total
        risk = 1.0 - mu
        confidence = total / (total + _CONFIDENCE_K)
        variance = (alpha * beta) / (total * total * (total + 1.0))
        uncertainty = variance / 0.25
        return mu, risk, confidence, uncertainty

    def _modulate_for_context(
        self,
        state: WorldState,
        action: str,
        mu: float,
        risk: float,
    ) -> tuple[float, float, str | None]:
        """Apply contextual modulation rules to the base Bayesian estimate.

        Returns (modulated_mu, modulated_risk, context_note).
        """
        notes: list[str] = []

        # --- Resource constraint: no internet ---
        if action in _INTERNET_REQUIRED_ACTIONS and state.resources.get("internet") is False:
            return 0.0, 1.0, "no internet access"

        # --- Git state penalty (deploy only) ---
        if action == "deploy" and self._is_git_dirty(state.environment_state):
            mu *= 0.7
            risk = 1.0 - mu
            notes.append("git_dirty penalty applied")

        # --- Test pass rate integration (deploy only) ---
        if action == "deploy":
            rate = self._parse_test_pass_rate(state.environment_state)
            if rate is not None:
                # Centre-shifted modulation: rate>0.5 boosts, rate<0.5 penalises
                mu = min(1.0, mu * (0.5 + rate))
                risk = 1.0 - mu
                notes.append(f"test_pass_rate={rate:.2f}")

        context_note = "; ".join(notes) if notes else None
        return mu, risk, context_note

    # ------------------------------------------------------------------
    # Main evaluation
    # ------------------------------------------------------------------

    def evaluate(self, state: WorldState, action: str) -> Prediction:
        """Return a Prediction for *action* given *state*.

        Resolution order:
        1. Exact action match in BetaPredictor.
        2. Similar known action (string similarity).
        3. Hardcoded fallback PredictionBridge.
        """
        # 1. Exact match
        resolved_action = action
        alpha_beta = self._predictor.posterior(action)

        # 2. Similar action
        if alpha_beta is None:
            similar = self._predictor.find_similar_action(action)
            if similar is not None:
                resolved_action = similar
                alpha_beta = self._predictor.posterior(similar)

        # 3. Cold-start fallback
        if alpha_beta is None:
            return self._fallback.evaluate(state, action)

        alpha, beta = alpha_beta
        mu, risk, confidence, uncertainty = self._compute_beta_stats(alpha, beta)

        # Cost from the predictor's running average
        cost_result = self._predictor.predict(resolved_action)
        cost = cost_result[2] if cost_result is not None else 0.25

        # Context modulation
        mu, risk, context_note = self._modulate_for_context(state, action, mu, risk)

        explanation = self._explanation(resolved_action, confidence)
        if context_note:
            explanation += f" [{context_note}]"

        return Prediction(
            success_probability=mu,
            risk=risk,
            cost=cost,
            confidence=confidence,
            uncertainty=uncertainty,
            explanation=explanation,
        )

    @staticmethod
    def _explanation(action: str, confidence: float) -> str:
        obs = "sufficient" if confidence >= 0.4 else "limited"
        return (
            f"Beta-predicted {action}: posterior mean estimate with {obs} observations (confidence={confidence:.2f})."
        )
