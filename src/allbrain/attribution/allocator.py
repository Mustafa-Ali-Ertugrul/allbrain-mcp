from __future__ import annotations

from allbrain.attribution.model import (
    ATTRIBUTION_CF_CONFIDENCE,
    ATTRIBUTION_MIN_CONTRIBUTION,
    ATTRIBUTION_PROPORTIONAL_WEIGHT,
    CreditAllocation,
)


def allocate_credit(
    reward: float,
    contributors: dict[str, float],
    *,
    cf_scores: dict[str, float] | None = None,
) -> tuple[CreditAllocation, ...]:
    """Weighted proportional allocation with CF confidence bias (Refinement #1).

    credit = proportional_credit * 0.70 + counterfactual_credit * 0.30
    CF read is downweighted because it's not true causal inference.

    MIN_CONTRIBUTION floor: signals below threshold get redistributed.
    """
    if cf_scores is None:
        cf_scores = {}

    total_contrib = sum(contributors.values())
    if abs(total_contrib) < 1e-12:
        return ()

    proportional = {s: v / total_contrib for s, v in contributors.items()}

    allocations: list[CreditAllocation] = []
    for signal in contributors:
        p_credit = proportional.get(signal, 0.0)
        cf_credit = cf_scores.get(signal, 0.0) * ATTRIBUTION_CF_CONFIDENCE

        contribution = (
            ATTRIBUTION_PROPORTIONAL_WEIGHT * p_credit + (1.0 - ATTRIBUTION_PROPORTIONAL_WEIGHT) * cf_credit
        ) * reward

        confidence = ATTRIBUTION_PROPORTIONAL_WEIGHT + (1.0 - ATTRIBUTION_PROPORTIONAL_WEIGHT) * (
            0.0 if cf_scores.get(signal, 0.0) == 0.0 else 0.5
        )

        if abs(contribution) >= ATTRIBUTION_MIN_CONTRIBUTION:
            allocations.append(
                CreditAllocation(
                    signal=signal,
                    contribution=max(-1.0, min(1.0, contribution)),
                    confidence=confidence,
                )
            )

    return tuple(allocations)


def redistribute_below_min(
    allocations: list[CreditAllocation],
    reward: float,
) -> list[CreditAllocation]:
    """Redistribute contributions from signals below MIN_CONTRIBUTION to above-threshold ones."""
    above = [a for a in allocations if abs(a.contribution) >= ATTRIBUTION_MIN_CONTRIBUTION]
    if not above:
        return allocations
    remainder = reward - sum(a.contribution for a in above)
    each = remainder / len(above)
    return [
        CreditAllocation(
            signal=a.signal,
            contribution=max(-1.0, min(1.0, a.contribution + each)),
            confidence=a.confidence,
        )
        for a in above
    ]
