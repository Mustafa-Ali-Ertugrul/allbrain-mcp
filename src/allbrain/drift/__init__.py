"""DEPRECATED: low-coupling module.

``allbrain.drift`` has no server-tool, CLI, or public-API importer
(only the cross-cutting ``reducers/`` layer consumes it). It remains
functional but is slated for removal in v0.4.0. Migrate any
drift-detection usage to ``allbrain.domains.analysis`` when available.
"""
import warnings

warnings.warn(
    "allbrain.drift is deprecated and slated for removal in v0.4.0. "
    "It has no server-tool, CLI, or public-API importers (reducers/ only). "
    "Use allbrain.domains.analysis from v0.4.0.",
    DeprecationWarning,
    stacklevel=2,
)

from allbrain.drift.detector import (
    DRIFT_TEMPLATE_VERSION,
    DRIFT_THRESHOLD,
    REASONS,
    DriftSample,
    detect_drift,
)
from allbrain.drift.events import make_payload, validate_payload

__all__ = [
    "DRIFT_TEMPLATE_VERSION",
    "DRIFT_THRESHOLD",
    "REASONS",
    "DriftSample",
    "detect_drift",
    "make_payload",
    "validate_payload",
]
