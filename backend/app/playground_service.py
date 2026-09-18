"""Concrete Coding Playground composition. Model output never applies lifecycle events."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from uuid import uuid4

from app.agent_integration import SendCoordinator
from app.agent_lifecycle import LifecycleService
from app.agent_request import prepare_agent_request
from app.coding_invariants import check_candidate, check_consistency, render_guidance, render_refusal, rule_refs
from app.coding_policy_store import TaskCodingPolicy
from app.memory_models import MemoryMutation
from app.memory_selection import build_context
from app.playground_coding import (CONFIG, TASK_TITLE, PROFILE_PRESETS, BOUNDED_COVERAGE,
    ConversationCandidateAdapter, render_turn)
from app.playground_models import PlaygroundError
from app.playground_setup_store import SetupRecord
from app.playground_workflow import (CHECKOUT_V2, EVENT_LABELS, NODE_LABELS, NEXT_ACTIONS,
    RECOVERY_EXPLANATIONS, EDUCATIONAL_EVENTS, transition_kind)


def explain_event(outcome, event, state):
    if outcome == "recovery_applied":
        return RECOVERY_EXPLANATIONS[event]
    if outcome == "rejected":
        return "Переход отклонён. " + NEXT_ACTIONS[state["state_id"]]
    if outcome == "technical_error":
        return "Результат записи неизвестен. Прочитайте текущее состояние."
    if outcome == "pause_applied":
        return "Задача приостановлена. Можно обсудить уточнения; затем возобновите задачу."
    if outcome == "resume_applied":
        return "Задача возобновлена. " + NEXT_ACTIONS[state["state_id"]]
    return "Переход применён. " + NEXT_ACTIONS[state["state_id"]]


class PlaygroundService:
    def __init__(self, memory, profiles, states, policies, setups, client):
        self.memory, self.profiles, self.states, self.policies, self.setups = memory, profiles, states, policies, setups
        self.send_coordinator = SendCoordinator(memory.raw, client)
        self.lifecycle = LifecycleService(CHECKOUT_V2, states, transition_kind, explain_event)
        self.busy = False
        self.generation_calls = 0
        self.adapter_factory = ConversationCandidateAdapter
        self.candidate_validator = check_candidate
        self.answer_renderer = render_turn
        self.refusal_renderer = render_refusal

    @contextmanager
    def claim(self, *, setup=False):
        if self.busy:
            raise PlaygroundError("playground_busy")
        if self.send_coordinator.reconciliation_required or self.lifecycle.reconciliation_required:
            raise PlaygroundError("reconciliation_required")
        if not setup and self.setups.pending():
            raise PlaygroundError("setup_pending")
        self.busy = True
        try:
            yield
        finally:
            self.busy = False

    def current(self):
        memory = self.memory.read()
        pending = self.setups.pending()
        setup = pending or (self.setups.read(memory["task_id"]) if memory else None)
        state = policy = profile = binding = None
        source_error = None
        if memory:
            try:
                state = self.states.read(memory["task_id"])
                policy = self.policies.read(memory["task_id"])
                binding = self.profiles.read_binding(memory["memory_owner_id"])
                if binding.active_profile_id:
                    profile = self.profiles.read(memory["memory_owner_id"], binding.active_profile_id)
                if setup and not pending and (setup.machine_id != (state.machine_id if state else None)
                        or setup.owner_id != memory["memory_owner_id"]):
                    source_error = "setup_state_incompatible"
                if policy and memory["working"].get("current_architecture") != policy.values.required_architecture:
                    source_error = "configuration_inconsistent"
                if policy and setup and not pending and policy.values != setup.configuration.policy:
                    source_error = "configuration_inconsistent"
                if not self.busy:
                    if self.send_coordinator.reconciliation_required:
                        self.send_coordinator.reconcile(memory["session_id"])
                    self.lifecycle.reconciliation_required = False
            except Exception as exc:
                source_error = getattr(exc, "code", "source_read_failed")
        readiness = {
            "memory_ready": bool(memory and memory["working"].get("task") and memory["working"].get("current_architecture")),
            "profile_ready": profile is not None, "state_ready": state is not None,
            "policy_ready": policy is not None, "setup_ready": bool(setup and setup.status == "ready"),
        }
        if pending:
            target_memory = bool(memory and memory["task_id"] == pending.task_id
                                 and memory["session_id"] == pending.session_id)
            readiness["memory_ready"] = bool(target_memory and
                memory["working"].get("task") == TASK_TITLE and
                memory["working"].get("current_architecture") == pending.configuration.policy.required_architecture)
            readiness["profile_ready"] = bool(profile and all(getattr(profile, k) == getattr(pending.profile_fields, k)
                for k in type(pending.profile_fields).model_fields))
            try:
                readiness["state_ready"] = self.states.read(pending.task_id) == CHECKOUT_V2.initial(pending.task_id)
                target_policy = self.policies.read(pending.task_id)
                readiness["policy_ready"] = bool(target_policy and target_policy.values == pending.configuration.policy)
            except Exception as exc:
                source_error = getattr(exc, "code", "source_read_failed")
        ready = all(readiness.values()) and not source_error and not pending
        ref = None
        if ready:
            ref = {"task_id": memory["task_id"], "session_id": memory["session_id"],
                "snapshot_id": memory["snapshot_id"], "state_revision": state.revision,
                "profile_id": profile.profile_id, "profile_revision": profile.revision,
                "binding_revision": binding.revision, "policy_id": policy.policy_id,
                "policy_version": policy.definition_version, "policy_snapshot_id": policy.fingerprint}
        view = CHECKOUT_V2.view(state) if state else None
        return deepcopy({
            "memory": memory, "profile": profile.model_dump() if profile else None,
            "binding": binding.model_dump() if binding else None, "task_state": view,
            "policy": policy.view() if policy else None, "setup": setup.model_dump() if setup else None,
            "source_error": source_error, "readiness": readiness, "ready": ready, "reference": ref,
            "can_send": bool(ready and not CHECKOUT_V2.validate_state(state).is_terminal),
            "busy": self.busy, "reconciliation_required": self.send_coordinator.reconciliation_required or self.lifecycle.reconciliation_required,
            "generation_calls": self.generation_calls,
            "stage_label": NODE_LABELS.get(state.state_id) if state else None,
            "next_action": ("Возобновите задачу; Send позволяет только обсудить уточнения." if state.status == "PAUSED"
                else NEXT_ACTIONS[state.state_id]) if state else "Подготовьте новую задачу.",
            "actions": [{"event": e, "label": EVENT_LABELS[e]} for e in CHECKOUT_V2.allowed_events(state)] if ready else [],
            "educational_event": EDUCATIONAL_EVENTS.get(state.state_id) if ready and state.status == "ACTIVE" else None,
        })

    def require_task(self, ref):
        memory = self.memory.require(ref.snapshot_id)
        if (ref.task_id, ref.session_id) != (memory["task_id"], memory["session_id"]):
            raise PlaygroundError("task_session_not_current")
        return memory

    def resolve_sources(self, ref):
        memory = self.require_task(ref)
        state = self.states.read(ref.task_id)
        if state is None:
            raise PlaygroundError("task_state_missing")
        if state.revision != ref.state_revision:
            raise PlaygroundError("stale_task_state")
        CHECKOUT_V2.validate_state(state)
        binding = self.profiles.read_binding(memory["memory_owner_id"])
        if not binding.active_profile_id:
            raise PlaygroundError("profile_unselected")
        profile = self.profiles.read(memory["memory_owner_id"], binding.active_profile_id)
        if (profile.profile_id, profile.revision, binding.revision) != (
                ref.profile_id, ref.profile_revision, ref.binding_revision):
            raise PlaygroundError("stale_profile_binding")
        policy = self.policies.read(ref.task_id)
        if policy is None:
            raise PlaygroundError("policy_missing")
        if (policy.policy_id, policy.definition_version, policy.fingerprint) != (
                ref.policy_id, ref.policy_version, ref.policy_snapshot_id):
            raise PlaygroundError("stale_policy")
        setup = self.setups.read(ref.task_id)
        if setup is None or setup.status != "ready" or setup.machine_id != state.machine_id:
            raise PlaygroundError("setup_not_ready")
        if setup.configuration.policy != policy.values or not memory["working"].get("task"):
            raise PlaygroundError("configuration_inconsistent")
        try:
            check_consistency(policy.values, memory["working"].get("current_architecture"))
        except Exception:
            raise PlaygroundError("configuration_inconsistent") from None
        return memory, profile, binding, state, policy

    def create_task(self, request):
        with self.claim(setup=True):
            if self.setups.pending():
                raise PlaygroundError("setup_pending")
            memory = self.memory.read()
            if memory is not None:
                if request.current is None:
                    raise PlaygroundError("current_reference_required")
                self.resolve_sources(request.current)
            elif request.current is not None:
                raise PlaygroundError("stale_snapshot")
            owner_id = memory["memory_owner_id"] if memory else str(uuid4())
            record = SetupRecord(configuration=request.configuration,
                profile_fields=PROFILE_PRESETS[request.configuration.profile_preset],
                owner_id=owner_id, task_id=str(uuid4()), session_id=str(uuid4()),
                previous_snapshot=memory["snapshot_id"] if memory else None,
                previous_profile_binding=self.profiles.read_binding(owner_id))
            self.setups.create(record)
            self._complete(record)
        return self.current()

    def complete_setup(self, request):
        with self.claim(setup=True):
            record = self.setups.read(request.task_id)
            if record is None:
                raise PlaygroundError("setup_missing", 404)
            if record.status == "pending":
                self._complete(record)
        return self.current()

    def _preset(self, owner_id, fields):
        exact = [p for p in self.profiles.list(owner_id)
                 if all(getattr(p, key) == getattr(fields, key) for key in type(fields).model_fields)]
        if len(exact) > 1:
            raise PlaygroundError("profile_setup_conflict")
        return exact[0] if exact else self.profiles.create(owner_id, fields)

    def _complete(self, record):
        memory = self.memory.create_reserved(owner_id=record.owner_id, task_id=record.task_id,
            session_id=record.session_id, expected_snapshot=record.previous_snapshot)
        expected_working = {"task": TASK_TITLE, "current_architecture": record.configuration.policy.required_architecture}
        if memory["short_term"] or any(k not in expected_working or expected_working[k] != v
                                      for k, v in memory["working"].items()):
            raise PlaygroundError("working_setup_conflict")
        state = self.states.read(record.task_id)
        if state is not None and state != CHECKOUT_V2.initial(record.task_id):
            raise PlaygroundError("state_setup_conflict")
        policy_record = TaskCodingPolicy(task_id=record.task_id, values=record.configuration.policy)
        old_policy = self.policies.read(record.task_id)
        if old_policy is not None and old_policy != policy_record:
            raise PlaygroundError("policy_setup_conflict")
        for key, value in expected_working.items():
            if key not in memory["working"]:
                memory = self.memory.mutate(MemoryMutation(snapshot_id=memory["snapshot_id"],
                    layer="WORKING", key=key, value=value, operation="set"))
        for preset, fields in PROFILE_PRESETS.items():
            self._preset(record.owner_id, record.profile_fields if preset == record.configuration.profile_preset else fields)
        profile = self._preset(record.owner_id, record.profile_fields)
        binding = self.profiles.read_binding(record.owner_id)
        previous = record.previous_profile_binding
        if binding != previous:
            expected_revision = previous.revision + (previous.active_profile_id != profile.profile_id)
            if binding.active_profile_id != profile.profile_id or binding.revision != expected_revision:
                raise PlaygroundError("profile_setup_conflict")
        self.profiles.select(record.owner_id, profile.profile_id, profile.revision, binding.revision)
        self.states.create_initial(record.task_id)
        self.policies.create(policy_record)
        self.setups.ready(record)

    def select_profile(self, request):
        with self.claim():
            memory, _, binding, _, _ = self.resolve_sources(request)
            fields = PROFILE_PRESETS[request.profile_preset]
            matches = [p for p in self.profiles.list(memory["memory_owner_id"])
                       if all(getattr(p, k) == getattr(fields, k) for k in type(fields).model_fields)]
            if len(matches) != 1:
                raise PlaygroundError("profile_preset_unavailable")
            profile = matches[0]
            self.profiles.select(memory["memory_owner_id"], profile.profile_id, profile.revision, binding.revision)
        return self.current()

    def new_conversation(self, request):
        with self.claim():
            self.resolve_sources(request)
            self.memory.transition("new-conversation", request.snapshot_id)
        return self.current()

    def event(self, request):
        with self.claim():
            self.require_task(request)
            setup = self.setups.read(request.task_id)
            if setup is None or setup.status != "ready":
                raise PlaygroundError("setup_not_ready")
            receipt = self.lifecycle.apply(request.task_id, request.state_revision, request.event)
        return {"current": self._safe_current(), "receipt": receipt}

    def _safe_current(self):
        try:
            return self.current()
        except Exception:
            return None

    async def send(self, request, *, on_dispatch=None):
        with self.claim():
            memory, profile, binding, state, policy = self.resolve_sources(request)
            if CHECKOUT_V2.validate_state(state).is_terminal:
                raise PlaygroundError("task_completed")
            history, selection = build_context(memory)
            rules = rule_refs(policy.values, policy.source)
            section = render_guidance(policy.values, policy.source)

            def dispatched():
                self.generation_calls += 1
                if on_dispatch:
                    on_dispatch()

            receipt = await self.send_coordinator.send(
                session_id=request.session_id, query=request.query, history_policy=history,
                prepare=lambda: prepare_agent_request(CONFIG, memory, profile, state, CHECKOUT_V2,
                    request.query, invariant_section=section),
                adapter_factory=self.adapter_factory, required_rules=rules,
                validate=lambda candidate: self.candidate_validator(policy.values, candidate.decisions, policy.source),
                render=self.answer_renderer,
                refuse=lambda checked, origin: self.refusal_renderer(policy.values, policy.source, checked, origin),
                sources={"memory": memory, "profile": profile.model_dump(), "binding": binding.model_dump(),
                    "state": CHECKOUT_V2.view(state), "policy": policy.view(), "selection": selection,
                    "rules": [asdict(r) for r in rules]},
                coverage=BOUNDED_COVERAGE, on_dispatch=dispatched)
        return {"current": self._safe_current(), "receipt": receipt}
