"""Offline diagnostics through the ordinary Facts flow; never opens the live store."""
import copy
from dataclasses import replace
import json
from uuid import UUID

import pytest

from test_context_strategies import lab, request
from app.context_strategies_models import EXTRACTION_CONFIG
from app.context_strategies_scenario import FIXTURES
from app.fact_extractor import user_assertions


@pytest.mark.asyncio
@pytest.mark.parametrize("case,reason,index,public_error", [
    ("scope", "assertion_not_found", 0, "extraction_unsupported_change"),
    ("evidence", "evidence_mismatch", 0, "extraction_unsupported_change"),
    ("empty_evidence", "empty_evidence", 0, "extraction_unsupported_change"),
    ("type", "type_mismatch", 1, "extraction_unsupported_change"),
    ("bool_as_int", "type_mismatch", 1, "extraction_unsupported_change"),
    ("value", "value_mismatch", 0, "extraction_unsupported_change"),
    ("duplicate", "duplicate_identity", 2, "extraction_unsupported_change"),
    ("legacy_op", "invalid_schema", None, "extraction_invalid_output"),
    ("clear", "invalid_state", 0, "extraction_invalid_state"),
    ("json", "invalid_json", None, "extraction_invalid_output"),
    ("schema", "invalid_schema", None, "extraction_invalid_output"),
])
async def test_failed_extraction_diagnostic_and_unchanged_state(lab, caplog, case, reason, index, public_error):
    svc, fake = lab
    run = svc.store.create("facts")
    for step in range(1, 4):
        run = (await svc.send(run["run_id"], "facts", request(run, step)))["run"]
    before = svc.store.load(run["run_id"], "facts")
    assert not [r for r in caplog.records if hasattr(r, "facts_diagnostic")]
    changes = [dict(state="set", scope=scope, key=key, kind="preference", value=value, evidence=evidence)
               for (scope, key), (value, evidence) in user_assertions(FIXTURES[3]).items()]
    if case == "scope": changes[0]["scope"] = "A"
    if case == "evidence": changes[0]["evidence"] += " "
    if case == "empty_evidence": changes[0]["evidence"] = ""
    if case == "type": changes[1]["value"] = "true"
    if case == "bool_as_int": changes[1]["value"] = 1
    if case == "value": changes[0]["value"] = "different"
    if case == "duplicate": changes.append(copy.deepcopy(changes[0]))
    if case == "legacy_op": changes[1]["op"] = "replace"
    if case == "clear": changes[0]["state"] = "cleared"
    if case == "schema": changes[0]["kind"] = "invalid-kind"
    raw = "{invalid JSON" if case == "json" else json.dumps({"changes": changes}, ensure_ascii=False, indent=2)
    original = fake.complete

    async def invalid_reply(messages, config):
        assert config == EXTRACTION_CONFIG
        result = await original(messages, config)
        return replace(result, reply=raw)

    fake.complete = invalid_reply
    req = request(run, 4)
    outcome = await svc.send(run["run_id"], "facts", req)
    records = [r for r in caplog.records if hasattr(r, "facts_diagnostic")]
    assert len(records) == 1
    diagnostic = records[0].facts_diagnostic
    UUID(diagnostic["server_attempt_id"])
    assert diagnostic == {
        "run_id": run["run_id"], "client_attempt_id": req.attempt_id,
        "server_attempt_id": diagnostic["server_attempt_id"], "scenario_step": 4,
        "raw_reply": raw, "public_error": public_error, "reason": reason,
        "parsed_changes": changes if index is not None else None,
        "change_index": index,
        "scope": changes[index]["scope"] if index is not None else None,
        "key": changes[index]["key"] if index is not None else None,
    }
    log_message = records[0].getMessage()
    assert "\n" not in log_message  # Raw newlines are JSON-escaped, not injected log lines.
    assert json.loads(log_message.split(" ", 1)[1]) == diagnostic
    assert outcome["receipt"]["error"] == public_error
    assert outcome["receipt"]["extraction"]["usage"]["input_tokens"] == 10
    assert not outcome["receipt"]["response"]["attempted"]
    assert not outcome["receipt"]["committed"]
    assert svc.store.load(run["run_id"], "facts") == before
    assert svc.store.outputs(run["run_id"]) == []
    assert len(fake.calls) == 7 and len(fake.counts) == 3
    assert not svc.guard.active
    assert "raw_reply" not in json.dumps(outcome) and "parsed_changes" not in json.dumps(outcome)
    assert json.loads(fake.calls[-1][0][0].content) == {
        "current_user": FIXTURES[3],
    }


@pytest.mark.asyncio
async def test_legacy_add_is_rejected_without_recovery(lab, caplog):
    svc, fake = lab
    run = svc.store.create("facts")
    for step in range(1, 5):
        run = (await svc.send(run["run_id"], "facts", request(run, step)))["run"]
    before = svc.store.load(run["run_id"], "facts")
    original = fake.complete

    async def invalid_add(messages, config):
        result = await original(messages, config)
        patch = json.loads(result.reply)
        patch["changes"][0]["op"] = "add"  # Turn 5 changes an existing deadline.
        return replace(result, reply=json.dumps(patch))

    fake.complete = invalid_add
    outcome = await svc.send(run["run_id"], "facts", request(run, 5))
    diagnostic, = [r.facts_diagnostic for r in caplog.records if hasattr(r, "facts_diagnostic")]
    assert (diagnostic["reason"], diagnostic["change_index"], diagnostic["key"]) == ("invalid_schema", None, None)
    assert outcome["receipt"]["error"] == "extraction_invalid_output"
    assert svc.store.load(run["run_id"], "facts") == before
