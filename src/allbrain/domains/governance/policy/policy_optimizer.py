from __future__ import annotations

from collections import Counter
from typing import Any

from allbrain.domains.memory.memory.semantic_memory import MemoryItem


class PolicyOptimizer:
    def derive_signals(self, memory_items: list[MemoryItem]) -> dict[str, Any]:
        fallback_pairs = Counter()
        failure_reasons = Counter()
        for item in memory_items:
            if item.tags.get("kind") == "fallback_pattern":
                parts = item.content.split(":")
                if len(parts) > 1 and "->" in parts[1]:
                    fallback_pairs[parts[1].strip().split(" status=")[0]] += 1
            if item.tags.get("kind") == "failure_pattern":
                failure_reasons[item.tags.get("reason", "unknown")] += 1
        return {
            "fallback_pairs": dict(fallback_pairs),
            "failure_reasons": dict(failure_reasons),
        }
