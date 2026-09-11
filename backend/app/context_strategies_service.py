"""Concrete Day 10 orchestration; providers never see stored audit/output tables."""
import asyncio
from contextlib import contextmanager
from dataclasses import asdict
from uuid import uuid4

from app.agent import SimpleAgent
from app.context_policy import SlidingWindowContextPolicy
from app.context_strategies_models import DAY10_CONFIG, EVALUATION_CONFIG, LabError, Receipt, evaluation_question
from app.context_strategies_store import sources, snapshot_id
from app.context_strategies_verifier import quality, retention
from app.fact_extractor import FactExtractor, facts_message
from app.llm_client import ConversationMessage
from app.token_diagnostics import CountFailure, PREFLIGHT_TIMEOUT


class RunGuard:
    def __init__(self):
        self.active = {}

    @contextmanager
    def claim(self, run_id, slot="mutation", revision=None):
        existing = self.active.get(run_id, {})
        if existing and (slot == "mutation" or "mutation" in existing or slot in existing or
                         any(r != revision for r in existing.values())):
            raise LabError("run_busy")
        self.active.setdefault(run_id, {})[slot] = revision
        try:
            yield
        finally:
            self.active[run_id].pop(slot)
            if not self.active[run_id]: self.active.pop(run_id)


async def response(agent, messages, receipt):
    try:
        receipt.preflight = await asyncio.wait_for(
            agent.count_messages(messages, include_instructions=True), PREFLIGHT_TIMEOUT)
    except CountFailure as exc:
        raise LabError(exc.code, 502) from None
    except TimeoutError:
        raise LabError("count_timeout", 502) from None
    if receipt.preflight > 128000: raise LabError("preflight_context_exceeded", 422)
    phase = receipt.response
    phase.attempted, phase.status = True, "running"
    try:
        result = await agent.generate(messages)
        phase.status, phase.usage, phase.error = result.status, result.usage, result.error_code
        if result.status != "completed": raise LabError(result.error_code or result.status, 502)
        return result.reply
    except BaseException:
        if phase.status == "running": phase.status, phase.error = "unknown", "interrupted"
        raise


class OrdinaryTurn:
    """Only SimpleAgent.run_turn invokes this concrete preparation/commit lifecycle."""
    def __init__(self, service, target, step, receipt):
        self.service, self.target, self.step, self.receipt = service, target, step, receipt

    async def run(self, agent, run, message):
        user_id = str(uuid4())
        facts = run["facts"]
        if run["strategy"] == "facts":
            facts = await self.service.extractor.extract(
                facts, message, user_id, self.receipt.extraction,
                run_id=run["run_id"], attempt_id=self.receipt.attempt_id, scenario_step=self.step)
        selected = sources(run, self.target)
        raw = tuple(ConversationMessage(m["role"],m["content"]) for m in selected)
        if run["strategy"] == "window":
            raw = (await SlidingWindowContextPolicy().prepare(run["run_id"], raw)).messages
        messages = ((facts_message(facts),) if run["strategy"] == "facts" else ()) + raw + (ConversationMessage("user",message),)
        reply = await response(agent, messages, self.receipt)
        self.service.store.commit_turn(run, self.target, self.step, user_id, message, reply, facts)
        self.receipt.status, self.receipt.committed, self.receipt.reply = "completed", True, reply


class ContextStrategiesService:
    def __init__(self, store, client, counter):
        self.store, self.guard = store, RunGuard()
        self.agent = SimpleAgent(client, DAY10_CONFIG, counter)
        self.evaluator = SimpleAgent(client, EVALUATION_CONFIG, counter)
        self.extractor = FactExtractor(client)

    def read(self, run_id, strategy):
        run = self.store.load(run_id, strategy)
        metadata = {k:v for k,v in run.items() if k != "messages"}
        metadata["counts"] = {s:sum(m["stream"] == s for m in run["messages"]) for s in ("root","A","B")}
        metadata["latest"] = {s:next((m["content"] for m in reversed(run["messages"]) if m["stream"] == s and m["role"] == "assistant"),None) for s in ("root","A","B")}
        metadata["message_refs"] = [{k:m[k] for k in ("message_id","stream","role")} for m in run["messages"]]
        metadata["outputs"] = self.store.outputs(run_id)
        metadata["busy"] = list(self.guard.active.get(run_id, {}))
        return metadata

    async def send(self, run_id, strategy, request):
        with self.guard.claim(run_id):
            run = self.store.check_revision(run_id,strategy,request.expected_revision)
            self.store.validate_send(run,request.target,request.step_id,request.message)
            receipt = Receipt(str(request.attempt_id))
            try:
                async with asyncio.timeout(180):
                    await self.agent.run_turn(run, request.message,
                        day10=OrdinaryTurn(self,request.target,request.step_id,receipt))
            except LabError as exc: receipt.error = exc.code
            except (TimeoutError, Exception): receipt.error = "operation_failed"
            finally:
                for phase in (receipt.extraction, receipt.response):
                    if phase.status == "running": phase.status, phase.error = "unknown", "interrupted"
            return {"receipt":asdict(receipt),"run":self.read(run_id,strategy)}

    async def evaluate(self, run_id, strategy, variant, request):
        with self.guard.claim(run_id,variant,request.expected_revision):
            run = self.store.check_revision(run_id,strategy,request.expected_revision)
            if len(run["steps"]) != 8: raise LabError("evaluation_not_ready")
            selected = sources(run,variant)
            opposite = {m["message_id"] for m in run["messages"] if m["stream"] == ("B" if variant == "A" else "A")}
            isolated = not (opposite & {m["message_id"] for m in selected}) if strategy == "branches" else None
            facts = run["facts"] if strategy == "facts" else []
            observation = retention(selected, facts, variant, {s["user_id"]:s["step_id"] for s in run["steps"]})
            messages = ((facts_message(facts),) if strategy == "facts" else ()) + tuple(
                ConversationMessage(m["role"],m["content"]) for m in selected) + (ConversationMessage("user",evaluation_question(variant)),)
            receipt = Receipt(str(request.attempt_id))
            output = {"snapshot_id":snapshot_id(run),"revision":run["revision"],"variant":variant,
                "attempt_id":str(request.attempt_id),"retention":observation,"isolation":isolated,
                "source_ids":[m["message_id"] for m in selected],"status":"error","reply":None,
                "quality":{"score":None,"reason":"generation_failed"},"error":None}
            try:
                if isolated is False:
                    output["retention"] = {"score":None,"total":11,"reason":"branch_isolation_violated"}
                    raise LabError("branch_isolation_violated",500)
                async with asyncio.timeout(100):
                    reply = await response(self.evaluator,messages,receipt)
                output["quality"] = quality(reply,variant)
                output["reply"] = reply
                output["status"] = "completed" if output["quality"]["score"] is not None else "invalid"
                receipt.status, receipt.reply = output["status"],reply
            except LabError as exc: receipt.error = exc.code
            except (TimeoutError, Exception): receipt.error = "operation_failed"
            output["error"] = receipt.error
            try: self.store.save_output(run,output)
            except LabError as exc:
                receipt.status, receipt.error = "error",exc.code
            return {"receipt":asdict(receipt),"run":self.read(run_id,strategy)}

    def checkpoint(self, run_id, strategy, revision):
        with self.guard.claim(run_id): self.store.checkpoint(run_id,strategy,revision)
        return self.read(run_id,strategy)

    def reset(self, run_id, strategy):
        with self.guard.claim(run_id): self.store.delete(run_id,strategy)
