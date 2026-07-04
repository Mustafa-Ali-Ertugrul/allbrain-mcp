from __future__ import annotations

from typing import TYPE_CHECKING, Any

from allbrain.adaptive_recovery.model import (
    CHAIN_OUTCOME_ESCALATED,
    CHAIN_OUTCOME_FAILED,
    CHAIN_OUTCOME_SUCCESS,
    DEFAULT_MAX_CHAIN_LENGTH,
)
from allbrain.adaptive_recovery.strategy_chain import StrategyChain
from allbrain.adaptive_recovery.switch_policy import LinearSwitchPolicy
from allbrain.events.schemas import EventType

if TYPE_CHECKING:
    pass


class AdaptiveRecoveryManager:
    """Orchestrates adaptive recovery chains.

    Builds ordered chains from consensus candidates, runs steps
    sequentially via attempt_outcomes (for test/simulation), and
    produces deterministic events.
    """

    def __init__(
        self,
        memory: Any = None,
        max_chain_length: int = DEFAULT_MAX_CHAIN_LENGTH,
    ) -> None:
        self._chain_builder = StrategyChain(max_chain_length=max_chain_length)
        self._switch_policy = LinearSwitchPolicy()
        self._memory = memory

    def run_chain(
        self,
        *,
        fault_id: str,
        fault_type: str,
        candidates: list[Any],
        attempt_outcomes: list[bool] | None = None,
    ) -> dict[str, Any]:
        """Run one adaptive recovery chain.

        Builds the chain from candidates, then simulates step execution
        when attempt_outcomes is provided.

        Args:
            fault_id: The fault identifier.
            fault_type: The fault type string.
            candidates: List of CandidateStrategy objects.
            attempt_outcomes: Optional list of bools [success, failure, ...].
                When None, chain is created but no steps are simulated.

        Returns:
            Dict with:
              - chain_id: str
              - fault_id: str
              - fault_type: str
              - steps: list of step dicts
              - outcome: str (success/failed/escalated) or "" if no outcomes
              - steps_taken: int (0 if no outcomes)
              - events: list of emitted event payloads
        """
        chain = self._chain_builder.build(
            candidates,
            fault_id=fault_id,
            fault_type=fault_type,
            memory=self._memory,
        )

        events: list[dict[str, str]] = []
        outcome = ""
        steps_taken = 0

        # Emit chain created
        events.append(
            {
                "event_type": EventType.RECOVERY_CHAIN_CREATED.value,
                "chain_id": chain.chain_id,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "steps_count": len(chain.steps),
                "strategies": [s.strategy for s in chain.steps],
            }
        )

        if not chain.steps:
            outcome = CHAIN_OUTCOME_FAILED
            steps_taken = 0
            events.append(
                {
                    "event_type": EventType.ADAPTIVE_RECOVERY_COMPLETED.value,
                    "chain_id": chain.chain_id,
                    "fault_id": fault_id,
                    "outcome": outcome,
                    "steps_taken": 0,
                }
            )
            return {
                "chain_id": chain.chain_id,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "steps": [],
                "outcome": outcome,
                "steps_taken": 0,
                "events": events,
            }

        if attempt_outcomes is None:
            return {
                "chain_id": chain.chain_id,
                "fault_id": fault_id,
                "fault_type": fault_type,
                "steps": [{"strategy": s.strategy, "order": s.order, "confidence": s.confidence} for s in chain.steps],
                "outcome": "",
                "steps_taken": 0,
                "events": events,
            }

        # Simulate step execution
        for idx, success in enumerate(attempt_outcomes):
            if idx >= len(chain.steps):
                break

            step = chain.steps[idx]
            steps_taken = idx + 1

            # Emit step started
            events.append(
                {
                    "event_type": EventType.RECOVERY_STEP_STARTED.value,
                    "chain_id": chain.chain_id,
                    "fault_id": fault_id,
                    "strategy": step.strategy,
                    "order": step.order,
                    "step_index": idx,
                }
            )

            if success:
                outcome = CHAIN_OUTCOME_SUCCESS
                events.append(
                    {
                        "event_type": EventType.RECOVERY_STEP_SUCCEEDED.value,
                        "chain_id": chain.chain_id,
                        "fault_id": fault_id,
                        "strategy": step.strategy,
                        "order": step.order,
                        "confidence": step.confidence,
                    }
                )
                break
            else:
                events.append(
                    {
                        "event_type": EventType.RECOVERY_STEP_FAILED.value,
                        "chain_id": chain.chain_id,
                        "fault_id": fault_id,
                        "strategy": step.strategy,
                        "order": step.order,
                        "reason": "step_failed",
                    }
                )

                # Try next step via switch policy
                next_idx = self._switch_policy.next_step(chain, idx)
                if next_idx is not None and next_idx < len(chain.steps):
                    next_step = chain.steps[next_idx]
                    events.append(
                        {
                            "event_type": EventType.RECOVERY_STRATEGY_SWITCHED.value,
                            "chain_id": chain.chain_id,
                            "fault_id": fault_id,
                            "from_strategy": step.strategy,
                            "to_strategy": next_step.strategy,
                            "reason": "step_failed_switching",
                        }
                    )
                else:
                    # Chain exhausted, escalate
                    outcome = CHAIN_OUTCOME_ESCALATED
                    break

        # Set final outcome if not set yet
        if not outcome:
            outcome = CHAIN_OUTCOME_ESCALATED

        events.append(
            {
                "event_type": EventType.ADAPTIVE_RECOVERY_COMPLETED.value,
                "chain_id": chain.chain_id,
                "fault_id": fault_id,
                "outcome": outcome,
                "steps_taken": steps_taken,
            }
        )

        return {
            "chain_id": chain.chain_id,
            "fault_id": fault_id,
            "fault_type": fault_type,
            "steps": [{"strategy": s.strategy, "order": s.order, "confidence": s.confidence} for s in chain.steps],
            "outcome": outcome,
            "steps_taken": steps_taken,
            "events": events,
        }
