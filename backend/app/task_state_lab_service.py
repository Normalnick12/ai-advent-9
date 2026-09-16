"""Day 13 coordinator: explicit events and ordinary conversation are separate operations."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from uuid import uuid4

from app.agent import SimpleAgent
from app.agent_request import prepare_agent_request
from app.agent_sessions import AgentSessionManager
from app.checkout_workflow import CHECKOUT
from app.llm_capture import CapturingClient
from app.memory_selection import build_context
from app.profile_store import ProfileStore
from app.profile_instructions import TEMPLATE_VERSION as PROFILE_TEMPLATE
from app.profiles import ProfileError
from app.task_state import TaskStateError, resolve
from app.task_state_store import TaskStateStore
from app.task_state_renderer import TEMPLATE_VERSION as STATE_TEMPLATE
from app.task_state_lab_models import CONFIG, QUERY


def check(correct, detail=""):
    return {"status": "pass" if correct else "fail", "correct": correct, "detail": detail}


class TaskStateLabService:
    def __init__(self, memory, profiles: ProfileStore, states: TaskStateStore, client):
        self.memory, self.profiles, self.states, self.client = memory, profiles, states, client
        self.sessions = AgentSessionManager(memory.raw)
        self.busy = False
        self.generation_calls = 0
        self._last_transition = None

    @contextmanager
    def claim(self):
        if self.busy:
            raise TaskStateError("task_state_busy")
        self.busy = True
        try:
            yield
        finally:
            self.busy = False

    def owner(self, expected=None):
        memory = self.memory.read()
        if memory is None:
            raise TaskStateError("not_initialized", 404)
        owner = memory["memory_owner_id"]
        if expected is not None and expected != owner:
            raise TaskStateError("owner_mismatch", 404)
        return owner

    def current(self):
        memory = self.memory.read()
        profiles = self.profiles.list(memory["memory_owner_id"]) if memory else ()
        binding = self.profiles.read_binding(memory["memory_owner_id"]) if memory else None
        state, state_error = None, None
        if memory:
            try:
                state = self.states.read(memory["task_id"])
                if state is not None:
                    CHECKOUT.validate_state(state)
            except TaskStateError as exc:
                state_error = exc.code
        readiness = {"memory_ready": memory is not None,
                     "profile_ready": bool(binding and binding.active_profile_id),
                     "task_state_ready": state is not None and state_error is None}
        return deepcopy({"memory": memory, "profiles": [p.model_dump() for p in profiles],
            "binding": binding.model_dump() if binding else None,
            "task_state": CHECKOUT.view(state) if state is not None and state_error is None else None,
            "state_error": state_error, "readiness": readiness, "ready": all(readiness.values()),
            "busy": self.busy, "generation_calls": self.generation_calls,
            "preview": build_context(memory)[1] if memory else None,
            "last_transition": self._last_transition})

    def initialize(self):
        with self.claim():
            memory = self.memory.initialize()
            self.states.create_initial(memory["task_id"])
        return self.current()

    def require_task(self, request):
        memory = self.memory.require(request.snapshot_id)
        if memory["task_id"] != request.task_id:
            raise TaskStateError("task_not_current", 404)
        return memory

    def initialize_state(self, request):
        with self.claim():
            memory = self.require_task(request)
            if request.machine_id != CHECKOUT.machine_id:
                raise TaskStateError("machine_version_incompatible")
            self.states.create_initial(memory["task_id"])
        return self.current()

    def create_profile(self, request):
        with self.claim():
            profile = self.profiles.create(self.owner(request.owner_id), request.fields)
        return {"current": self.current(), "profile": profile.model_dump()}

    def edit_profile(self, pid, request):
        with self.claim():
            profile = self.profiles.edit(self.owner(request.owner_id), pid, request.expected_revision, request.fields)
        return {"current": self.current(), "profile": profile.model_dump()}

    def select_profile(self, pid, request):
        with self.claim():
            self.profiles.select(self.owner(request.owner_id), pid,
                request.expected_profile_revision, request.expected_binding_revision)
        return self.current()

    def mutate_memory(self, request):
        with self.claim():
            self.memory.mutate(request)
        return self.current()

    def lifecycle(self, action, request):
        with self.claim():
            memory = self.memory.transition(action, request.snapshot_id)
            self.sessions.get(memory["session_id"])
            if action == "new-task":
                self.states.create_initial(memory["task_id"])
        return self.current()

    def resolve_sources(self, request, *, profile_refs=False):
        memory = self.require_task(request)
        state = self.states.read(memory["task_id"])
        if state is None:
            raise TaskStateError("task_state_missing")
        CHECKOUT.validate_state(state)
        if state.revision != request.state_revision:
            raise TaskStateError("stale_task_state")
        binding = self.profiles.read_binding(memory["memory_owner_id"])
        if binding.active_profile_id is None:
            raise TaskStateError("profile_unselected")
        profile = self.profiles.read(memory["memory_owner_id"], binding.active_profile_id)
        if profile_refs and (profile.profile_id, profile.revision, binding.revision) != (
                request.profile_id, request.profile_revision, request.binding_revision):
            raise ProfileError("stale_profile_binding")
        return memory, profile, binding, state

    def apply_event(self, request):
        with self.claim():
            _, _, _, before = self.resolve_sources(request)
            after = self.states.compare_and_set(request.state_revision, resolve(before, request.event, CHECKOUT))
            self._last_transition = {"task_id": before.task_id, "event": request.event,
                "before": before.model_dump(), "after": after.model_dump()}
        return self.current()

    async def send(self, request, *, probe=False, on_dispatch=None):
        with self.claim():
            memory, profile, binding, state = self.resolve_sources(request, profile_refs=True)
            query = QUERY if probe else request.message
            prepared = prepare_agent_request(CONFIG, memory, profile, state, CHECKOUT, query)

            def dispatched():
                self.generation_calls += 1
                if on_dispatch is not None:
                    on_dispatch()

            capture = CapturingClient(self.client, dispatched)
            agent = SimpleAgent(capture, prepared.config, context_policy=prepared.policy)
            committed = False
            if probe:
                outcome = await agent.generate(prepared.messages)
            else:
                result = await agent.run_turn(self.sessions.get(memory["session_id"]), query)
                outcome, committed = result.outcome, result.committed
            actual = capture.request
            observation = deepcopy({"attempt_id": str(uuid4()), "mode": "probe" if probe else "send",
                "memory": memory, "profile": profile.model_dump(), "binding": binding.model_dump(),
                "stored_state": state.model_dump(), "selected_state": CHECKOUT.view(state),
                "selection": build_context(memory)[1], "profile_section": prepared.profile_section,
                "state_section": prepared.state_section,
                "profile_template": PROFILE_TEMPLATE, "state_template": STATE_TEMPLATE,
                "request": actual, "query": query, "outcome": asdict(outcome),
                "conversation_committed": committed,
                "storage_checks": {"current_state_read": check(self.states.read(state.task_id) == state,
                    "Current persisted snapshot; not a reopen test.")},
                "selection_checks": {"task": check(state.task_id == memory["task_id"] == request.task_id),
                    "state_revision": check(state.revision == request.state_revision),
                    "profile": check(profile.profile_id == binding.active_profile_id == request.profile_id)},
                "assembly_checks": {"instructions": check(actual["config"]["instructions"] == prepared.config.instructions),
                    "messages": check(actual["messages"] == [asdict(m) for m in prepared.messages]),
                    "settings": check(actual["config"] == asdict(prepared.config))},
                "model_adherence": {"status": "human_observation" if outcome.status == "completed" else "unavailable",
                    "detail": "Оцените соответствие этапу/паузе отдельно; ответ не применяет event."}})
        return {"current": self.current(), "observation": observation}
