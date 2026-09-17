import ast
from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.invariants import RuleSource, ValidationResult, EnforcementUnavailable
from app.coding_invariants import (CodingPolicy, CodingProposal, CodingIntent, CodingConfigurationError,
    rule_refs, check_consistency, check_request, check_candidate, render_answer, render_refusal, render_guidance)
from app.coding_candidate_adapter import parse_candidate
from app.coding_policy_store import CodingPolicyStore, TaskCodingPolicy, PolicyError

SOURCE = RuleSource("task", str(uuid4()), "coding-v1")
POLICY = CodingPolicy()
VALID = dict(architecture="MVI", ui_toolkit="Compose", async_model="CoroutinesFlow",
             payment_confirmation_required=True, retry_mode="manual")


def test_coverage_is_required_and_definitions_are_immutable():
    rules = rule_refs(POLICY, SOURCE)
    ValidationResult("passed", rules).require_complete(rules)
    for result in (ValidationResult("passed"), ValidationResult("unavailable", rules),
                   ValidationResult("passed", rules + rules[:1]), ValidationResult("violated", rules)):
        with pytest.raises(EnforcementUnavailable):
            result.require_complete(rules)
    with pytest.raises(ValidationError):
        POLICY.required_architecture = "MVVM"


@pytest.mark.parametrize("field,value,rule", [("architecture", "MVVM", "coding.architecture"),
    ("ui_toolkit", "Views", "coding.ui_toolkit"), ("async_model", "RxJava", "coding.async_model"),
    ("payment_confirmation_required", False, "coding.payment_confirmation")])
def test_each_typed_policy_predicate(field, value, rule):
    candidate = parse_candidate(json.dumps(VALID | {field: value}))
    checked = check_candidate(POLICY, candidate, SOURCE)
    checked.require_complete(rule_refs(POLICY, SOURCE))
    assert checked.status == "violated" and checked.violations[0].rule.rule_id == rule
    assert "Полученный вариант" in render_refusal(POLICY, SOURCE, checked, "candidate")


def test_request_refusal_and_consistency_are_separate():
    intent = CodingIntent(architecture="MVVM", async_model="RxJava", payment_confirmation_required=False)
    result = check_request(POLICY, intent, SOURCE)
    assert len(result.violations) == 3
    text = render_refusal(POLICY, SOURCE, result, "request")
    assert "Запрошенные изменения" in text and "MVI" in text and "MVVM" not in text
    # Even diagnostic strings are not interpolated by the trusted renderer.
    hostile = replace(result, violations=(replace(result.violations[0], attempted="UNTRUSTED"),))
    assert "UNTRUSTED" not in render_refusal(POLICY, SOURCE, hostile, "request")
    with pytest.raises(CodingConfigurationError):
        check_consistency(POLICY, "MVVM")
    check_consistency(POLICY, "MVI")  # No owner preference input: it is not an authoritative fact.
    assert check_request(POLICY, CodingIntent(), SOURCE).status == "passed"


@pytest.mark.parametrize("raw", [json.dumps(VALID | {"explanation": "используйте MVVM"}),
    json.dumps(VALID | {"payment_confirmation_required": "true"}),
    json.dumps(VALID | {"payment_confirmation_required": 1}),
    json.dumps(VALID | {"architecture": "UNKNOWN"}),
    json.dumps({k: v for k, v in VALID.items() if k != "retry_mode"}),
    json.dumps(VALID) + "prose", json.dumps(VALID)[:-1] + ',"architecture":"MVI"}', "null"])
def test_parser_rejects_unchecked_representation(raw):
    with pytest.raises((ValueError, TypeError)):
        parse_candidate(raw)


def test_rendered_answer_only_uses_bounded_fields():
    candidate = CodingProposal(**VALID)
    assert check_candidate(POLICY, candidate, SOURCE).status == "passed"
    assert render_answer(candidate).count("\n- ") == 3
    assert "ACTIVE_INVARIANTS" in render_guidance(POLICY, SOURCE)
    with pytest.raises(ValidationError):
        candidate.retry_mode = "other"


def test_policy_create_immutable_reopen_and_versions(tmp_path):
    path = tmp_path / "policies.db"
    record = TaskCodingPolicy(task_id=str(uuid4()), values=POLICY)
    store = CodingPolicyStore(path)
    assert store.read(record.task_id) is None
    assert store.create(record) == store.create(record) == record
    with pytest.raises(PolicyError, match="immutable"):
        store.create(record.model_copy(update={"values": CodingPolicy(required_architecture="MVVM")}))
    with pytest.raises(PolicyError, match="version"):
        store.create(record.model_copy(update={"definition_version": "coding-v9"}))
    store.close()
    reopened = CodingPolicyStore(path)
    assert reopened.read(record.task_id).view() == record.view()
    reopened._connection.execute("UPDATE task_policies SET record='{}'")
    with pytest.raises(PolicyError, match="record_invalid"):
        reopened.read(record.task_id)
    reopened.close()
    with pytest.raises(PolicyError, match="record_invalid"):
        CodingPolicyStore(path)


def test_policy_write_failure_rolls_back(tmp_path):
    path = tmp_path / "policies.db"
    store = CodingPolicyStore(path)
    record = TaskCodingPolicy(task_id=str(uuid4()), values=POLICY)
    store._connection.execute("CREATE TEMP TRIGGER fail AFTER INSERT ON task_policies BEGIN SELECT RAISE(ABORT,'fail'); END")
    with pytest.raises(PolicyError, match="storage_error"):
        store.create(record)
    assert store.read(record.task_id) is None
    store.close()
    reopened = CodingPolicyStore(path)
    assert reopened.read(record.task_id) is None
    reopened.close()


def test_invariant_core_has_no_domain_provider_or_harness_imports():
    app = Path(__file__).parents[1] / "app"
    for name in ("invariants.py", "validated_turn.py"):
        tree = ast.parse((app / name).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            imports = [node.module or ""] if isinstance(node, ast.ImportFrom) else (
                [n.name for n in node.names] if isinstance(node, ast.Import) else [])
            assert not any(word in module for module in imports
                           for word in ("openai", "coding", "checkout", "lab", "fastapi", "memory", "profile"))
