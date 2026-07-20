from __future__ import annotations

from allbrain.domains.reasoning.intent.graph import IntentGraph
from allbrain.domains.reasoning.intent.models import Intent
from allbrain.models.schemas import EventRead


class IntentStore:
    def build_graph(self, intents: list[Intent], events: list[EventRead] | None = None) -> IntentGraph:
        graph = IntentGraph()
        file_map: dict[str, str] = {}
        task_map: dict[str, str] = {}
        source_to_intent = {intent.source_event_id: intent.intent_id for intent in intents}

        for intent in intents:
            graph.add_intent(intent)
            for file_path in intent.related_files:
                if file_path in file_map:
                    graph.link(file_map[file_path], intent.intent_id, "same_file")
                file_map[file_path] = intent.intent_id
            if intent.goal in task_map:
                graph.link(task_map[intent.goal], intent.intent_id, "same_task")
            task_map[intent.goal] = intent.intent_id

        for event in events or []:
            if event.caused_by and event.caused_by in source_to_intent and event.id in source_to_intent:
                graph.link(source_to_intent[event.caused_by], source_to_intent[event.id], "caused_by")

        return graph

