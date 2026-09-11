import asyncio
import json
import sqlite3
from uuid import uuid4
from dataclasses import replace
import pytest

from test_context_strategies import lab, finish, request
from app.context_strategies_models import *
from app.context_strategies_scenario import FIXTURES
from app.context_strategies_verifier import retention, assistant_assertions
from app.fact_extractor import apply_patch, facts_message
from app.context_strategies_store import Day10Store, sources
from app.llm_client import LlmResult, TokenUsage
from app.token_diagnostics import CountFailure


def patch(**changes):
    return json.dumps({"changes":[dict(state="set",scope="shared",key="deadline_weeks",kind="constraint",value=8,evidence="deadline_weeks=8") | changes]})


def test_patch_updates_clears_omissions_and_invalid_evidence():
    f=apply_patch([],patch(),FIXTURES[1],"u2")
    assert apply_patch(f,'{"changes":[]}',FIXTURES[4],"u5") == f
    f=apply_patch(f,patch(value=6,evidence="deadline_weeks=6"),FIXTURES[4],"u5")
    assert f[0]["value"] == 6 and f[0]["user_id"] == "u5"
    for bad in [patch(value=True),patch(scope="A"),patch(evidence="weeks=8"),patch(value=137),patch(op="replace"),patch()+"garbage"]:
        with pytest.raises(LabError): apply_patch([],bad,FIXTURES[1],"u")
    with pytest.raises(LabError): apply_patch([],json.dumps({"changes":json.loads(patch())["changes"]*2}),FIXTURES[1],"u")
    clear=patch(state="cleared",key="email_reminders",value=None,evidence="email_reminders=cleared")
    with pytest.raises(LabError, match="extraction_clear_missing"):
        apply_patch([],clear,FIXTURES[5],"u6")
    previous=apply_patch([],patch(key="email_reminders",value=True,evidence="email_reminders=true"),FIXTURES[3],"u4")
    tombstone=apply_patch(previous,clear,FIXTURES[5],"u6")
    assert tombstone[0]["state"] == "cleared"
    assert "evidence" not in facts_message(f).content and "user_id" not in facts_message(f).content


@pytest.mark.asyncio
async def test_actual_retention_grammar_not_audit(lab):
    svc,_=lab; metadata=await finish(lab,"window"); run=svc.store.load(metadata["run_id"],"window")
    selected=sources(run,"A"); order={s["user_id"]:s["step_id"] for s in run["steps"]}
    selected[1]["content"]='pilot_users=37;platform=Android'
    assert retention(selected,[],"A",order)["score"] == 5
    selected[3]["content"]='pilot_users=137'
    assert retention(selected,[],"A",order)["score"] == 4
    selected[-1]["content"]='Мы всё обсудили, вот мои советы.'
    assert retention(selected,[],"A",order)["reason"] == "unverifiable_restatement"
    assert assistant_assertions('{"scope":"A","payment":"on_site"}') == {("A","payment"):"on_site"}
    with pytest.raises(ValueError): assistant_assertions('payment=on_site')


@pytest.mark.asyncio
async def test_two_slots_block_mutations_same_slot_and_clean_up(lab):
    svc,fake=lab; run=await finish(lab,"facts"); fake.entered.clear(); fake.wait=asyncio.Event()
    a=asyncio.create_task(svc.evaluate(run["run_id"],"facts","A",request(run)))
    await fake.entered.wait()
    b=asyncio.create_task(svc.evaluate(run["run_id"],"facts","B",request(run)))
    await asyncio.sleep(0)
    with pytest.raises(LabError,match="run_busy"): await svc.evaluate(run["run_id"],"facts","A",request(run))
    with pytest.raises(LabError,match="run_busy"): svc.reset(run["run_id"],"facts")
    a.cancel()
    with pytest.raises(asyncio.CancelledError): await a
    fake.wait.set(); result=await b
    assert result["receipt"]["status"] == "completed"
    assert not svc.guard.active and len(svc.store.outputs(run["run_id"]))==1


@pytest.mark.asyncio
async def test_branch_invariant_blocks_before_count(lab,monkeypatch):
    svc,fake=lab; run=await finish(lab,"branches"); size=len(fake.calls); counts=len(fake.counts)
    def leaking(run,target): return run["messages"]
    monkeypatch.setattr("app.context_strategies_service.sources",leaking)
    result=await svc.evaluate(run["run_id"],"branches","A",request(run))
    assert result["receipt"]["error"]=="branch_isolation_violated"
    assert result["run"]["outputs"][0]["isolation"] is False
    assert len(fake.calls)==size and len(fake.counts)==counts


@pytest.mark.asyncio
async def test_preflight_unknown_overflow_never_fallback(lab):
    svc,fake=lab; run=svc.store.create("facts")
    async def fail(*args,**kwargs): raise CountFailure("count_unavailable")
    fake.count=fail
    outcome=await svc.send(run["run_id"],"facts",request(run,1))
    assert outcome["receipt"]["error"]=="count_unavailable"
    assert not outcome["receipt"]["response"]["attempted"]
    assert outcome["receipt"]["extraction"]["usage"]["total_tokens"]==12
    assert outcome["run"]["revision"]==0
    async def huge(*args,**kwargs): return 128001
    fake.count=huge
    outcome=await svc.send(run["run_id"],"facts",request(run,1))
    assert outcome["receipt"]["error"]=="preflight_context_exceeded"
    assert len(fake.calls)==2


@pytest.mark.asyncio
async def test_checkpoint_topology_validation_and_corruption(lab):
    svc,fake=lab; run=svc.store.create("branches")
    with pytest.raises(LabError,match="checkpoint_not_ready"): svc.checkpoint(run["run_id"],"branches",0)
    for i in range(1,7): run=(await svc.send(run["run_id"],"branches",request(run,i)))["run"]
    with pytest.raises(LabError,match="checkpoint_required"): await svc.send(run["run_id"],"branches",request(run,7))
    run=svc.checkpoint(run["run_id"],"branches",run["revision"])
    assert svc.checkpoint(run["run_id"],"branches",6)["revision"]==7
    req=request(run,7); req.target="C"
    with pytest.raises(LabError,match="invalid_target"): await svc.send(run["run_id"],"branches",req)
    assert len(fake.calls)==6
    db=svc.store.connection
    db.execute("UPDATE runs SET config_version='wrong' WHERE run_id=?",(run["run_id"],))
    with pytest.raises(LabError,match="configuration_mismatch"): svc.read(run["run_id"],"branches")


def test_corrupt_schema_is_not_migrated(tmp_path):
    path=tmp_path/"wrong.db"
    db=sqlite3.connect(path); db.execute("CREATE TABLE old(value)"); db.close()
    with pytest.raises(LabError,match="storage_schema_invalid"): Day10Store(path)
    db=sqlite3.connect(path)
    assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[("old",)]
    db.close()


@pytest.mark.asyncio
async def test_failed_sqlite_commit_rolls_back_all_four_tables(lab):
    svc,fake=lab; run=svc.store.create("facts")
    db=svc.store.connection
    def authorizer(action,arg1,arg2,*rest):
        return sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_TRANSACTION and arg1=="COMMIT" else sqlite3.SQLITE_OK
    db.set_authorizer(authorizer)
    result=await svc.send(run["run_id"],"facts",request(run,1))
    db.set_authorizer(None)
    assert result["receipt"]["error"]=="storage_error"
    assert svc.store.load(run["run_id"],"facts")==run
    assert not db.in_transaction


@pytest.mark.asyncio
async def test_output_write_failure_never_commits_conversation(lab):
    svc,fake=lab; run=await finish(lab,"window")
    svc.store.connection.execute("CREATE TEMP TRIGGER reject_output BEFORE INSERT ON evaluation_outputs BEGIN SELECT RAISE(ABORT,'test'); END")
    result=await svc.evaluate(run["run_id"],"window","A",request(run))
    assert result["receipt"]["error"]=="storage_error"
    assert result["receipt"]["response"]["usage"]["total_tokens"]==12
    assert result["run"]["revision"]==8 and not result["run"]["outputs"]
