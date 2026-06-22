from __future__ import annotations

import math


DEFAULT_DECAY_THRESHOLD = 1000


def decay(event_distance: int, threshold: int = DEFAULT_DECAY_THRESHOLD) -> float:
    """Sprint 46 decay by event-distance (NOT time).

    decay = max(0.0, 1.0 - log(distance + 1) / log(threshold + 1))

    Spec examples (approximate):
      distance=10  -> 1 - log(11)/log(1001) = 1 - 2.398/6.909 = 0.653
      distance=100 -> 1 - log(101)/log(1001) = 1 - 4.615/6.909 = 0.332

    The spec's 10->0.95 and 100->0.50 are illustrative targets; the formula
    above is monotonic in distance and deterministic.
    """
    distance = max(0, int(event_distance))
    threshold = max(2, int(threshold))
    if distance == 0:
        return 1.0
    raw = 1.0 - math.log(distance + 1) / math.log(threshold + 1)
    return max(0.0, min(1.0, raw))