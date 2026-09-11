import json
import re
from pathlib import Path
from dataclasses import replace
import pytest
from test_context_strategies import lab, finish, request
from app.context_strategies_models import LabError, EVALUATION_CONFIG
from app.context_strategies_scenario import FIXTURES
from app.context_strategies_verifier import retention
from app.context_strategies_store import sources
from app.llm_client import LlmResult


def test_catalog_bytes_equal_eight_canonical_spec_blocks():
    root = Path(__file__).parents[2]
    path = root / "openspec/changes/day-10-context-strategies/specs/context-strategies-experiment/spec.md"
    if not path.exists():
        path = root / "openspec/specs/context-strategies-experiment/spec.md"
    spec = path.read_text(encoding="utf-8")
    blocks=re.findall(r"```text\n(.*?)\n```",spec,re.S)
    assert tuple(blocks)==FIXTURES
    assert all("\r" not in text and not text.endswith("\n") for text in FIXTURES)


@pytest.mark.asyncio
async def test_incomplete_pair_rejected_without_repair(lab):
    svc,_=lab; run=svc.store.create("window")
    svc.store.connection.execute("INSERT INTO messages VALUES ('bad',?,'root',0,'user','audit')",(run["run_id"],))
    with pytest.raises(LabError,match="run_state_invalid"): svc.read(run["run_id"],"window")


@pytest.mark.asyncio
@pytest.mark.parametrize("status",["refused","incomplete","invalid"])
async def test_invalid_evaluation_keeps_quality_unavailable(lab,status):
    svc,fake=lab; run=await finish(lab,"window")
    original=fake.complete
    async def complete(messages,config):
        result=await original(messages,config)
        return replace(result,status="completed" if status=="invalid" else status,reply="{}");
    fake.complete=complete
    result=await svc.evaluate(run["run_id"],"window","A",request(run))
    assert result["run"]["outputs"][0]["quality"]["score"] is None
    assert result["run"]["revision"]==8


@pytest.mark.asyncio
async def test_fact_correction_supersedes_older_assistant_restatement(lab):
    svc,_=lab; metadata=await finish(lab,"facts"); run=svc.store.load(metadata["run_id"],"facts")
    chosen=run["messages"][2:6]
    chosen[1]["content"]="deadline_weeks=8"
    order={s["user_id"]:s["step_id"] for s in run["steps"]}
    assert retention(chosen,run["facts"],"A",order)["score"]==11


@pytest.mark.asyncio
async def test_readiness_wrong_revision_and_noncanonical_rejected_before_calls(lab):
    svc,fake=lab; run=svc.store.create("window")
    with pytest.raises(LabError,match="evaluation_not_ready"): await svc.evaluate(run["run_id"],"window","A",request(run))
    req=request(run,1); req.message+=" "
    with pytest.raises(LabError,match="scenario_not_applicable"): await svc.send(run["run_id"],"window",req)
    req=request(run,1); req.expected_revision=1
    with pytest.raises(LabError,match="revision_conflict"): await svc.send(run["run_id"],"window",req)
    assert not fake.calls and not fake.counts
