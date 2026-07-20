from __future__ import annotations

from allbrain.domains.analysis.belief.models import BeliefState


def beta_mean(alpha: float, beta: float) -> float:
    if alpha <= 0.0 or beta <= 0.0:
        raise ValueError("alpha and beta must be positive")
    return alpha / (alpha + beta)


def beta_variance(alpha: float, beta: float) -> float:
    if alpha <= 0.0 or beta <= 0.0:
        raise ValueError("alpha and beta must be positive")
    total = alpha + beta
    return (alpha * beta) / (total * total * (total + 1.0))


def beta_info_gain(alpha: float, beta: float) -> float:
    if alpha <= 0.0 or beta <= 0.0:
        raise ValueError("alpha and beta must be positive")
    mean = beta_mean(alpha, beta)
    var_success = beta_variance(alpha + 1.0, beta)
    var_failure = beta_variance(alpha, beta + 1.0)
    expected_var_after = mean * var_success + (1.0 - mean) * var_failure
    current_var = beta_variance(alpha, beta)
    return max(0.0, current_var - expected_var_after)


def update_state(
    *,
    context_key: str,
    successes: int,
    failures: int,
    blocked: int,
    prior_alpha: float,
    prior_beta: float,
    sample_count: int,
    analysis_id: str,
) -> BeliefState:
    alpha = prior_alpha + successes
    beta = prior_beta + failures + blocked
    return BeliefState(
        context_key=context_key,
        alpha=alpha,
        beta=beta,
        sample_count=sample_count,
        successes=successes,
        failures=failures,
        blocked=blocked,
        analysis_id=analysis_id,
        mean=round(beta_mean(alpha, beta), 6),
        variance=round(beta_variance(alpha, beta), 6),
        info_gain=round(beta_info_gain(alpha, beta), 6),
    )
