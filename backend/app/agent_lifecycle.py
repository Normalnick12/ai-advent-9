"""Application-owned lifecycle boundary using the existing resolver and CAS."""
from copy import deepcopy
from uuid import uuid4

from app.task_state import TaskStateError, resolve


class LifecycleService:
    def __init__(self, definition, store, classify, explain):
        self.definition, self.store = definition, store
        self.classify, self.explain = classify, explain
        self.reconciliation_required = False

    def apply(self, task_id, expected_revision, event):
        before = self.store.read(task_id)
        if before is None:
            raise TaskStateError("task_state_missing", 404)
        if before.revision != expected_revision:
            raise TaskStateError("stale_task_state")
        after, error, persistence = before, None, "not_attempted"
        try:
            proposed = resolve(before, event, self.definition)
        except TaskStateError as exc:
            if exc.code != "invalid_task_event":
                raise
            outcome, error = "rejected", exc.code
        else:
            try:
                after = self.store.compare_and_set(expected_revision, proposed)
            except TaskStateError as exc:
                if exc.code == "stale_task_state":
                    raise
                outcome, error, persistence, after = "technical_error", exc.code, "unknown", None
                self.reconciliation_required = True
            except Exception:
                outcome, error, persistence, after = "technical_error", "state_storage_error", "unknown", None
                self.reconciliation_required = True
            else:
                outcome, persistence = self.classify(event), "committed"
        view = self.definition.view(after) if after else None
        return deepcopy({
            "attempt_id": str(uuid4()), "operation": "lifecycle", "task_id": task_id,
            "outcome": outcome, "event": event, "error": error,
            "before": self.definition.view(before), "after": view,
            "persistence": persistence, "provider_dispatch": "not_required", "generation_calls": 0,
            "actual_request": None, "candidate": None, "conversation": "unchanged",
            "conversation_commit": "not_applicable",
            "explanation": self.explain(outcome, event, view or self.definition.view(before)),
        })
