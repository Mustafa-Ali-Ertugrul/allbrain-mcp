"""DEPRECATED: low-coupling module.

``allbrain.domains.analysis.drift`` has no server-tool, CLI, or public-API importer
(only the cross-cutting ``reducers/`` layer consumes it). It remains
functional but is slated for removal in v0.5.0.
"""

import warnings

warnings.warn(
    "allbrain.drift is deprecated and slated for removal in v0.5.0. "
    "It has no server-tool, CLI, or public-API importers (reducers/ only).",
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
