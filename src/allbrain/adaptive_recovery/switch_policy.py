from __future__ import annotations

from typing import Any

from allbrain.adaptive_recovery.model import RecoveryChain


class LinearSwitchPolicy:
    """Default switch policy: move to the next step in the chain.

    Returns the next step index if available, or None to signal escalation.
    """

    def next_step(self, chain: RecoveryChain, current_index: int) -> int | None:
        """Determine the next step index after a failed step.

        Args:
            chain: The recovery chain being executed.
            current_index: The index that just failed.

        Returns:
            The next step index, or None if the chain is exhausted (escalate).
        """
        next_idx = current_index + 1
        if next_idx < len(chain.steps):
            return next_idx
        return None
