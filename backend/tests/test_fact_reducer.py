"""Facts v3: semantic truth before deterministic mutation, no live provider."""
import copy
import json
from dataclasses import replace

import pytest

from app import fact_extractor as extraction
from app import context_strategies_store as storage
from app.context_strategies_models import EXTRACTION_CONFIG, LabError, Patch
from app.context_strategies_scenario import FIXTURES
from app.openai_agent_payload import generation_payload
from app.llm_client import ConversationMessage
from test_context_strategies import lab, request


def change(key="payment", value="link", scope="B", state="set", kind="decision", evidence=None):
    literal = "cleared" if state == "cleared" else "true" if value is True else "false" if value is False else str(value)
    return dict(scope=scope, key=key, kind=kind, state=state, value=value,
                evidence=evidence if evidence is not None else f"{key}={literal}")


def current(*changes):
    return f"Область требований: {changes[0]['scope']}.\n" + "\n".join(c["evidence"] for c in changes)


def apply(previous, *changes, user_id="new-source", text=None):
    return extraction.apply_patch(previous, json.dumps({"changes": changes}), text or current(*changes), user_id)


def test_new_b_identity_ignores_a_and_updates_do_not_mutate_input():
    a = apply([], change(scope="A", value="on_site"), user_id="a-source")
    before = copy.deepcopy(a)
    combined = apply(a, change())
    assert a == before and combined[0] == a[0]
    assert combined[1]["scope"] == "B" and combined[1]["value"] == "link"
    assert combined[1]["user_id"] == "new-source"
    updated = apply(combined, change(value="cash"), user_id="correction")
    assert updated[1]["value"] == "cash" and updated[1]["user_id"] == "correction"
    assert combined[1]["value"] == "link"


def test_same_value_noop_preserves_kind_evidence_and_provenance():
    old = apply([], change(kind="decision"), user_id="first-confirmed")
    repeated = apply(old, change(kind="other"), user_id="second-confirmed")
    assert repeated == old


def test_typed_equality_does_not_confuse_boolean_and_integer():
    old = apply([], change(value=True))
    updated = apply(old, change(value=1), user_id="integer-source")
    assert type(updated[0]["value"]) is int and updated[0]["user_id"] == "integer-source"


def test_clear_repeat_clear_and_reactivation():
    old = apply([], change(), user_id="set-source")
    cleared = apply(old, change(value=None, state="cleared"), user_id="clear-source")
    assert cleared[0]["state"] == "cleared" and cleared[0]["value"] is None
    assert apply(cleared, change(value=None, state="cleared", kind="other")) == cleared
    reactivated = apply(cleared, change(value="cash"), user_id="reactivation")
    assert reactivated[0]["state"] == "set" and reactivated[0]["value"] == "cash"
    assert reactivated[0]["user_id"] == "reactivation"


def test_unknown_clear_discards_earlier_candidate_changes():
    previous = apply([], change(scope="A", value="on_site"))
    before = copy.deepcopy(previous)
    with pytest.raises(extraction.ExtractionValidationError) as error:
        apply(previous, change(), change(key="confirmation", value=None, state="cleared"))
    assert error.value.code == "extraction_clear_missing"
    assert error.value.diagnostic["reason"] == "clear_missing"
    assert error.value.diagnostic["change_index"] == 1
    assert previous == before


@pytest.mark.parametrize("field,value,reason", [
    ("key", "other_key", "assertion_not_found"),
    ("scope", "A", "assertion_not_found"),
    ("value", "cash", "value_mismatch"),
    ("value", True, "type_mismatch"),
    ("evidence", "confirmation=admin", "evidence_mismatch"),
    ("state", "cleared", "invalid_state"),
])
def test_whole_semantic_validation_before_reducer(monkeypatch, field, value, reason):
    good = change(key="confirmation", value="admin")
    invalid = change(); invalid[field] = value
    def unexpected(*args):
        pytest.fail("Reducer called before whole semantic patch validation")
    monkeypatch.setattr(extraction, "reduce_facts", unexpected)
    with pytest.raises(extraction.ExtractionValidationError) as error:
        apply([], good, invalid, text=current(good, change()))
    assert error.value.diagnostic["reason"] == reason
    assert error.value.diagnostic["change_index"] == 1


def test_duplicate_semantic_identity_rejected_before_reducer(monkeypatch):
    monkeypatch.setattr(extraction, "reduce_facts", lambda *args: pytest.fail("Unexpected reducer"))
    with pytest.raises(extraction.ExtractionValidationError) as error:
        apply([], change(), change(), text=current(change()))
    assert error.value.diagnostic["reason"] == "duplicate_identity"


def test_null_set_and_unconfirmed_clear_are_invalid():
    for invalid, text in [(change(value=None), current(change(value=None, state="cleared"))),
                          (change(value=None, state="cleared"), current(change()))]:
        with pytest.raises(LabError): apply([], invalid, text=text)


def test_strict_output_schema_is_opt_in_semantic_contract():
    fmt = EXTRACTION_CONFIG.text_format
    assert fmt == {"type":"json_schema", "name":"facts-v2", "strict":True, "schema":Patch.model_json_schema()}
    root = fmt["schema"]; item = root["$defs"]["Change"]
    assert root["additionalProperties"] is False and root["required"] == ["changes"]
    fields = {"scope", "key", "kind", "state", "value", "evidence"}
    assert set(item["properties"]) == fields and set(item["required"]) == fields
    assert item["additionalProperties"] is False
    assert item["properties"]["state"]["enum"] == ["set", "cleared"]
    assert {v["type"] for v in item["properties"]["value"]["anyOf"]} == {"string","integer","boolean","null"}
    payload = generation_payload((ConversationMessage("user", '{"current_user":"exact"}'),), EXTRACTION_CONFIG)
    assert payload["text"]["format"] == fmt and payload["store"] is False


@pytest.mark.parametrize("missing", ["scope","key","kind","state","value","evidence"])
def test_every_semantic_field_is_required(missing):
    incomplete = change(); incomplete.pop(missing)
    with pytest.raises(LabError, match="extraction_invalid_output"):
        apply([], incomplete, text=current(change()))


@pytest.mark.asyncio
async def test_reducer_failure_prevents_response_and_preserves_confirmed_state(lab, caplog):
    svc, fake = lab; run = svc.store.create("facts")
    original = fake.complete
    async def omit_reminders(messages, config):
        result = await original(messages, config)
        if config == EXTRACTION_CONFIG and json.loads(messages[0].content)["current_user"] == FIXTURES[3]:
            patch = json.loads(result.reply)
            patch["changes"] = [c for c in patch["changes"] if c["key"] != "email_reminders"]
            return replace(result, reply=json.dumps(patch))
        return result
    fake.complete = omit_reminders
    for step in range(1, 6): run = (await svc.send(run["run_id"],"facts",request(run,step)))["run"]
    before = svc.store.load(run["run_id"],"facts")
    result = await svc.send(run["run_id"],"facts",request(run,6))
    assert result["receipt"]["error"] == "extraction_clear_missing"
    assert result["receipt"]["extraction"]["usage"]["input_tokens"] == 10
    assert not result["receipt"]["response"]["attempted"]
    assert svc.store.load(run["run_id"],"facts") == before
    diagnostic, = [r.facts_diagnostic for r in caplog.records if hasattr(r,"facts_diagnostic")]
    assert (diagnostic["reason"],diagnostic["change_index"],diagnostic["key"]) == ("clear_missing",1,"email_reminders")
    assert len(fake.calls) == 11 and len(fake.counts) == 5


@pytest.mark.asyncio
async def test_noop_pair_commits_without_rewriting_fact_provenance(lab, monkeypatch):
    svc, fake = lab; run = svc.store.create("facts")
    # A test-only repeated fixture exercises the ordinary no-op commit path.
    monkeypatch.setattr(storage, "FIXTURES", (FIXTURES[0], FIXTURES[0], *FIXTURES[2:]))
    run = (await svc.send(run["run_id"],"facts",request(run,1)))["run"]
    old = copy.deepcopy(run["facts"])
    req = request(run,2); req.message = FIXTURES[0]
    outcome = await svc.send(run["run_id"],"facts",req)
    assert outcome["receipt"]["committed"] and outcome["run"]["revision"] == 2
    assert outcome["run"]["facts"] == old and len(outcome["run"]["steps"]) == 2
    assert len(fake.calls) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("response_fails", [False, True])
async def test_candidate_context_and_correction_commit_or_rollback(lab, response_fails):
    svc, fake = lab; run = svc.store.create("facts")
    for step in range(1,5): run = (await svc.send(run["run_id"],"facts",request(run,step)))["run"]
    before = svc.store.load(run["run_id"],"facts")
    if response_fails: fake.failure = None
    outcome = await svc.send(run["run_id"],"facts",request(run,5))
    messages, _ = fake.calls[-1]
    candidate = json.loads(messages[0].content.split("\n",1)[1])
    assert next(f for f in candidate if f["key"] == "deadline_weeks")["value"] == 6
    assert next(f for f in candidate if f["key"] == "auth")["value"] == "magic_link"
    assert [m.content for m in messages[1:-1]] == [m["content"] for m in before["messages"][-6:]]
    assert messages[-1].content == FIXTURES[4]
    after = svc.store.load(run["run_id"],"facts")
    if response_fails: assert after == before and not outcome["receipt"]["committed"]
    else:
        assert after["revision"] == 5 and len(after["messages"]) == 10
        assert extraction.semantic_facts(after["facts"]) == candidate
        path = svc.store.connection.execute("PRAGMA database_list").fetchone()[2]
        reopened = storage.Day10Store(__import__("pathlib").Path(path))
        try: assert reopened.load(run["run_id"],"facts") == after
        finally: reopened.close()
