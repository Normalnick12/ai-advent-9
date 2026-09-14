"""Day 11 orchestration around the shared SimpleAgent generation lifecycle."""
from contextlib import contextmanager
from dataclasses import asdict
from uuid import uuid4
from app.agent import SimpleAgent
from app.agent_sessions import AgentSessionManager
from app.llm_client import ConversationMessage
from app.memory_models import DAY11_CONFIG, VERIFY_CONFIG, FIELDS, MemoryError, VerificationOutput
from app.memory_context import build_context, availability, applicable_stages, EXPECTED, QUERY, SEED
from app.memory_store import strict_json
from app.openai_agent_payload import generation_payload


class MemoryExperimentService:
    def __init__(self, store, client):
        self.store, self.client = store, client
        self.sessions = AgentSessionManager(store.raw)
        self.busy = False
        self.latest_transition = None  # Runtime observation, not a memory source.

    @contextmanager
    def claim(self):
        if self.busy:
            raise MemoryError("memory_busy")
        self.busy = True
        try:
            yield
        finally:
            self.busy = False

    def read(self):
        state = self.store.read()
        return {"state": state, "busy": self.busy,
                "applicable_stages": applicable_stages(state),
                "preview": build_context(state)[1] if state else None,
                "transition": self.latest_transition}

    def initialize(self):
        with self.claim():
            self.store.initialize()
        return self.read()

    def mutate(self, request):
        with self.claim():
            self.store.mutate(request)
        return self.read()

    def transition(self, action, request):
        with self.claim():
            before = self.store.require(request.snapshot_id)
            after = self.store.transition(action, request.snapshot_id)
            # Publish only after durable commit. Cache loads the new session through the old contract.
            self.sessions.get(after["session_id"])
            self.latest_transition = {
                "action": action,
                "before": {k: before[k] for k in ("memory_owner_id", "task_id", "session_id")},
                "after": {k: after[k] for k in ("memory_owner_id", "task_id", "session_id")},
            }
        return self.read()

    async def send(self, request):
        with self.claim():
            state = self.store.require(request.snapshot_id)
            if request.message == SEED and (state["short_term"] or state["working"] or state["long_term"]):
                raise MemoryError("seed_requires_empty_memory")
            policy, selection = build_context(state)
            agent = SimpleAgent(self.client, DAY11_CONFIG, context_policy=policy)
            result = await agent.run_turn(self.sessions.get(state["session_id"]), request.message)
            observation = self._observation(state, selection, (*policy.messages, ConversationMessage("user", request.message)),
                                            DAY11_CONFIG, result.outcome)
            observation["committed"] = result.committed
        return {"current": self.read(), "observation": observation}

    @staticmethod
    def _observation(state, selection, messages, config, result):
        return {
            "attempt_id": str(uuid4()), "snapshot_id": state["snapshot_id"], "stored": state,
            "selection": selection, "request": generation_payload(messages, config),
            "status": result.status, "reply": result.reply, "error": result.error_code,
            "usage": asdict(result.usage) if result.usage is not None else None,
            "stage": None, "input_checks": {}, "output_checks": {}, "parsed": None,
            "committed": False,
        }

    async def verify(self, stage, request):
        if stage not in EXPECTED:
            raise MemoryError("invalid_stage", 422)
        with self.claim():
            state = self.store.require(request.snapshot_id)
            if stage not in applicable_stages(state):
                raise MemoryError("scenario_not_applicable", 422)
            policy, selection = build_context(state)
            messages = (*policy.messages, ConversationMessage("user", QUERY))
            expected = dict(zip(FIELDS, EXPECTED[stage]))
            input_checks = availability(state, selection, expected)
            result = await SimpleAgent(self.client, VERIFY_CONFIG).generate(messages)
            observation = self._observation(state, selection, messages, VERIFY_CONFIG, result)
            observation["stage"], observation["input_checks"] = stage, input_checks
            parsed = None
            if result.status == "completed":
                try:
                    parsed = VerificationOutput.model_validate(strict_json(result.reply)).model_dump()
                except (ValueError, TypeError):
                    observation["status"], observation["error"] = "invalid", "invalid_structured_output"
            observation["parsed"] = parsed
            observation["output_checks"] = {
                key: {"status": "unavailable" if parsed is None else "match" if parsed[key] == value else "mismatch",
                      "expected": value, "actual": parsed[key] if parsed else None,
                      "correct": None if parsed is None else parsed[key] == value}
                for key, value in expected.items()
            }
        return {"current": self.read(), "observation": observation}
