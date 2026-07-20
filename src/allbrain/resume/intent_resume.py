from __future__ import annotations

from allbrain.domains.analysis.contradiction import ContradictionDetector
from allbrain.domains.reasoning.intent import IntentExtractor, IntentStore
from allbrain.models.schemas import EventRead
from allbrain.resume.multi_agent import MultiAgentResumeEngine


class IntentResumeEngine:
    def __init__(
        self,
        multi_agent_engine: MultiAgentResumeEngine,
        extractor: IntentExtractor | None = None,
        store: IntentStore | None = None,
        detector: ContradictionDetector | None = None,
    ):
        self.multi_agent_engine = multi_agent_engine
        self.extractor = extractor or IntentExtractor()
        self.store = store or IntentStore()
        self.detector = detector or ContradictionDetector()

    def resume(
        self,
        *,
        events: list[EventRead],
        project_path: str,
        project_id: int,
        limit: int,
        include_git: bool,
        use_snapshot: bool,
    ) -> dict:
        global_state = self.multi_agent_engine.resume(
            project_path=project_path,
            project_id=project_id,
            events=events,
            limit=limit,
            include_git=include_git,
            use_snapshot=use_snapshot,
        )
        intents = self.extractor.extract(events)
        graph = self.store.build_graph(intents, events)
        contradictions = self.detector.detect(intents)
        return {
            "global_state": global_state,
            "intent_view": {
                "intents": [intent.model_dump(mode="json") for intent in intents],
                "active_intents": len(intents),
                "unique_agents": sorted({intent.agent_id for intent in intents}),
            },
            "intent_graph": graph.to_dict(),
            "contradiction_view": {
                "contradictions": contradictions,
                "count": len(contradictions),
            },
            "decision_view": self._decision_view(contradictions, intents),
        }

    def _decision_view(self, contradictions, intents) -> dict:
        if contradictions:
            first = contradictions[0]
            target = first["related_files"][0] if first["related_files"] else first["a_goal"]
            return {
                "next_step": f"resolve contradiction in {target}",
                "required_action": "resolve_contradiction",
                "confidence": 0.65,
            }
        if intents:
            return {
                "next_step": f"continue intent: {intents[-1].goal}",
                "required_action": "continue_intent",
                "confidence": intents[-1].confidence,
            }
        return {
            "next_step": "no active intent",
            "required_action": "idle",
            "confidence": 1.0,
        }
