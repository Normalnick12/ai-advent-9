"""Offline request/evidence tests: injected SDK only, no network."""
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import mcp_orchestration_service as module
from app.mcp_orchestration_api import router
from app.mcp_orchestration_models import OrchestrationRequest

TOKEN = "synthetic-day20-secret-sentinel-123456789"
SETTINGS = module.Settings("https://day19.example.org/mcp", TOKEN)


class Stream:
    def __init__(self, events, error=None):
        self.events, self.error = events, error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def __aiter__(self):
        for event in self.events:
            yield event
        if self.error:
            raise self.error


class Fake:
    def __init__(self, events=(), error=None):
        self.responses, self.calls = self, []
        self.events, self.error = events, error

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return Stream(self.events, self.error)

    async def close(self):
        pass


def completed():
    item = dict(id="r1", type="mcp_call", server_label="deepwiki", name="ask_wiki_question",
                arguments='{"repoName":"android/nowinandroid","question":"dependencies"}',
                output="observed " + TOKEN, status="completed")
    response = dict(id="resp_fake", status="completed", output=[item,
        dict(type="message", content=[dict(type="output_text", text='{"branches":[]}')])])
    return [dict(type="response.mcp_call.in_progress", item_id="r1"),
            dict(type="response.output_item.done", item=item),
            dict(type="response.completed", response=response)]


@pytest.mark.asyncio
async def test_one_request_both_servers_and_evidence(tmp_path, monkeypatch):
    fake = Fake(completed())
    constructor = []
    def make(**kwargs):
        constructor.append(kwargs)
        return fake
    monkeypatch.setattr(module, "AsyncOpenAI", make)
    service = module.OrchestrationService(settings=SETTINGS, evidence_dir=tmp_path)
    result = await service.run(OrchestrationRequest(prompt=module.PROMPT))
    assert len(fake.calls) == 1 and constructor[0]["max_retries"] == 0
    request = fake.calls[0]
    assert request["tool_choice"] == "auto" and request["stream"] and not request["store"]
    assert request["model"] == "gpt-5.6" and request["reasoning"] == {"effort": "none"}
    assert request["max_output_tokens"] == 32768 and SETTINGS.deadline == 900
    servers = request["tools"]
    assert [s["server_label"] for s in servers] == ["deepwiki", "dependency_composition"]
    assert [s["server_url"] for s in servers] == [module.DEEPWIKI, SETTINGS.url]
    assert servers[1]["authorization"] == TOKEN and "authorization" not in servers[0]
    prompt = request["input"] + request["instructions"]
    for forbidden in [*module.RESEARCH_TOOLS, *module.DEPENDENCY_TOOLS, "save", "Context7",
                      "androidx.room", "androidx.work", "Room", "WorkManager", TOKEN, "lookup →"]:
        assert forbidden not in prompt
    assert servers[1]["allowed_tools"] == module.DEPENDENCY_TOOLS
    assert all(s["require_approval"] == "never" for s in servers)
    folder = Path(result.evidence_path)
    assert result.outcome == "response_received" and result.invocation == "observed"
    for path in folder.iterdir():
        assert TOKEN not in path.read_text(encoding="utf-8")
    assert len((folder / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 3
    assert json.loads((folder / "response.json").read_text(encoding="utf-8"))["id"] == "resp_fake"
    assert (folder / "model-answer.txt").read_text(encoding="utf-8") == result.final_text
    assert json.loads((folder / "attempt.json").read_text(encoding="utf-8"))["max_retries"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), httpx.ReadError("secret not to log")])
async def test_interruption_retains_prefix_no_retry(tmp_path, error):
    fake = Fake(completed()[:2], error)
    result = await module.OrchestrationService(fake, settings=SETTINGS, evidence_dir=tmp_path).run(
        OrchestrationRequest(prompt=module.PROMPT))
    assert result.outcome == "evidence_incomplete" and len(fake.calls) == 1
    folder = Path(result.evidence_path)
    assert len((folder / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert not (folder / "response.json").exists()
    assert result.invocation == "observed"


@pytest.mark.asyncio
async def test_existing_attempt_not_overwritten_or_dispatched(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "uuid4", lambda: "collision")
    folder = tmp_path / "collision"
    folder.mkdir()
    (folder / "keep").write_text("original")
    fake = Fake()
    result = await module.OrchestrationService(fake, settings=SETTINGS, evidence_dir=tmp_path).run(
        OrchestrationRequest(prompt="task"))
    assert result.outcome == "evidence_storage_error" and not fake.calls
    assert list(folder.iterdir()) == [folder / "keep"] and (folder / "keep").read_text(encoding="utf-8") == "original"


def test_api_fake_and_unconfigured_startup(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    fake = Fake(completed())
    app.state.mcp_orchestration = module.OrchestrationService(fake, settings=SETTINGS, evidence_dir=tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/v1/mcp-orchestration/run", json={"prompt": module.PROMPT})
        assert response.status_code == 200 and response.json()["invocation"] == "observed"
        assert client.post("/api/v1/mcp-orchestration/run", json={"prompt": " "}).status_code == 422
    monkeypatch.delenv("DAY19_MCP_SERVER_URL", raising=False)
    monkeypatch.delenv("DAY19_MCP_TOKEN", raising=False)
    from app.main import app as main
    with TestClient(main) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/api/v1/mcp-orchestration/run", json={"prompt": "task"}).json()["invocation"] == "not_sent"
        assert "/api/v1/mcp-composition/run" in client.get("/openapi.json").json()["paths"]
