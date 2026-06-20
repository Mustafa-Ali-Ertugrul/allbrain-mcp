from __future__ import annotations

from typing import Any


class LongHorizonObjectiveSynthesizer:
    def synthesize(self, context: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
        objectives = list(context.get("long_horizon_objectives", [])) or [
            "preserve_alignment",
            "preserve_auditability",
            "bound_autonomy_growth",
        ]
        pressure = sorted(
            {
                str(proposal.get("target_layer"))
                for proposal in proposals
                if proposal.get("target_layer")
            }
        )
        return {"objectives": objectives, "pressured_layers": pressure}
