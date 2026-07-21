from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from math import sqrt
from typing import Any

VECTOR_SIZE = 32


@dataclass(frozen=True)
class MemoryItem:
    id: str
    content: str
    embedding: list[float]
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: datetime | None = None
    importance_score: float = 0.5
    source_event_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "tags": self.tags,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "importance_score": self.importance_score,
            "source_event_ids": self.source_event_ids,
        }


class SemanticMemory:
    def embed(self, content: str) -> list[float]:
        vector = [0.0] * VECTOR_SIZE
        for token in _tokens(content):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % VECTOR_SIZE
            vector[index] += 1.0
        norm = sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 6) for value in vector]

    def make_item(
        self,
        *,
        id: str,
        content: str,
        tags: dict[str, str] | None = None,
        timestamp: datetime | None = None,
        importance_score: float = 0.5,
        source_event_ids: list[str] | None = None,
    ) -> MemoryItem:
        return MemoryItem(
            id=id,
            content=content,
            embedding=self.embed(content),
            tags=tags or {},
            timestamp=timestamp,
            importance_score=importance_score,
            source_event_ids=source_event_ids or [],
        )

    def similarity(self, left: list[float], right: list[float]) -> float:
        return round(sum(a * b for a, b in zip(left, right, strict=False)), 6)


def _tokens(content: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", content.lower())
