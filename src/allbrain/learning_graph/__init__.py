"""DEPRECATED: low-coupling module.

``allbrain.learning_graph`` has no server-tool, CLI, or public-API
importer (only the cross-cutting ``reducers/`` layer consumes it).
It remains functional but is slated for removal in v0.4.0. Migrate
any learning-graph usage to ``allbrain.domains.learning`` when available.
"""

import warnings

warnings.warn(
    "allbrain.learning_graph is deprecated and slated for removal in v0.4.0. "
    "It has no server-tool, CLI, or public-API importers (reducers/ only). "
    "Use allbrain.domains.learning from v0.4.0.",
    DeprecationWarning,
    stacklevel=2,
)

from allbrain.learning_graph.graph import LearningGraph  # noqa: E402
from allbrain.learning_graph.model import (  # noqa: E402
    LEARNING_GRAPH_MIN_DELTA,
    LEARNING_GRAPH_PARAM_BOUND,
    LEARNING_GRAPH_REWRITE_INTERVAL,
    LEARNING_GRAPH_TEMPLATE_VERSION,
    LearningNode,
    RewriteRecord,
)
from allbrain.learning_graph.node import NodeRegistry  # noqa: E402
from allbrain.learning_graph.rewriter import GraphRewriter  # noqa: E402

__all__ = [
    "LEARNING_GRAPH_TEMPLATE_VERSION",
    "LEARNING_GRAPH_REWRITE_INTERVAL",
    "LEARNING_GRAPH_MIN_DELTA",
    "LEARNING_GRAPH_PARAM_BOUND",
    "LearningNode",
    "RewriteRecord",
    "NodeRegistry",
    "LearningGraph",
    "GraphRewriter",
]
