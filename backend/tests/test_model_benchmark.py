import asyncio
import copy
import json
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError, BadRequestError

from app.main import app
from app.model_benchmark_api import get_model_benchmark_service
from app.model_benchmark_domain import (
    b_has_following_c, benchmark_schema, common_parameters, feasible, payload_fingerprint,
    reference_answers, schedule_valid, trace_array, valid_counting_string,
)
from app.model_benchmark_models import BenchmarkRunRequest, BenchmarkUsage, TokenRates
from app.model_benchmark_pricing import MODEL_REGISTRY, ROLE_DEFAULTS, calculate_cost
from app.model_benchmark_service import ModelBenchmarkService, catalog, normalize_response

MODELS = list(MODEL_REGISTRY)
SELECTIONS = {role: value[1] for role, value in ROLE_DEFAULTS.items()}


def response(answer=None, status="completed", **overrides):
    value = SimpleNamespace(
        output_text=json.dumps(reference_answers() if answer is None else answer), status=status,
        model=MODELS[0], service_tier="default", output=[],
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        usage=SimpleNamespace(
            input_tokens=953, output_tokens=5800, total_tokens=6753,
            input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            output_tokens_details=SimpleNamespace(reasoning_tokens=5691),
        ),
    )
    for key, val in overrides.items():
        setattr(value, key, val)
    return value


def normalized(value):
    return normalize_response(value, role="economical", model_id=MODELS[0], latency_ms=12)


def service_with(create):
    @asynccontextmanager
    async def factory():
        yield SimpleNamespace(responses=SimpleNamespace(create=create))
    return ModelBenchmarkService(factory)


def test_canonical_payload_and_schema():
    assert payload_fingerprint() == "01914c54838704723619457331e4d787299a23d010fdb23b1e66f725947d755c"
    payload = common_parameters()
    assert payload["reasoning"] == {"effort": "medium"}
    assert payload["max_output_tokens"] == 6000
    assert not {"temperature", "top_p", "tools", "prompt_cache_options", "previous_response_id"} & payload.keys()
    def check(node):
        assert not {"const", "enum", "minimum", "maximum"} & node.keys()
        if node["type"] == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for child in node["properties"].values():
                check(child)
        elif node["type"] == "array":
            check(node["items"])
    check(benchmark_schema())


def test_independent_references_are_not_mutable_shared_results():
    ref = reference_answers()
    assert ref == {
        "task1": {"database_queries": 468},
        "task2": dict(zip(("monday", "tuesday", "wednesday", "thursday"), ("Анна", "Глеб", "Вера", "Борис"))),
        "task3": {"selected_features": ["A", "C", "F", "G"], "total_cost": 15, "total_value": 29},
        "task4": {"final_array": [22, 15, -10, -10, 11, 18, -28, -12], "checksum": -147},
        "task5": {"count": 24},
    }
    ref["task4"]["final_array"][0] = 0
    assert reference_answers()["task4"] == trace_array()
    assert not schedule_valid(("Анна", "Анна", "Вера", "Борис"))


@pytest.mark.parametrize("selected", [set("BE"), set("C"), set("AD"), set("GH"), set("ABFH"), {"X"}])
def test_feature_constraints(selected):
    assert not feasible(selected)


@pytest.mark.parametrize("text,expected", [("B", False), ("AB", False), ("ABA", False), ("BC", True), ("BAC", True), ("BAAC", False)])
def test_following_c_boundary(text, expected):
    assert b_has_following_c(text) is expected


def test_counting_constraints():
    assert valid_counting_string("ABACABCBAC")
    assert not valid_counting_string("ABACABCBAB")
    assert not valid_counting_string("CBACABCBAC")


def test_quality_and_actual_reference():
    answer = reference_answers()
    answer["task3"]["selected_features"].reverse()
    assert normalized(response(answer)).quality.correct_count == 5
    answer["task5"]["count"] = 21
    result = normalized(response(answer))
    assert result.quality.correct_count == 4
    assert result.tasks[4].actual_answer == {"count": 21}
    assert result.tasks[4].reference_answer == {"count": 24}
    assert all(task.reference_answer is None for task in result.tasks[:4])


@pytest.mark.parametrize("task,field,value", [
    ("task3", "selected_features", ["A", "C", "F", "G", "G"]),
    ("task3", "selected_features", ["X"]),
    ("task3", "total_cost", 14), ("task3", "total_value", 30),
    ("task4", "checksum", 0), ("task4", "final_array", [0]),
])
def test_wrong_answer_is_incorrect(task, field, value):
    answer = reference_answers()
    answer[task][field] = value
    result = normalized(response(answer))
    assert result.quality.correct_count == 4
    assert next(t for t in result.tasks if t.task_id == task).verdict == "incorrect"


def test_zero_quality_is_distinct_from_unverified():
    answer = reference_answers()
    answer["task1"]["database_queries"] = 0
    answer["task2"]["monday"] = "Борис"
    answer["task3"]["total_value"] = 0
    answer["task4"]["checksum"] = 0
    answer["task5"]["count"] = 0
    assert normalized(response(answer)).quality.correct_count == 0
    result = normalized(response(status="incomplete"))
    assert result.quality is None and result.reason == "max_output_tokens"
    assert result.cost.amount_usd == "0.0071506"
    assert all(t.verdict == "unverified" for t in result.tasks)


@pytest.mark.parametrize("value", [True, "468", 468.0])
def test_strict_integers(value):
    answer = reference_answers()
    answer["task1"]["database_queries"] = value
    assert normalized(response(answer)).quality is None


@pytest.mark.parametrize("changes,status", [
    ({"output_text": "{broken"}, "invalid_response"),
    ({"output_text": "{}"}, "invalid_response"),
    ({"output": [{"content": [{"type": "refusal"}]}]}, "refused"),
    ({"status": "failed"}, "api_error"),
])
def test_unverified_status(changes, status):
    result = normalized(response(**changes))
    assert result.status == status and result.quality is None
    assert all(t.verdict == "unverified" for t in result.tasks)


def test_nullable_usage_and_unknown_resolution():
    result = normalized(response(usage=None, model="unknown"))
    assert result.quality.correct_count == 5
    assert all(v is None for v in result.usage.model_dump().values())
    assert result.cost.amount_usd is None


def test_pricing_with_cache_and_no_double_counted_reasoning():
    usage = BenchmarkUsage(input_tokens=1000, cached_input_tokens=200, cache_write_tokens=100, output_tokens=500, reasoning_tokens=499)
    assert calculate_cost(usage, MODELS[0], "default").amount_usd == "0.000769"
    for model, output, expected in zip(MODELS, (5800, 3215, 5511), ("0.0071506", "0.040486", "0.114032")):
        usage = BenchmarkUsage(input_tokens=953, cached_input_tokens=0, cache_write_tokens=0, output_tokens=output)
        assert calculate_cost(usage, model, "default").amount_usd == expected


@pytest.mark.parametrize("patch_usage,model,tier", [
    ({"cache_write_tokens": None}, MODELS[0], "default"),
    ({"cached_input_tokens": 1000, "cache_write_tokens": 100}, MODELS[0], "default"),
    ({"input_tokens": 300000}, MODELS[0], "default"),
    ({}, "unknown", "default"), ({}, MODELS[0], "fast"),
])
def test_price_unavailable(patch_usage, model, tier):
    usage = BenchmarkUsage(input_tokens=953, cached_input_tokens=0, cache_write_tokens=0, output_tokens=100)
    result = calculate_cost(usage.model_copy(update=patch_usage), model, tier)
    assert result.status == "unavailable" and result.amount_usd is None and result.reason


@pytest.mark.asyncio
async def test_calls_are_concurrent_equal_and_stable():
    active = 0
    peak = 0
    async def create(**kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return response(model=kwargs["model"])
    create_mock = AsyncMock(side_effect=create)
    result = await service_with(create_mock).run(BenchmarkRunRequest(models=SELECTIONS), "test")
    assert peak == 3 and create_mock.call_count == 3 and result.api_call_count == 3
    assert [r.role for r in result.results] == list(ROLE_DEFAULTS)
    payloads = [copy.deepcopy(c.kwargs) for c in create_mock.call_args_list]
    assert [p.pop("model") for p in payloads] == MODELS
    assert payloads[0] == payloads[1] == payloads[2] == common_parameters()


@pytest.mark.asyncio
async def test_factory_uses_zero_retries_and_explicit_timeout():
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.responses.create.return_value = response()
    with patch("app.model_benchmark_service.AsyncOpenAI", return_value=client) as constructor:
        await ModelBenchmarkService().run(BenchmarkRunRequest(models=SELECTIONS), "test")
    assert constructor.call_count == 3
    assert all(call.kwargs["max_retries"] == 0 for call in constructor.call_args_list)
    assert constructor.call_args.kwargs["timeout"].read == 240
    assert constructor.call_args.kwargs["timeout"].connect == 15


@pytest.mark.asyncio
@pytest.mark.parametrize("exception,expected", [
    (APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses")), "timeout"),
    (BadRequestError("sensitive-marker", response=httpx.Response(400, request=httpx.Request("POST", "https://api.openai.com/v1/responses")), body=None), "api_error"),
    (RuntimeError("sensitive-marker"), "internal_error"),
])
async def test_one_failure_does_not_destroy_other_slots(exception, expected, caplog):
    create = AsyncMock(side_effect=[exception, response(), response(status="incomplete")])
    result = await service_with(create).run(BenchmarkRunRequest(models=SELECTIONS), "test")
    assert [r.status for r in result.results] == [expected, "completed", "incomplete"]
    assert result.results[0].quality is None and result.results[1].quality.correct_count == 5
    assert result.api_call_count == 3 and create.call_count == 3
    assert "sensitive-marker" not in result.model_dump_json() + caplog.text


@pytest.mark.asyncio
async def test_wall_clock_timeout_and_pre_call_failure():
    async def delayed(**kwargs):
        await asyncio.sleep(10)
    create = AsyncMock(side_effect=delayed)
    with patch("app.model_benchmark_service.OPENAI_TIMEOUT_SECONDS", 0.01):
        result = await service_with(create).run(BenchmarkRunRequest(models=SELECTIONS), "test")
    assert all(r.status == "timeout" and r.api_call_count == 1 for r in result.results)
    def broken_factory():
        raise RuntimeError("sensitive-marker")
    result = await ModelBenchmarkService(broken_factory).run(BenchmarkRunRequest(models=SELECTIONS), "test")
    assert result.api_call_count == 0


def test_catalog_and_run_routes(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)
    assert client.get("/api/v1/model-benchmark/catalog").json()["roles"][0]["default_model_id"] == MODELS[0]
    create = AsyncMock(side_effect=[response(), response(status="incomplete"), response()])
    app.dependency_overrides[get_model_benchmark_service] = lambda: service_with(create)
    try:
        for invalid in ({}, {"models": {"economical": MODELS[0]}}, {"models": {**SELECTIONS, "flagship": "unknown"}}, {"models": SELECTIONS, "prompt": "different"}):
            assert client.post("/api/v1/model-benchmark/run", json=invalid).status_code == 422
        assert create.call_count == 0
        r = client.post("/api/v1/model-benchmark/run", json={"models": {k: MODELS[0] for k in SELECTIONS}})
        assert r.status_code == 200 and r.json()["api_call_count"] == 3
        assert r.headers["X-Request-ID"] == r.json()["request_id"]
        assert r.json()["results"][1]["quality"] is None
        assert create.call_count == 3
    finally:
        app.dependency_overrides.clear()


def test_invalid_registry_is_not_published(monkeypatch):
    monkeypatch.setitem(MODEL_REGISTRY, MODELS[0], replace(MODEL_REGISTRY[MODELS[0]], rates=TokenRates(input="NaN", cached_input="0", cache_write="0", output="1")))
    client = TestClient(app)
    assert client.get("/api/v1/model-benchmark/catalog").status_code == 503
    assert client.post("/api/v1/model-benchmark/run", json={"models": SELECTIONS}).status_code == 503
