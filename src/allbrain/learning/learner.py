from __future__ import annotations

from collections.abc import Iterable

from allbrain.learning.model import (
    INITIAL_CAPABILITY,
    LEARNING_EMA_BIAS,
    LEARNING_RETENTION,
)


def _stable_learning_id(key: str, event_ids: Iterable[str] | None = None) -> str:
    import hashlib

    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode()).digest()
    return f"learn-{d.hex()[:12]}"


def observation(*, success: bool, runtime_score: float, selection_score: float) -> float:
    raw = (1.0 if success else 0.0) * 0.5 + float(runtime_score) * 0.3 + float(selection_score) * 0.2
    return max(0.0, min(1.0, raw))


def ema_update(old_score: float, observation_val: float) -> float:
    raw = old_score * LEARNING_RETENTION + observation_val * LEARNING_EMA_BIAS
    return max(0.0, min(1.0, raw))
