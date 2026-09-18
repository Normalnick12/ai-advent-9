"""Reusable Send orchestration. Sources, preparation, policy and candidate bindings are injected."""
from copy import deepcopy
from dataclasses import asdict, replace
from uuid import uuid4

from app.agent_sessions import AgentSessionManager
from app.llm_capture import CapturingClient
from app.validated_turn import run_validated_turn


class SendCoordinator:
    def __init__(self, conversation_store, client):
        self.store, self.client = conversation_store, client
        self.sessions = AgentSessionManager(conversation_store)
        self.reconciliation_required = False

    def reconcile(self, session_id):
        fresh = AgentSessionManager(self.store)
        fresh.get(session_id)
        self.sessions = fresh
        self.reconciliation_required = False

    async def send(self, *, session_id, query, history_policy, prepare, adapter_factory,
                   required_rules, validate, render, refuse, sources, coverage,
                   precheck=None, on_dispatch=None):
        calls = 0
        adapter = prepared = None

        def dispatched():
            nonlocal calls
            calls += 1
            if on_dispatch:
                on_dispatch()

        capture = CapturingClient(self.client, dispatched)

        async def generate():
            nonlocal prepared, adapter
            prepared = prepare()
            adapter = adapter_factory(capture, prepared)
            return await adapter.generate()

        turn = await run_validated_turn(self.sessions.get(session_id), query,
            context_policy=history_policy, required_rules=required_rules, precheck=precheck,
            generate=generate, validate=validate, render=render, refuse=refuse)
        if turn.commit_status == "unknown":
            self.reconciliation_required = True
            try:
                self.reconcile(session_id)
                if self.sessions.get(session_id).history == history_policy.history:
                    turn = replace(turn, commit_status="failed")
            except Exception:
                self.reconciliation_required = True
        actual = capture.request
        return deepcopy({
            "attempt_id": str(uuid4()), "operation": "send", "session_id": session_id,
            "query": query, "outcome": turn.decision if turn.status == "completed" else "technical_error",
            "sources": sources, "coverage": coverage,
            "provider_dispatch": "dispatched" if calls else "not_dispatched",
            "generation_calls": calls, "actual_request": actual,
            "profile_section": prepared.profile_section if prepared else None,
            "state_section": prepared.state_section if prepared else None,
            "invariant_section": prepared.invariant_section if prepared else None,
            "provider_outcome": adapter.outcome if adapter else None,
            "raw_candidate": adapter.outcome.get("reply") if adapter and adapter.outcome else None,
            "candidate": adapter.candidate.model_dump() if adapter and adapter.candidate else None,
            "candidate_preparation": adapter.preparation if adapter else "not_attempted",
            "precheck_status": "not_applicable" if precheck is None else
                turn.precheck.status if turn.precheck else "not_attempted",
            "assembly_status": ("passed" if actual["config"] == asdict(adapter.config)
                and actual["messages"] == [asdict(m) for m in prepared.messages] else "failed")
                if actual and adapter and prepared else "not_attempted",
            "turn": asdict(turn),
            "pair_position": len(history_policy.history) if turn.commit_status == "committed" else None,
        })
