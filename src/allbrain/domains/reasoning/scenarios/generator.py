from __future__ import annotations

from dataclasses import dataclass, field

from allbrain.domains.reasoning.scenarios.models import SCENARIO_TEMPLATE_VERSION


@dataclass(frozen=True)
class ScenarioTemplate:
    name: str
    environment_state_overlay: dict[str, str] = field(default_factory=dict)
    environment_state_remove: list[str] = field(default_factory=list)
    resources_overlay: dict[str, bool] = field(default_factory=dict)
    resources_remove: list[str] = field(default_factory=list)
    confidence: float = 0.25
    description: str = ""
    template_version: int = SCENARIO_TEMPLATE_VERSION


DEFAULT_TEMPLATES: dict[str, ScenarioTemplate] = {
    "best_case": ScenarioTemplate(
        name="best_case",
        environment_state_overlay={"tests": "passed", "deployment": "ready"},
        resources_overlay={"internet": True, "disk_available": True},
        confidence=0.25,
        description="All conditions favorable",
    ),
    "expected_case": ScenarioTemplate(
        name="expected_case",
        environment_state_overlay={},
        resources_overlay={},
        confidence=0.50,
        description="Baseline trajectory",
    ),
    "worst_case": ScenarioTemplate(
        name="worst_case",
        environment_state_remove=["tests"],
        resources_overlay={"internet": False, "disk_available": False},
        confidence=0.15,
        description="Adverse conditions",
    ),
    "safest_case": ScenarioTemplate(
        name="safest_case",
        environment_state_overlay={"tests": "passed", "deployment": "verified"},
        resources_overlay={"internet": True, "disk_available": True},
        confidence=0.10,
        description="Maximum safety",
    ),
}


class ScenarioGenerator:
    def defaults(self) -> list[ScenarioTemplate]:
        return [DEFAULT_TEMPLATES[name] for name in ("best_case", "expected_case", "worst_case", "safest_case")]

    def from_specs(self, specs: list[dict]) -> list[ScenarioTemplate]:
        templates: list[ScenarioTemplate] = []
        for spec in specs:
            templates.append(
                ScenarioTemplate(
                    name=str(spec.get("name") or f"custom_{len(templates)}"),
                    environment_state_overlay=dict(spec.get("environment_state_overlay") or {}),
                    environment_state_remove=list(spec.get("environment_state_remove") or []),
                    resources_overlay=dict(spec.get("resources_overlay") or {}),
                    resources_remove=list(spec.get("resources_remove") or []),
                    confidence=float(spec.get("confidence", 0.25)),
                    description=str(spec.get("description", "")),
                    template_version=int(spec.get("template_version", SCENARIO_TEMPLATE_VERSION)),
                )
            )
        return templates

