from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.adaptive_recovery.events import (
    validate_chain_created,
    validate_step_started,
    validate_step_failed,
    validate_step_succeeded,
    validate_strategy_switched,
    validate_adaptive_recovery_completed,
)
from allbrain.adaptive_recovery.model import (
    ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
    RecoveryStep,
    RecoveryChain,
)


class AdaptiveRecoveryReducer:
    """Event-driven reducer for adaptive recovery.

    Reconstructs recovery chain state from events for replay compatibility.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._active_chains: dict[str, RecoveryChain] = {}
        self._completed: list[RecoveryChain] = []
        self._failed: list[RecoveryChain] = []
        self._escalated: list[RecoveryChain] = []
        self._total_created: int = 0
        self._total_completed: int = 0
        self._total_failed: int = 0
        self._total_escalated: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.RECOVERY_CHAIN_CREATED.value:
            try:
                validate_chain_created(payload)
            except ValueError:
                return
            self._total_created += 1
            chain_id = str(payload["chain_id"])
            fault_id = str(payload["fault_id"])
            fault_type = str(payload["fault_type"])
            strategies = list(payload.get("strategies", []))
            steps = tuple(
                RecoveryStep(
                    strategy=s,
                    order=i + 1,
                    confidence=0.0,
                    fault_id=fault_id,
                    chain_id=chain_id,
                )
                for i, s in enumerate(strategies)
            )
            self._active_chains[chain_id] = RecoveryChain(
                chain_id=chain_id,
                fault_id=fault_id,
                fault_type=fault_type,
                steps=steps,
                current_index=0,
            )

        elif et == EventType.RECOVERY_STEP_STARTED.value:
            try:
                validate_step_started(payload)
            except ValueError:
                return
            chain_id = str(payload["chain_id"])
            index = int(payload["step_index"])
            chain = self._active_chains.get(chain_id)
            if chain is not None:
                self._active_chains[chain_id] = RecoveryChain(
                    chain_id=chain.chain_id,
                    fault_id=chain.fault_id,
                    fault_type=chain.fault_type,
                    steps=chain.steps,
                    current_index=index,
                    created_at=chain.created_at,
                )

        elif et == EventType.RECOVERY_STEP_FAILED.value:
            try:
                validate_step_failed(payload)
            except ValueError:
                return
            # No structural change; outcome tracked via ADAPTIVE_RECOVERY_COMPLETED

        elif et == EventType.RECOVERY_STEP_SUCCEEDED.value:
            try:
                validate_step_succeeded(payload)
            except ValueError:
                return
            # No structural change; outcome tracked via ADAPTIVE_RECOVERY_COMPLETED

        elif et == EventType.RECOVERY_STRATEGY_SWITCHED.value:
            try:
                validate_strategy_switched(payload)
            except ValueError:
                return
            # Logical switch; current_index updated by next RECOVERY_STEP_STARTED

        elif et == EventType.ADAPTIVE_RECOVERY_COMPLETED.value:
            try:
                validate_adaptive_recovery_completed(payload)
            except ValueError:
                return
            chain_id = str(payload["chain_id"])
            outcome = str(payload["outcome"])
            chain = self._active_chains.pop(chain_id, None)
            if chain is not None:
                if outcome == "success":
                    self._completed.append(chain)
                    self._total_completed += 1
                elif outcome == "failed":
                    self._failed.append(chain)
                    self._total_failed += 1
                elif outcome == "escalated":
                    self._escalated.append(chain)
                    self._total_escalated += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "active_chains": list(self._active_chains.values()),
            "completed_chains": list(self._completed),
            "failed_chains": list(self._failed),
            "escalated_chains": list(self._escalated),
            "total_created": self._total_created,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "total_escalated": self._total_escalated,
            "version": ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
