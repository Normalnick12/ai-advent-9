import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mcp_composition_api import router
from app.mcp_composition_models import CompositionRequest
from app.mcp_composition_service import CompositionService, TOOLS

TOKEN = "synthetic-day19-secret-sentinel-123456789"
URL = "https://day19.example.org/mcp"


class Fake:
    def __init__(self, response=None, error=None):
        self.responses = self
        self.calls = []
        self.response, self.error = response, error

    async def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.error: raise self.error
        return self.response


def service(tmp_path, fake, **kwargs):
    return CompositionService(fake, url=URL, token=TOKEN, budget=8000, deadline=120, evidence_dir=tmp_path, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,count", [("completed", 0), ("completed", 3), ("completed", 4), ("incomplete", 2), ("failed", 1)])
async def test_one_native_attempt_preserves_every_item(tmp_path, status, count):
    items = [dict(type="mcp_list_tools", id="list", tools=[])] + [dict(type="mcp_call", id=str(i), server_label="dependency_composition",
        name=TOOLS[i % 3], arguments='{"unmodified":"value"}', output='{"unmodified":true}', error=None) for i in range(count)]
    items.append(dict(type="message", content=[dict(type="output_text", text="raw final")]))
    raw = dict(id="resp_fixture", model="resolved-fixture", status=status, output=items)
    fake = Fake(raw)
    result = await service(tmp_path, fake).run(CompositionRequest(prompt="do requested work"))
    assert len(fake.calls) == 1
    config = fake.calls[0]
    assert config["tool_choice"] == "auto" and config["model"] == "gpt-5.6" and config["store"] is False
    assert config["reasoning"] == {"effort": "none"}
    assert len(config["tools"]) == 1
    assert config["tools"][0] == dict(type="mcp", server_label="dependency_composition", server_url=URL,
        authorization=TOKEN, allowed_tools=TOOLS, require_approval="never")
    folder = Path(result.evidence_path)
    assert json.loads((folder / "response.json").read_text()) == raw
    record = json.loads((folder / "operation.json").read_text())
    assert len(record["calls"]) == count and record["final_text"] == "raw final"
    assert result.evidence_saved
    assert TOKEN not in "".join(f.read_text() for f in folder.iterdir())
    assert json.loads((folder / "attempt.json").read_text())["max_retries"] == 0


@pytest.mark.asyncio
async def test_error_refusal_and_secret_redaction(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "api-secret-sentinel")
    raw = dict(status="completed", output=[dict(type="mcp_call", id="failed", error=TOKEN, arguments="{}"),
        dict(type="message", content=[dict(type="refusal", refusal="api-secret-sentinel")])])
    result = await service(tmp_path, Fake(raw)).run(CompositionRequest(prompt="test"))
    text = (Path(result.evidence_path) / "response.json").read_text()
    assert TOKEN not in text and "api-secret-sentinel" not in text and "failed" in text
    assert result.final_text is None


@pytest.mark.asyncio
async def test_timeout_unknown_no_retry(tmp_path):
    fake = Fake(error=TimeoutError())
    result = await service(tmp_path, fake).run(CompositionRequest(prompt="test"))
    assert len(fake.calls) == 1 and result.invocation == "unknown" and result.evidence_saved
    assert (Path(result.evidence_path) / "error.json").exists()


@pytest.mark.asyncio
async def test_storage_failure_not_sent(tmp_path):
    target = tmp_path / "file"
    target.write_text("not a directory")
    fake = Fake()
    result = await service(target, fake).run(CompositionRequest(prompt="test"))
    assert result.invocation == "not_sent" and not fake.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("key,value", [("url", "http://localhost/mcp"), ("token", ""), ("budget", True), ("deadline", 0)])
async def test_configuration_not_sent(tmp_path, key, value):
    fake = Fake()
    svc = service(tmp_path, fake)
    setattr(svc, key, value)
    result = await svc.run(CompositionRequest(prompt="test"))
    assert result.invocation == "not_sent" and result.outcome == "configuration_error" and not fake.calls


def test_route_validation_and_sdk_configuration(tmp_path, monkeypatch):
    from app import mcp_composition_service as module
    configs = []
    fake = Fake(dict(status="completed", output=[]))
    def constructor(**kw):
        configs.append(kw)
        return fake
    monkeypatch.setattr(module, "AsyncOpenAI", constructor)
    app = FastAPI()
    app.state.mcp_composition = service(tmp_path, None)
    app.include_router(router)
    with TestClient(app) as client:
        assert client.post("/api/v1/mcp-composition/run", json={"prompt": " "}).status_code == 422
        assert client.post("/api/v1/mcp-composition/run", json={"prompt": "x", "path": "x"}).status_code == 422
        assert client.post("/api/v1/mcp-composition/run", json={"prompt": "x"}).status_code == 200
    assert configs[0]["max_retries"] == 0
    assert len(fake.calls) == 1
