"""Day 14 composition: trusted sources, explicit setup/events, and immutable receipts."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from uuid import uuid4

from app.agent_request import prepare_agent_request
from app.agent_sessions import AgentSessionManager
from app.checkout_workflow import CHECKOUT
from app.coding_candidate_adapter import CodingCandidateAdapter
from app.coding_invariants import (check_consistency, CodingConfigurationError, check_request,
    check_candidate, render_guidance, render_answer, render_refusal, rule_refs)
from app.coding_policy_store import TaskCodingPolicy, PolicyError
from app.invariants_lab_models import CONFIG, WORKING, PROFILE, POLICY, ACTIONS, InvariantsLabError
from app.llm_capture import CapturingClient
from app.memory_models import MemoryMutation
from app.memory_selection import build_context
from app.task_state import TaskStateError, resolve
from app.validated_turn import run_validated_turn, ValidatedTurnResult


class InvariantsLabService:
    def __init__(self, memory, profiles, states, policies, client):
        self.memory, self.profiles, self.states, self.policies, self.client = memory, profiles, states, policies, client
        self.sessions = AgentSessionManager(memory.raw)
        self.busy = False
        self.recovery_required = False
        self.generation_calls = 0
        self.candidate_validator = check_candidate
        self.answer_renderer = render_answer
        self.refusal_renderer = render_refusal
        self.adapter_factory = CodingCandidateAdapter

    @contextmanager
    def claim(self):
        if self.busy:
            raise InvariantsLabError("invariants_busy")
        if self.recovery_required:
            self.reconcile()
        self.busy = True
        try:
            yield
        finally:
            self.busy = False

    def reconcile(self):
        # Replace only this namespace's session cache after an uncertain write. Never replay.
        try:
            memory = self.memory.read()
            fresh = AgentSessionManager(self.memory.raw)
            if memory:
                fresh.get(memory["session_id"])
            self.sessions = fresh
            self.recovery_required = False
        except Exception:
            self.recovery_required = True
            raise InvariantsLabError("conversation_recovery_required", 500) from None

    def current(self):
        if self.recovery_required and not self.busy:
            self.reconcile()
        memory = self.memory.read()
        profile = binding = state = policy = None
        source_error = None
        if memory:
            binding = self.profiles.read_binding(memory["memory_owner_id"])
            if binding.active_profile_id:
                profile = self.profiles.read(memory["memory_owner_id"], binding.active_profile_id)
            try:
                state = self.states.read(memory["task_id"])
                policy = self.policies.read(memory["task_id"])
            except (TaskStateError, PolicyError) as exc:
                source_error = exc.code
        working_ready = bool(memory and all(k in memory["working"] for k in WORKING))
        consistent = bool(working_ready and policy and memory["working"]["current_architecture"] == policy.values.required_architecture)
        if working_ready and policy and not consistent:
            source_error = "configuration_inconsistent"
        readiness = {"memory_ready": working_ready, "profile_ready": profile is not None,
                     "state_ready": state is not None, "policy_ready": policy is not None,
                     "consistent": consistent}
        return deepcopy({"memory": memory, "profile": profile.model_dump() if profile else None,
            "binding": binding.model_dump() if binding else None,
            "task_state": CHECKOUT.view(state) if state else None,
            "policy": policy.view() if policy else None,
            "rules": [asdict(r) for r in rule_refs(policy.values, policy.source)] if policy else [],
            "readiness": readiness, "ready": all(readiness.values()) and source_error is None,
            "can_propose": all(readiness.values()) and source_error is None and state.status == "ACTIVE"
                           and state.state_id == "EXECUTION_IMPLEMENT" and not self.recovery_required,
            "source_error": source_error, "busy": self.busy, "recovery_required": self.recovery_required,
            "generation_calls": self.generation_calls})

    def initialize(self):
        with self.claim():
            memory = self.memory.initialize()
            self.states.create_initial(memory["task_id"])
        return self.current()

    def require_task(self, request):
        memory = self.memory.require(request.snapshot_id)
        if memory["task_id"] != request.task_id:
            raise InvariantsLabError("task_not_current", 404)
        return memory

    def setup(self, request):
        with self.claim():
            memory = self.require_task(request)
            if any(k in memory["working"] and memory["working"][k] != v for k, v in WORKING.items()):
                raise InvariantsLabError("working_setup_conflict")
            owner = memory["memory_owner_id"]
            binding = self.profiles.read_binding(owner)
            if binding.active_profile_id:
                active = self.profiles.read(owner, binding.active_profile_id)
                if active.behavior() != PROFILE.behavior():
                    raise InvariantsLabError("profile_setup_conflict")
            # Reads distinguish corruption from missing sources before completing partial setup.
            self.states.read(memory["task_id"])
            old_policy = self.policies.read(memory["task_id"])
            record = TaskCodingPolicy(task_id=memory["task_id"], values=POLICY)
            if old_policy is not None and old_policy != record:
                raise PolicyError("policy_immutable")
            for key, value in WORKING.items():
                if key not in memory["working"]:
                    memory = self.memory.mutate(MemoryMutation(snapshot_id=memory["snapshot_id"],
                        layer="WORKING", key=key, value=value, operation="set"))
            if not binding.active_profile_id:
                profile = next((p for p in self.profiles.list(owner) if p.behavior() == PROFILE.behavior()), None)
                if profile is None:
                    profile = self.profiles.create(owner, PROFILE)
                self.profiles.select(owner, profile.profile_id, profile.revision, binding.revision)
            self.states.create_initial(memory["task_id"])
            self.policies.create(record)
        return self.current()

    def lifecycle(self, action, request):
        with self.claim():
            self.require_task(request)
            memory = self.memory.transition(action, request.snapshot_id)
            self.sessions.get(memory["session_id"])
            if action == "new-task":
                self.states.create_initial(memory["task_id"])
        return self.current()

    def event(self, request):
        with self.claim():
            memory = self.require_task(request)
            before = self.states.read(memory["task_id"])
            if before is None:
                raise InvariantsLabError("task_state_missing")
            self.states.compare_and_set(request.state_revision, resolve(before, request.event, CHECKOUT))
        return self.current()

    def resolve_sources(self, request):
        memory = self.require_task(request)
        if request.session_id != memory["session_id"]:
            raise InvariantsLabError("session_not_current", 404)
        state = self.states.read(memory["task_id"])
        if state is None or state.revision != request.state_revision:
            raise InvariantsLabError("stale_or_missing_state")
        if state.status != "ACTIVE" or state.state_id != "EXECUTION_IMPLEMENT":
            raise InvariantsLabError("proposal_not_applicable")
        binding = self.profiles.read_binding(memory["memory_owner_id"])
        if not binding.active_profile_id:
            raise InvariantsLabError("profile_unselected")
        profile = self.profiles.read(memory["memory_owner_id"], binding.active_profile_id)
        if (profile.profile_id, profile.revision, binding.revision) != (
                request.profile_id, request.profile_revision, request.binding_revision):
            raise InvariantsLabError("stale_profile_binding")
        policy = self.policies.read(memory["task_id"])
        if policy is None:
            raise InvariantsLabError("policy_missing")
        if (policy.policy_id, policy.definition_version, policy.fingerprint) != (
                request.policy_id, request.policy_version, request.policy_snapshot_id):
            raise InvariantsLabError("stale_policy")
        if not all(k in memory["working"] for k in WORKING):
            raise InvariantsLabError("working_not_ready")
        return memory, profile, binding, state, policy

    async def propose(self, request, *, on_dispatch=None):
        with self.claim():
            memory, profile, binding, state, policy = self.resolve_sources(request)
            query, intent = ACTIONS[request.action_id]
            history_policy, selection = build_context(memory)
            section = render_guidance(policy.values, policy.source)
            adapter = prepared = None
            calls = 0

            def dispatched():
                nonlocal calls
                calls += 1
                self.generation_calls += 1
                if on_dispatch:
                    on_dispatch()

            capture = CapturingClient(self.client, dispatched)

            async def generate():
                nonlocal adapter, prepared
                prepared = prepare_agent_request(CONFIG, memory, profile, state, CHECKOUT, query,
                                                 invariant_section=section)
                adapter = self.adapter_factory(capture, prepared)
                return await adapter.generate()

            try:
                check_consistency(policy.values, memory["working"].get("current_architecture"))
            except CodingConfigurationError:
                turn = ValidatedTurnResult(error_code="configuration_inconsistent", error_stage="consistency")
            else:
                turn = await run_validated_turn(self.sessions.get(memory["session_id"]), query,
                    context_policy=history_policy, required_rules=rule_refs(policy.values, policy.source),
                    precheck=lambda: check_request(policy.values, intent, policy.source), generate=generate,
                    validate=lambda candidate: self.candidate_validator(policy.values, candidate, policy.source),
                    render=self.answer_renderer,
                    refuse=lambda result, origin: self.refusal_renderer(policy.values, policy.source, result, origin))
            if turn.commit_status == "unknown":
                self.recovery_required = True
                try:
                    self.reconcile()
                    if self.sessions.get(memory["session_id"]).history == history_policy.history:
                        turn = replace(turn, commit_status="failed")
                except InvariantsLabError:
                    pass
            actual = capture.request
            receipt = deepcopy({"attempt_id": str(uuid4()), "action_id": request.action_id,
                "query": query, "intent": intent.model_dump(), "memory": memory,
                "profile": profile.model_dump(), "binding": binding.model_dump(),
                "state": CHECKOUT.view(state), "policy": policy.view(), "selection": selection,
                "rules": [asdict(r) for r in rule_refs(policy.values, policy.source)],
                "invariant_section": section, "profile_section": prepared.profile_section if prepared else None,
                "state_section": prepared.state_section if prepared else None,
                "actual_request": actual, "provider_dispatch": "dispatched" if calls else "not_dispatched",
                "generation_calls": calls, "provider_outcome": adapter.outcome if adapter else None,
                "raw_candidate": adapter.outcome.get("reply") if adapter and adapter.outcome else None,
                "candidate": adapter.candidate.model_dump() if adapter and adapter.candidate else None,
                "candidate_preparation": adapter.preparation if adapter else "not_attempted",
                "turn": asdict(turn), "storage_checks": {"policy_read": "pass"},
                "selection_checks": {"source_references": "pass"},
                "assembly_checks": {"status": "pass" if actual and
                    actual["config"] == asdict(adapter.config) and actual["messages"] == [asdict(m) for m in prepared.messages]
                    else "not_dispatched" if not actual else "fail"},
                "model_adherence": "typed_decisions_only" if turn.validation else "unavailable"})
        try:
            current = self.current()
        except Exception:
            current = None  # Keep the actual receipt even when a recovery read is unavailable.
        return {"current": current, "observation": receipt}
