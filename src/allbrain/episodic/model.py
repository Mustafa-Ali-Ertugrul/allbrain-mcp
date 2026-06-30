from __future__ import annotations

from dataclasses import dataclass, field

MAX_EPISODES = 1000
IMPORTANCE_THRESHOLD = 0.50
DEFAULT_RETRIEVAL_LIMIT = 5
EPISODIC_TEMPLATE_VERSION = 1
HIGH_REWARD_THRESHOLD = 0.80
LOW_REWARD_THRESHOLD = 0.20
NOVELTY_SAMPLE_WINDOW = 5


@dataclass(frozen=True)
class Episode:
    episode_id: str
    timestamp: int
    reward: float
    importance: float
    workspace_items: tuple[str, ...]
    decision_id: str
    retrieval_count: int = 0
    last_retrieved: int | None = None


@dataclass(frozen=True)
class EpisodicState:
    episodes: tuple[Episode, ...]
    total_episodes: int
    retained_episodes: int
    forgotten_episodes: int = 0
    version: int = EPISODIC_TEMPLATE_VERSION
