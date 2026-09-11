import asyncio
from dataclasses import asdict
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.context_policy import SlidingWindowContextPolicy
from app.context_strategies_models import *
from app.context_strategies_scenario import FIXTURES, catalog, target_for
from app.context_strategies_service import ContextStrategiesService
from app.context_strategies_store import Day10Store, sources, snapshot_id
from app.context_strategies_verifier import quality, SHARED, ALTERNATIVES, assistant_assertions
from app.fact_extractor import apply_patch, user_assertions
from app.llm_client import ConversationMessage, LlmResult, TokenUsage, AgentConfig
from app.openai_agent_payload import generation_payload, context_payload
from app.main import app


class Provider:
    def __init__(self, store):
        self.store, self.calls, self.counts = store, [], []
        self.failure, self.wait, self.entered = None, None, asyncio.Event()

    async def count(self, messages, config, *, include_instructions):
        assert not self.store.connection.in_transaction
        self.counts.append(context_payload(messages,config,include_instructions=include_instructions))
        return 250

    async def complete(self, messages, config):
        assert not self.store.connection.in_transaction
        self.calls.append((messages,config))
        self.entered.set()
        if self.wait: await self.wait.wait()
        if self.failure == config.text_format or self.failure == "all":
            return LlmResult("error",error_code="fake_failure",usage=TokenUsage(input_tokens=10,output_tokens=2,total_tokens=12))
        if config == EXTRACTION_CONFIG:
            data = json.loads(messages[0].content)
            assert set(data) == {"current_user"}
            changes = []
            for (scope,key),(value,evidence) in user_assertions(data["current_user"]).items():
                state = "cleared" if value is None else "set"
                changes.append(dict(state=state,scope=scope,key=key,value=value,evidence=evidence,kind="other"))
            reply = json.dumps({"changes":changes},ensure_ascii=False)
        elif config == EVALUATION_CONFIG:
            variant = "A" if "варианта A" in messages[-1].content else "B"
            reply = json.dumps({**SHARED,**ALTERNATIVES[variant]},ensure_ascii=False)
        else: reply = "Принято."
        return LlmResult("completed",reply=reply,usage=TokenUsage(input_tokens=10,output_tokens=2,total_tokens=12))


@pytest.fixture
def lab(tmp_path):
    store = Day10Store(tmp_path/"day10.db")
    fake = Provider(store)
    # None is the default text format, so use a distinct sentinel for no failure.
    fake.failure = "none"
    service = ContextStrategiesService(store,fake,fake)
    yield service,fake
    store.close()


def request(run, step=None):
    values = dict(expected_revision=run["revision"],attempt_id=str(uuid4()))
    if step: values.update(step_id=step,target=target_for(run["strategy"],step),message=FIXTURES[step-1])
    return SimpleNamespace(**values)


async def finish(lab, strategy):
    svc,_ = lab
    run = svc.store.create(strategy)
    for step in range(1,9):
        if strategy == "branches" and step == 7:
            run = svc.checkpoint(run["run_id"],strategy,run["revision"])
        outcome = await svc.send(run["run_id"],strategy,request(run,step))
        assert outcome["receipt"]["committed"],outcome
        run = outcome["run"]
    return run


@pytest.mark.asyncio
@pytest.mark.parametrize("size",[0,2,4,6,8,16])
async def test_fixed_window(size):
    history = tuple(ConversationMessage("user" if i%2==0 else "assistant",str(i)) for i in range(size))
    prepared = await SlidingWindowContextPolicy().prepare("x",history)
    assert prepared.messages == history[-6:]


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy",["window","facts","branches"])
async def test_controlled_budget_sources_restore_and_evaluation(lab,strategy):
    svc,fake = lab
    run = await finish(lab,strategy)
    before = svc.store.load(run["run_id"],strategy)
    assert len(before["messages"]) == 16
    assert len(fake.calls) == (16 if strategy == "facts" else 8)
    if strategy == "facts":
        facts = {(f["scope"],f["key"]):f for f in before["facts"]}
        assert facts["shared","deadline_weeks"]["value"] == 6
        assert facts["shared","email_reminders"]["state"] == "cleared"
        assert facts["A","payment"]["value"] == "on_site"
        for messages,config in fake.calls:
            if config == EXTRACTION_CONFIG:
                data = json.loads(messages[0].content)
                assert set(data) == {"current_user"}
                assert len(messages) == 1 and data["current_user"] in FIXTURES
    outcomes = await asyncio.gather(*(svc.evaluate(run["run_id"],strategy,v,request(run)) for v in ("B","A")))
    after = svc.store.load(run["run_id"],strategy)
    assert before == after
    outputs = svc.store.outputs(run["run_id"])
    assert {o["snapshot_id"] for o in outputs} == {snapshot_id(before)}
    for out in outputs:
        assert out["quality"]["score"] == 11
        assert out["retention"]["score"] == (3 if strategy == "window" else 11)
        assert out["isolation"] is (True if strategy == "branches" else None)
        selected = sources(before,out["variant"])
        assert out["source_ids"] == [m["message_id"] for m in selected]
    eval_calls = [(m,c) for m,c in fake.calls if c == EVALUATION_CONFIG]
    if strategy != "branches": assert eval_calls[0][0][:-1] == eval_calls[1][0][:-1]
    else:
        assert FIXTURES[6] not in [m.content for m in eval_calls[0][0]]
        assert FIXTURES[7] not in [m.content for m in eval_calls[1][0]]
    if strategy == "window":
        assert len(fake.calls[-1][0]) == 7
        assert FIXTURES[0] not in [m.content for m in fake.calls[-1][0]]
        assert FIXTURES[0] not in json.dumps(fake.counts[-1],ensure_ascii=False)
    assert len(fake.counts) == 10
    assert len(fake.calls) == (18 if strategy == "facts" else 10)
    path = svc.store.connection.execute("PRAGMA database_list").fetchone()[2]
    reopened = Day10Store(__import__('pathlib').Path(path))
    assert reopened.load(run["run_id"],strategy) == before
    assert reopened.outputs(run["run_id"]) == outputs
    reopened.close()
    svc.reset(run["run_id"],strategy)
    svc.reset(run["run_id"],strategy)
    assert svc.store.connection.execute("SELECT count(*) FROM messages").fetchone()[0] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure",["extraction","response","commit"])
async def test_atomic_failure(lab,failure,monkeypatch):
    svc,fake = lab
    run = svc.store.create("facts")
    if failure == "extraction": fake.failure = EXTRACTION_CONFIG.text_format
    if failure == "response": fake.failure = None
    if failure == "commit":
        svc.store.connection.execute("CREATE TEMP TRIGGER reject_pair BEFORE INSERT ON scenario_steps BEGIN SELECT RAISE(ABORT,'test'); END")
    outcome = await svc.send(run["run_id"],"facts",request(run,1))
    assert not outcome["receipt"]["committed"]
    assert outcome["receipt"]["extraction"]["usage"]["input_tokens"] == 10
    assert svc.store.load(run["run_id"],"facts") == run
    assert len(fake.calls) == (1 if failure == "extraction" else 2)
    assert not svc.guard.active


@pytest.mark.asyncio
async def test_busy_cancellation_and_namespaces(lab):
    svc,fake = lab
    run = svc.store.create("window")
    fake.wait = asyncio.Event()
    task = asyncio.create_task(svc.send(run["run_id"],"window",request(run,1)))
    await fake.entered.wait()
    for action in (lambda:svc.reset(run["run_id"],"window"),lambda:svc.checkpoint(run["run_id"],"window",0)):
        with pytest.raises(LabError,match="run_busy"): action()
    with pytest.raises(LabError,match="run_busy"):
        await svc.send(run["run_id"],"window",request(run,1))
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert not svc.guard.active
    with pytest.raises(LabError,match="run_not_found"): svc.read(run["run_id"],"facts")
    assert svc.store.load(run["run_id"],"window")["revision"] == 0


def test_strict_schema_quality_and_no_answer_values():
    payload = generation_payload((),AgentConfig())
    assert payload["text"]["format"] == {"type":"text"}
    schema = EVALUATION_CONFIG.text_format
    assert schema["strict"] is True
    assert set(schema["schema"]["properties"]) == set(SHARED)|set(ALTERNATIVES["A"])
    assert "on_site" not in json.dumps(schema)
    values = {**SHARED,**ALTERNATIVES["A"]}
    assert quality(json.dumps(values),"A")["score"] == 11
    values["pilot_users"] = 137
    assert quality(json.dumps(values),"A")["score"] == 10
    values["pilot_users"] = True
    assert quality(json.dumps(values),"A")["score"] is None
    values = dict.fromkeys(values)
    assert quality(json.dumps(values),"A")["score"] == 0
    assert quality(json.dumps(values)[:-1]+',"pilot_users":37}',"A")["score"] is None
    assert assistant_assertions(' scope=A;payment=on_site,confirmation=immediate ') == {("A","payment"):"on_site",("A","confirmation"):"immediate"}
    with pytest.raises(ValueError): assistant_assertions("Кажется, мы всё обсудили")


@pytest.mark.asyncio
async def test_api_strict_and_reconciliation(lab):
    svc,fake = lab
    app.state.context_strategies = svc
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
        base = "/api/v1/context-strategies/window/runs"
        versions = {"config_version":VERSION,"scenario_version":SCENARIO}
        run = (await client.post(base,json=versions)).json()
        url = base+"/"+run["run_id"]
        req = {**versions,**vars(request(run,1))}
        assert (await client.post(url+"/messages",json={**req,"history":[]})).status_code == 422
        result = (await client.post(url+"/messages",json=req)).json()
        assert result["receipt"]["committed"]
        assert (await client.get(url)).json()["revision"] == 1
        assert (await client.post(url+"/messages",json=req)).status_code == 409
        assert (await client.get(url.replace("window","facts"))).status_code == 404
        mid = result["run"]["steps"][0]["user_id"]
        assert (await client.get(url+"/messages/"+mid)).json()["content"] == FIXTURES[0]
        assert len(fake.calls) == 1
