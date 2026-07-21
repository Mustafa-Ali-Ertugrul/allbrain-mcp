"""DEPRECATED: low-coupling module.

``allbrain.drift`` is deprecated and slated for removal in v2.0.0.
It has no server-tool, CLI, or public-API importers (reducers/ only).
Use ``allbrain.domains.analysis.drift`` instead.
"""

import warnings

warnings.warn(
    "allbrain.drift is deprecated and slated for removal in v2.0.0. "
    "It has no server-tool, CLI, or public-API importers (reducers/ only). "
    "Use allbrain.domains.analysis.drift instead.",
    DeprecationWarning,
    stacklevel=2,
)

from allbrain.domains.analysis.drift.detector import (  # noqa: E402
    DRIFT_TEMPLATE_VERSION,
    DRIFT_THRESHOLD,
    REASONS,
    DriftSample,
    detect_drift,
)
from allbrain.domains.analysis.drift.events import make_payload, validate_payload  # noqa: E402

__all__ = [
    "DRIFT_TEMPLATE_VERSION",
    "DRIFT_THRESHOLD",
    "REASONS",
    "DriftSample",
    "detect_drift",
    "make_payload",
    "validate_payload",
]
