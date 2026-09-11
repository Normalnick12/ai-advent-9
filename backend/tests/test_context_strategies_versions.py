"""Current prompt/historical namespace contracts, fake providers and temporary stores only."""
from dataclasses import replace
import json
from pathlib import Path
import re

import pytest
from httpx import ASGITransport, AsyncClient

from app import context_strategies_store as storage
from app.context_strategies_models import VERSION, SCENARIO, EXTRACTION_CONFIG, EVALUATION_CONFIG, DAY10_CONFIG, LabError
from app.context_strategies_scenario import FIXTURES
from app.context_strategies_service import ContextStrategiesService
from app.main import app
from test_context_strategies import lab, request, Provider

HISTORICAL = ("day10-gpt4o-mini-n6-v1", "day10-gpt4o-mini-n6-v2")
DEFAULT_PATH = Path(app.state.strategies_database_path)


def test_exact_v3_prompt_and_fixed_identities():
    changes = Path(__file__).parents[2] / "openspec/changes"
    path = changes / "day-10-context-strategies/design.md"
    if not path.exists():
        path, = (changes / "archive").glob("*-day-10-context-strategies/design.md")
    design = path.read_text(encoding="utf-8")
    section = design.split("#### Extractor instructions v3", 1)[1]
    exact = re.search(r"```text\n(.*?)\n```", section, re.S)[1]
    assert EXTRACTION_CONFIG.instructions == exact
    assert "Ты не выбираешь storage operation" in exact
    assert "Не переноси evidence или value между keys" in exact
    assert "Не выводи op, add или replace" in exact
    assert VERSION == "day10-gpt4o-mini-n6-v3" and SCENARIO == "meeting-rooms-v1"
    assert DEFAULT_PATH.parts[-3:] == ("context-strategies", VERSION, "experiments.sqlite3")
    assert EXTRACTION_CONFIG.text_format["name"] == "facts-v2"
    assert EVALUATION_CONFIG.text_format["name"] == "meeting-spec-v1"
    for config in (DAY10_CONFIG, EXTRACTION_CONFIG, EVALUATION_CONFIG):
        assert config.version == VERSION and config.model == "gpt-4o-mini"
    assert replace(EXTRACTION_CONFIG, instructions=DAY10_CONFIG.instructions,
                   text_format=DAY10_CONFIG.text_format, max_output_tokens=DAY10_CONFIG.max_output_tokens) == DAY10_CONFIG
    assert replace(EVALUATION_CONFIG, text_format=DAY10_CONFIG.text_format) == DAY10_CONFIG


@pytest.mark.asyncio
@pytest.mark.parametrize("case,reason", [("previous_only", "assertion_not_found"), ("borrowed_evidence", "evidence_mismatch"), ("omission", None)])
async def test_v3_input_and_unmodified_rejection_or_omission(lab, caplog, case, reason):
    svc, fake = lab
    run = svc.store.create("facts")
    for step in range(1, 4):
        run = (await svc.send(run["run_id"], "facts", request(run, step)))["run"]
    before = svc.store.load(run["run_id"], "facts")
    original = fake.complete

    async def complete(messages, config):
        result = await original(messages, config)
        if config != EXTRACTION_CONFIG:
            return result
        data = json.loads(messages[0].content)
        assert len(messages) == 1 and messages[0].role == "user"
        assert data == {"current_user": FIXTURES[3]}
        patch = json.loads(result.reply)
        if case == "previous_only":
            patch["changes"].insert(0, dict(state="set", scope="shared", key="offline_schedule", kind="preference", value=True, evidence="email_reminders=true"))
        elif case == "borrowed_evidence":
            patch["changes"][0]["evidence"] = "email_reminders=true"
        else:
            patch["changes"] = []
        return replace(result, reply=json.dumps(patch))

    fake.complete = complete
    outcome = await svc.send(run["run_id"], "facts", request(run, 4))
    after = svc.store.load(run["run_id"], "facts")
    if reason:
        diagnostic, = [r.facts_diagnostic for r in caplog.records if hasattr(r, "facts_diagnostic")]
        assert diagnostic["reason"] == reason and diagnostic["change_index"] == 0
        assert outcome["receipt"]["error"] == "extraction_unsupported_change"
        assert not outcome["receipt"]["response"]["attempted"]
        assert after == before and len(fake.calls) == 7 and len(fake.counts) == 3
    else:
        assert outcome["receipt"]["committed"] and after["revision"] == 4
        assert after["facts"] == before["facts"]  # No backend repair from fixture assertions.
        assert len(fake.calls) == 8 and len(fake.counts) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("historical_version", HISTORICAL)
async def test_historical_stores_preserved_and_never_fallback(tmp_path, monkeypatch, historical_version):
    old_path = tmp_path / historical_version / "experiments.sqlite3"
    new_path = tmp_path / VERSION / "experiments.sqlite3"
    # Simulate the historical store profile without opening the developer's live DB.
    with monkeypatch.context() as historical:
        historical.setattr(storage, "VERSION", historical_version)
        old = storage.Day10Store(old_path)
        fake = Provider(old); fake.failure = "none"
        svc = ContextStrategiesService(old, fake, fake)
        run = old.create("facts")
        for step in range(1, 4):
            run = (await svc.send(run["run_id"], "facts", request(run, step)))["run"]
        old_state = old.load(run["run_id"], "facts")
        old.close()
    old_bytes = old_path.read_bytes()
    new = storage.Day10Store(new_path)
    fresh = new.create("facts")
    assert fresh["revision"] == 0 and fresh["facts"] == []
    with pytest.raises(LabError, match="run_not_found"):
        new.load(run["run_id"], "facts")
    new.delete(run["run_id"], "facts")
    # Even if a wrong file is supplied, row identity cannot be reinterpreted as v3.
    wrong = storage.Day10Store(old_path)
    with pytest.raises(LabError, match="configuration_mismatch"):
        wrong.load(run["run_id"], "facts")
    wrong.close()
    new.close()
    with monkeypatch.context() as historical:
        historical.setattr(storage, "VERSION", historical_version)
        old = storage.Day10Store(old_path)
        assert old.load(run["run_id"], "facts") == old_state
        with pytest.raises(LabError, match="run_not_found"):
            old.load(fresh["run_id"], "facts")
        old.close()
        wrong = storage.Day10Store(new_path)
        with pytest.raises(LabError, match="configuration_mismatch"):
            wrong.load(fresh["run_id"], "facts")
        wrong.close()
    new = storage.Day10Store(new_path)
    assert new.load(fresh["run_id"], "facts") == fresh
    new.delete(fresh["run_id"], "facts"); new.close()
    assert old_path.read_bytes() == old_bytes
    assert len(fake.calls) == 6 and len(fake.counts) == 3  # No calls for namespace operations.


@pytest.mark.asyncio
@pytest.mark.parametrize("historical_version", HISTORICAL)
async def test_historical_request_rejected_by_v3_api_without_provider(lab, monkeypatch, historical_version):
    svc, fake = lab
    monkeypatch.setattr(app.state, "context_strategies", svc, raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        result = await client.post("/api/v1/context-strategies/facts/runs", json={"config_version":historical_version,"scenario_version":SCENARIO})
    assert result.status_code == 422
    assert svc.store.connection.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
    assert not fake.calls and not fake.counts
