from __future__ import annotations

from typing import Any

from allbrain.attribution.model import ATTRIBUTION_CF_CONFIDENCE
from allbrain.causal import simulate_intervention


def estimate_signal_impact(
    *,
    signal: str,
    agent_id: str,
    task_type: str,
    actual_agent: str,
    events: list[Any],
    event_ids: list[str] | None = None,
) -> float:
    """Read-only Sprint 55 reuse: 'this signal olmasa outcome ne olurdu?'

    CF confidence bias (Refinement #1):
    Returns impact score * ATTRIBUTION_CF_CONFIDENCE.
    Because this is NOT true causal inference — it's a projection
    approximation. Downweighted to prevent overconfident attribution.
    """
    try:
        result = simulate_intervention(
            agent_id=agent_id,
            task_type=task_type,
            actual_agent=actual_agent,
            alternative_agent=actual_agent,
            events=events,
            event_ids=event_ids,
        )
        impact = result.impact_score
        return max(-1.0, min(1.0, impact * ATTRIBUTION_CF_CONFIDENCE))
    except Exception:
        return 0.0
