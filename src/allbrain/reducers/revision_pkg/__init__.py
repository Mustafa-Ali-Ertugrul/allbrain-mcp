"""Revision sub-reducer package.

Breaks the former monolithic ``RevisionReducer`` (reducers/core.py) into
focused, single-responsibility units: belief/contradiction, signal values
(uncertainty / trust / calibration / drift), and scalar agent signals.  The
``RevisionReducer`` facade composes them and preserves the original public
contract so existing imports keep working.
"""

from __future__ import annotations

from allbrain.reducers.revision_pkg._state import SeenIds
from allbrain.reducers.revision_pkg.belief import BeliefRevisionSubReducer
from allbrain.reducers.revision_pkg.reducer import RevisionReducer
from allbrain.reducers.revision_pkg.scalars import ScalarSubReducer
from allbrain.reducers.revision_pkg.signals import (
    CalibrationSubReducer,
    DriftSubReducer,
    TrustSubReducer,
    UncertaintySubReducer,
)

__all__ = [
    "SeenIds",
    "BeliefRevisionSubReducer",
    "UncertaintySubReducer",
    "TrustSubReducer",
    "CalibrationSubReducer",
    "DriftSubReducer",
    "ScalarSubReducer",
    "RevisionReducer",
]
