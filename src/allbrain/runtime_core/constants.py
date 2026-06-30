"""Runtime pipeline defaults and decision thresholds."""

from __future__ import annotations

# Pipeline execution defaults
DEFAULT_PIPELINE_EVENT_LIMIT = 5000
"""Default event limit per pipeline run."""

DEFAULT_RISK_THRESHOLD = 0.7
"""Default risk threshold for world-simulation blocking decisions."""

DEFAULT_REGRET_THRESHOLD = 0.20
"""Default regret threshold for counterfactual recommendations."""

DEFAULT_COUNTERFACTUAL_LIMIT = 3
"""Default number of counterfactual alternatives to generate."""

DEFAULT_SCENARIOS_LIMIT = 4
"""Default number of scenarios to generate."""

DEFAULT_SCENARIO_RECOMMENDATION_THRESHOLD = 0.50
"""Default threshold for scenario-based recommendations."""

DEFAULT_FORESIGHT_LIMIT = 5
"""Default number of foresight plans to generate."""

DEFAULT_MAX_HORIZON = 5
"""Default planning horizon in steps."""

# Objective defaults
DEFAULT_OBJECTIVE_PRIORITY = 3
"""Default priority for objectives and tasks (1=low, 5=critical)."""

DEFAULT_OBJECTIVE_CONFIDENCE = 0.75
"""Default confidence score for objectives and trajectories."""

DEFAULT_AUTONOMY_LEVEL = 2
"""Default current autonomy level (0=none, 5=full)."""

# Score thresholds
PREDICTION_ERROR_DELTA_THRESHOLD = 0.3
"""Minimum prediction-error delta to trigger an event."""

DEFAULT_HISTORICAL_SUCCESS_RATE = 0.7
"""Fallback historical success rate when no events exist."""

CAPABILITY_SCORE_MIN_DELTA = 0.02
"""Minimum capability-score change worth emitting an event."""

FORECAST_SIGNIFICANT_DIFFERENCE_THRESHOLD = 0.05
"""Forecast-vs-current capability difference threshold."""

DEFAULT_EXPLORATION_RATE = 0.05
"""Default meta-policy exploration rate."""

# Memory retrieval
DEFAULT_EPISODIC_RETRIEVAL_LIMIT = 5
"""Default episodic memory retrieval limit."""

DEFAULT_SEMANTIC_RETRIEVAL_LIMIT = 5
"""Default semantic memory retrieval limit."""
