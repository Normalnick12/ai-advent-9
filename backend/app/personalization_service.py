"""Day 12 coordinator around existing memory and SimpleAgent primitives."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import json
from uuid import uuid4

from app.agent import SimpleAgent
from app.agent_sessions import AgentSessionManager
from app.llm_client import ConversationMessage
from app.memory_selection import build_context
from app.personalization_models import CONFIG, FIXTURES, LONG, WORKING, QUERY, SEED
from app.personalization_observations import CapturingClient, check, output_checks
from app.profile_instructions import BASE_INSTRUCTIONS, TEMPLATE_VERSION, render_profile
from app.profile_store import ProfileStore
from app.profiles import ProfileError


@dataclass(frozen=True)
class Comparison:
    comparison_id: str
    memory_json: str
    profiles_json: str
    query: str
    config_json: str


class PersonalizationService:
    def __init__(self, memory, profiles: ProfileStore, client):
        self.memory, self.profiles, self.client = memory, profiles, client
        self.sessions = AgentSessionManager(memory.raw)
        self.busy = False
        self.comparison = None
        self.generation_calls = 0

    @contextmanager
    def claim(self):
        if self.busy:
            raise ProfileError("personalization_busy")
        self.busy = True
        try:
            yield
        finally:
            self.busy = False

    def owner(self, expected=None):
        state = self.memory.read()
        if state is None:
            raise ProfileError("not_initialized", 404)
        owner = state["memory_owner_id"]
        if expected is not None and expected != owner:
            raise ProfileError("owner_mismatch", 404)
        return owner

    def current(self):
        state = self.memory.read()
        profiles = self.profiles.list(state["memory_owner_id"]) if state else ()
        binding = self.profiles.read_binding(state["memory_owner_id"]) if state else None
        comparison = None
        if self.comparison:
            frozen_memory = json.loads(self.comparison.memory_json)
            frozen_profiles = json.loads(self.comparison.profiles_json)
            fresh = state == frozen_memory and all(any(
                p.model_dump() == record for p in profiles) for record in frozen_profiles.values())
            comparison = {"comparison_id": self.comparison.comparison_id,
                          "snapshot_id": frozen_memory["snapshot_id"], "profiles": frozen_profiles,
                          "query": self.comparison.query, "settings": json.loads(self.comparison.config_json),
                          "valid": fresh}
        return {"memory": state, "profiles": [p.model_dump() for p in profiles],
                "binding": binding.model_dump() if binding else None,
                "preview": build_context(state)[1] if state else None,
                "busy": self.busy, "comparison": comparison, "generation_calls": self.generation_calls,
                "preparation": "not_initialized" if not state else "profiles_missing" if not profiles
                else "unselected" if binding.active_profile_id is None else "ready"}

    def initialize(self):
        with self.claim():
            self.memory.initialize()
        return self.current()

    def create(self, request):
        with self.claim():
            profile = self.profiles.create(self.owner(request.owner_id), request.fields)
        return {"current": self.current(), "profile": profile.model_dump()}

    def edit(self, pid, request):
        with self.claim():
            profile = self.profiles.edit(self.owner(request.owner_id), pid, request.expected_revision, request.fields)
        return {"current": self.current(), "profile": profile.model_dump()}

    def select(self, pid, request):
        with self.claim():
            self.profiles.select(self.owner(request.owner_id), pid,
                                 request.expected_profile_revision, request.expected_binding_revision)
        return self.current()

    def mutate_memory(self, request):
        with self.claim():
            self.memory.mutate(request)
        return self.current()

    def transition(self, action, request):
        with self.claim():
            after = self.memory.transition(action, request.snapshot_id)
            self.sessions.get(after["session_id"])
        return self.current()

    def resolve(self, request):
        state = self.memory.require(request.snapshot_id)
        binding = self.profiles.read_binding(state["memory_owner_id"])
        if binding.active_profile_id is None:
            raise ProfileError("profile_unselected")
        profile = self.profiles.read(state["memory_owner_id"], binding.active_profile_id)
        if (profile.profile_id, profile.revision, binding.revision) != (
                request.profile_id, request.profile_revision, request.binding_revision):
            raise ProfileError("stale_profile_binding")
        return state, profile, binding

    def freeze(self, request):
        with self.claim():
            state, _, _ = self.resolve(request)
            h = state["short_term"]
            if state["working"] != WORKING or state["long_term"] != LONG or len(h) != 2 or h[0]["content"] != SEED:
                raise ProfileError("comparison_setup_required")
            pair = {}
            for slot in ("A", "B"):
                key = slot.lower()
                profile = self.profiles.read(state["memory_owner_id"], getattr(request, f"profile_{key}_id"))
                if profile.revision != getattr(request, f"profile_{key}_revision"):
                    raise ProfileError("stale_profile")
                if profile.behavior() != FIXTURES[slot].behavior():
                    raise ProfileError("fixture_fields_mismatch")
                pair[slot] = profile.model_dump()
            self.comparison = Comparison(str(uuid4()), json.dumps(state, ensure_ascii=False),
                json.dumps(pair, ensure_ascii=False), QUERY, json.dumps(asdict(CONFIG)))
        return self.current()

    def _count_call(self):
        self.generation_calls += 1

    async def _generate(self, state, profile, binding, query, *, mode, expected, slot=None):
        policy, selection = build_context(state)
        profile_text = render_profile(profile)
        config = replace(CONFIG, instructions=BASE_INSTRUCTIONS + "\n\n" + profile_text)
        messages = (*policy.messages, ConversationMessage("user", query))
        capture = CapturingClient(self.client, self._count_call)
        agent = SimpleAgent(capture, config, context_policy=policy)
        committed = False
        if mode == "probe":
            outcome = await agent.generate(messages)
        else:
            result = await agent.run_turn(self.sessions.get(state["session_id"]), query)
            outcome, committed = result.outcome, result.committed
        adherence, markers = output_checks(profile, outcome)
        request = capture.request
        assembly = {
            "instructions": check(request["config"]["instructions"] == config.instructions),
            "messages": check(request["messages"] == [asdict(m) for m in messages]),
            "settings": check(request["config"] == asdict(config)),
        }
        if slot:
            frozen = json.loads(self.comparison.memory_json)
            frozen_messages = (*build_context(frozen)[0].messages, ConversationMessage("user", self.comparison.query))
            settings = {k: v for k, v in request["config"].items() if k != "instructions"}
            frozen_settings = {k: v for k, v in json.loads(self.comparison.config_json).items() if k != "instructions"}
            assembly["frozen_input"] = check(request["messages"] == [asdict(m) for m in frozen_messages]
                                               and settings == frozen_settings)
        return deepcopy({"attempt_id": str(uuid4()), "mode": mode, "slot": slot,
            "comparison_id": self.comparison.comparison_id if slot else None,
            "memory": state, "profile": profile.model_dump(), "binding": binding.model_dump(),
            "selection": selection, "profile_instructions": profile_text, "template_version": TEMPLATE_VERSION,
            "request": request, "query": query, "outcome": asdict(outcome), "committed": committed,
            "selection_checks": {"owner": check(profile.owner_id == state["memory_owner_id"]),
                                 "active_profile": check(profile.profile_id == binding.active_profile_id == expected.profile_id),
                                 "profile_revision": check(profile.revision == expected.profile_revision),
                                 "binding_revision": check(binding.revision == expected.binding_revision)},
            "assembly_checks": assembly, "adherence_checks": adherence, "marker_checks": markers})

    async def send(self, request, *, seed=False):
        with self.claim():
            state, profile, binding = self.resolve(request)
            if seed and (state["short_term"] or state["working"] or state["long_term"]):
                raise ProfileError("seed_requires_empty_memory")
            observation = await self._generate(state, profile, binding, SEED if seed else request.message,
                                                mode="seed" if seed else "send", expected=request)
        return {"current": self.current(), "observation": observation}

    async def probe(self, request):
        with self.claim():
            state, profile, binding = self.resolve(request)
            if not self.comparison or request.comparison_id != self.comparison.comparison_id:
                raise ProfileError("comparison_not_found")
            pair = json.loads(self.comparison.profiles_json)
            if state != json.loads(self.comparison.memory_json) or any(
                    self.profiles.read(state["memory_owner_id"], p["profile_id"]).model_dump() != p for p in pair.values()):
                raise ProfileError("stale_comparison")
            if profile.model_dump() != pair[request.slot]:
                raise ProfileError("active_profile_mismatch")
            observation = await self._generate(state, profile, binding, self.comparison.query,
                                               mode="probe", expected=request, slot=request.slot)
        return {"current": self.current(), "observation": observation}
