from __future__ import annotations

from allbrain.events import EventType
from allbrain.intent.models import Intent
from allbrain.models.schemas import EventRead


class IntentExtractor:
    def extract(self, events: list[EventRead]) -> list[Intent]:
        intents: list[Intent] = []
        for event in events:
            if self._is_supporting_file_evidence(event, events):
                continue
            intent = self._extract_one(event, events)
            if intent is not None:
                intents.append(intent)
        return intents

    def _extract_one(self, event: EventRead, events: list[EventRead]) -> Intent | None:
        agent_id = event.agent_id or "unknown"
        related_files = self._related_files(event)
        if event.type == EventType.TASK_STARTED.value:
            task = self._task(event)
            supporting_files = self._supporting_files(event, events)
            return self._intent(event, agent_id, task or "task started", "task_started", self._status(event, events, "active"), self._merge_files(related_files, supporting_files), self._confidence(event, events, 0.7))
        if event.type == EventType.TASK_COMPLETED.value:
            task = self._task(event)
            return self._intent(event, agent_id, task or "task completed", "task_completed", "completed", related_files, self._confidence(event, events, 0.8))
        if event.type == EventType.TASK_BLOCKED.value:
            task = self._task(event)
            return self._intent(event, agent_id, task or "task blocked", "task_blocked", "blocked", related_files, self._confidence(event, events, 0.85))
        if event.type == EventType.FAILURE.value:
            return self._intent(event, agent_id, "debug failure", "failure", "active", related_files, self._confidence(event, events, 0.75))
        if event.type == EventType.FILE_MODIFIED.value and event.file_path:
            return self._intent(event, agent_id, "file modification", "file_modified", "active", related_files, self._confidence(event, events, 0.5))
        return None

    def _intent(
        self,
        event: EventRead,
        agent_id: str,
        goal: str,
        sub_goal: str,
        status: str,
        related_files: list[str],
        confidence: float,
    ) -> Intent:
        return Intent(
            intent_id=f"intent_{event.id}_{sub_goal}",
            agent_id=agent_id,
            goal=goal,
            sub_goal=sub_goal,
            status=status,
            related_files=related_files,
            confidence=confidence,
            source_event_id=event.id,
            created_at=event.created_at,
        )

    def _related_files(self, event: EventRead) -> list[str]:
        files: list[str] = []
        for value in [event.file_path, event.payload.get("file_path"), event.payload.get("file")]:
            if isinstance(value, str) and value and value not in files:
                files.append(value)
        return files

    def _task(self, event: EventRead) -> str | None:
        task = event.payload.get("task") or event.task_hint
        return task if isinstance(task, str) and task else None

    def _confidence(self, event: EventRead, events: list[EventRead], base_confidence: float) -> float:
        agent_id = event.agent_id or "unknown"
        task = self._task(event)
        files = set(self._related_files(event))
        file_evidence = 0
        completion_evidence = 0
        blocker_or_failure_evidence = 0
        for candidate in events:
            if (candidate.agent_id or "unknown") != agent_id:
                continue
            candidate_files = set(self._related_files(candidate))
            candidate_task = self._task(candidate)
            same_task = bool(task and candidate_task == task)
            same_file = bool(files and candidate_files & files)
            if candidate.type == EventType.FILE_MODIFIED.value and (same_task or same_file):
                file_evidence += 1
            if candidate.type == EventType.TASK_COMPLETED.value and same_task:
                completion_evidence += 1
            if candidate.type in {EventType.TASK_BLOCKED.value, EventType.FAILURE.value} and (same_task or same_file):
                blocker_or_failure_evidence += 1
        multiplier = 1.0 + min(file_evidence, 5) * 0.05 + min(completion_evidence, 2) * 0.12 + min(blocker_or_failure_evidence, 2) * 0.04
        return round(min(1.0, base_confidence * multiplier), 4)

    def _status(self, event: EventRead, events: list[EventRead], default: str) -> str:
        task = self._task(event)
        if not task:
            return default
        agent_id = event.agent_id or "unknown"
        later_events = [candidate for candidate in events if candidate.id > event.id and (candidate.agent_id or "unknown") == agent_id]
        if any(candidate.type == EventType.TASK_COMPLETED.value and self._task(candidate) == task for candidate in later_events):
            return "completed"
        if any(candidate.type == EventType.TASK_BLOCKED.value and self._task(candidate) == task for candidate in later_events):
            return "blocked"
        return default

    def _is_supporting_file_evidence(self, event: EventRead, events: list[EventRead]) -> bool:
        if event.type != EventType.FILE_MODIFIED.value:
            return False
        agent_id = event.agent_id or "unknown"
        active_task: str | None = None
        for candidate in events:
            if candidate.id > event.id:
                break
            if (candidate.agent_id or "unknown") != agent_id:
                continue
            if candidate.type == EventType.TASK_STARTED.value:
                active_task = self._task(candidate)
            elif candidate.type in {EventType.TASK_COMPLETED.value, EventType.TASK_BLOCKED.value} and self._task(candidate) == active_task:
                active_task = None
        return active_task is not None

    def _supporting_files(self, event: EventRead, events: list[EventRead]) -> list[str]:
        agent_id = event.agent_id or "unknown"
        files: list[str] = []
        for candidate in events:
            if candidate.id <= event.id:
                continue
            if (candidate.agent_id or "unknown") != agent_id:
                continue
            if candidate.type in {EventType.TASK_COMPLETED.value, EventType.TASK_BLOCKED.value} and self._task(candidate) == self._task(event):
                break
            if candidate.type == EventType.FILE_MODIFIED.value:
                files = self._merge_files(files, self._related_files(candidate))
        return files

    def _merge_files(self, left: list[str], right: list[str]) -> list[str]:
        merged = list(left)
        for file_path in right:
            if file_path not in merged:
                merged.append(file_path)
        return merged
