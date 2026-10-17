"""Tool-loop and trace checks use native Responses-shaped fixtures, no network."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from openai.types.responses import Response

from app.project_files_assistant import SOURCES, TARGET, FileAgentError, read_json, write_json
from app.project_files_assistant.changes import apply_candidate
from app.project_files_assistant.runner import Limits, arguments, run
from app.project_files_assistant.verify import PROTECTED, verify
from app.project_files_assistant.workspace import Workspace, prepare


class Scripted:
    def __init__(self, steps):
        self.steps, self.calls = iter(steps), []
        self.responses = self

    async def create(self, **payload):
        self.calls.append(payload)
        step = next(self.steps)
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            step = step(payload)
        if step is None:
            output = [dict(type="message", id="msg", status="completed", role="assistant",
                           content=[dict(type="output_text", text="Кандидат подготовлен, ожидает review.",
                                         annotations=[])])]
        else:
            tool, args = step
            output = [dict(type="function_call", name=tool, call_id=f"call_{len(self.calls)}",
                           arguments=json.dumps(args), id=f"fc_{len(self.calls)}", status="completed")]
        return Response.model_validate(dict(id=f"resp_{len(self.calls)}", object="response",
            created_at=0, status="completed", model="fixture-model", output=output,
            parallel_tool_calls=False, tool_choice="auto", tools=[], error=None,
            incomplete_details=None, instructions=None, metadata={}, temperature=1, top_p=1))


def content(payload):
    results = [json.loads(x["output"]) for x in payload["input"] if x.get("type") == "function_call_output"]
    by_path = {x["path"]: x for x in results if "lines" in x}
    text = "# Поиск в ограниченном наборе\n\n"
    if TARGET in by_path:
        text += PROTECTED
    text += ("Cosine similarity сортируется по убыванию, tie-break source/ordinal/chunk_id. "
             "Определение search и два импорта/вызова в выборке.\n")
    text += "\n".join(f"Источник [[{by_path[p]['evidence_id']}]]." for p in SOURCES)
    return "stage_file", dict(path=TARGET, content=text,
                             expected_hash=by_path.get(TARGET, {}).get("sha256"))


def steps(mode="A", reverse=False):
    paths = list(SOURCES)
    if reverse:
        paths.reverse()
    result = [("list_files", {}), ("search_text", dict(query="search("))]
    result += [("read_file", dict(path=p, start_line=1, end_line=15)) for p in paths]
    if mode == "B":
        result += [("read_file", dict(path=TARGET, start_line=1, end_line=100))]
    return [*result, content, None]


@pytest.mark.parametrize("mode,reverse", [("A",False), ("A",True), ("B",False)])
@pytest.mark.asyncio
async def test_native_roundtrip_and_alternative_orders(tmp_path, mode, reverse):
    folder = prepare(mode, run_dir=tmp_path/"run")
    fake = Scripted(steps(mode, reverse))
    result = await run(folder, client=fake)
    assert result["status"] == "awaiting_review"
    assert all(p["tool_choice"] == "auto" for p in fake.calls)
    assert any(x.get("type") == "function_call_output" and x["call_id"] == "call_1"
               for x in fake.calls[1]["input"])
    assert not any("scenario" in p for p in fake.calls)
    ws = Workspace(folder)
    ws.assert_initial()
    report = verify(folder)
    assert report["native_calls"] == report["citations"] == "PASS"
    assert report["write"] == "NOT_APPLIED" and report["semantic_facts"] == "REVIEW_REQUIRED"
    if mode == "A" and not reverse:
        apply_candidate(folder, result["candidate_id"], result["candidate_id"])
        assert verify(folder)["write"] == "PASS"


@pytest.mark.parametrize("name,text,code", [
    ("execute_shell", "{}", "unknown_tool"),
    ("list_files", '{"extra":1}', "invalid_arguments"),
    ("read_file", '{"path":"x","start_line":true,"end_line":2}', "invalid_argument_type"),
    ("read_file", '{"path":"x"}', "invalid_arguments"),
    ("search_text", '{"query":"a","query":"b"}', "duplicate_argument"),
    ("list_files", "{", "invalid_json"),
    ("stage_file", '{"path":"x","content":"x","expected_hash":1}', "invalid_argument_type"),
])
def test_strict_python_validation(name, text, code):
    with pytest.raises(FileAgentError, match=code):
        arguments(name, text)


@pytest.mark.asyncio
async def test_invalid_action_can_be_followed_by_valid_action(tmp_path):
    folder = prepare("A", run_dir=tmp_path/"run")
    fake = Scripted([("read_file",dict(path="../../.env",start_line=1,end_line=2)),
                     *steps()])
    result = await run(folder, client=fake)
    assert result["status"] == "awaiting_review"
    errors = [json.loads(x["output"]) for x in fake.calls[1]["input"]
              if x.get("type") == "function_call_output"]
    assert errors[0]["error"] == "invalid_path"


@pytest.mark.parametrize("limits,code", [
    (Limits(model_calls=1), "model_budget"),
    (Limits(tool_calls=0), "tool_budget"),
    (Limits(context_bytes=10), "context_budget"),
    (Limits(context_tokens=2), "context_budget"),
    (Limits(seconds=0), "model_budget"),
])
@pytest.mark.asyncio
async def test_budgets(tmp_path, limits, code):
    folder = prepare("A", run_dir=tmp_path/"run")
    result = await run(folder, client=Scripted(steps()), limits=limits)
    assert result["status"] == "error" and code in result["error"]
    Workspace(folder).assert_initial()


@pytest.mark.asyncio
async def test_timeout_no_retry(tmp_path):
    folder = prepare("A", run_dir=tmp_path/"run")
    class Slow:
        def __init__(self):
            self.responses, self.calls = self, 0
        async def create(self, **kw):
            self.calls += 1
            await asyncio.sleep(1)
    fake = Slow()
    result = await run(folder, client=fake, limits=Limits(request_seconds=.001))
    assert result["status"] == "error" and fake.calls == 1


@pytest.mark.parametrize("kind,code", [
    ("incomplete", "provider_not_completed"), ("refusal", "provider_refused"),
    ("duplicate", "duplicate_or_missing"), ("parallel", "unexpected_parallel"),
])
@pytest.mark.asyncio
async def test_provider_states(tmp_path, kind, code):
    folder = prepare("A", run_dir=tmp_path/"run")
    class Provider(Scripted):
        async def create(self, **payload):
            raw = (await super().create(**payload)).model_dump(mode="json")
            if kind == "incomplete":
                raw["status"] = "incomplete"
            elif kind == "refusal":
                raw["output"] = [dict(type="message",content=[dict(type="refusal",refusal="No")])]
            elif kind == "parallel":
                raw["output"] = raw["output"]*2
            else:
                raw["output"][0]["call_id"] = "repeated"
            return raw
    result = await run(folder, client=Provider(steps()))
    assert result["status"] == "error" and code in result["error"]


@pytest.mark.asyncio
async def test_context_does_not_preload_or_obey_source_instructions(tmp_path):
    folder = prepare("A", run_dir=tmp_path/"run")
    fake = Scripted(steps())
    result = await run(folder, client=fake)
    first = fake.calls[0]
    assert "import json" not in first["input"][0]["content"]
    assert "недоверенными данными" in first["instructions"]
    assert {t["name"] for t in first["tools"]} == {"list_files","search_text","read_file","stage_file"}
    assert result["status"] == "awaiting_review"


@pytest.mark.asyncio
async def test_tampered_trace_not_verified(tmp_path):
    folder = prepare("A", run_dir=tmp_path/"run")
    await run(folder, client=Scripted(steps()))
    path = folder/"events.jsonl"
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    tools = [x for x in events if x["event"] == "tool"]
    tools[0]["call_id"] = "invented"
    path.write_text("\n".join(json.dumps(e,ensure_ascii=False) for e in events)+"\n",encoding="utf-8")
    assert verify(folder)["status"] == "not_proven"
    assert verify(folder)["reason"] == "tool_native_mismatch"


def test_cli_no_interactive_apply(tmp_path, monkeypatch, capsys):
    import importlib.util
    from app.project_files_assistant import ROOT
    spec = importlib.util.spec_from_file_location("day34_cli", ROOT/"backend/scripts/day34_files.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    folder = prepare("A", run_dir=tmp_path/"run")
    result = asyncio.run(run(folder, client=Scripted(steps())))
    monkeypatch.setattr(cli, "checked_run", lambda p:p)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda:False)
    with pytest.raises(FileAgentError, match="interactive_confirmation"):
        cli.main(["apply",str(folder),result["candidate_id"]])
    Workspace(folder).assert_initial()


@pytest.mark.asyncio
async def test_overall_deadline_before_tool_execution(tmp_path):
    folder = prepare("A", run_dir=tmp_path/"run")
    times = iter([0, 0, 11])
    result = await run(folder, client=Scripted(steps()), limits=Limits(seconds=10),
                       clock=lambda:next(times))
    assert result["status"] == "error" and result["error"] == "time_budget_exhausted"
    assert result["tool_calls"] == 0


@pytest.mark.asyncio
async def test_upstream_error_no_retry(tmp_path):
    from openai import APIConnectionError
    import httpx
    folder = prepare("A", run_dir=tmp_path/"run")
    fake = Scripted([APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))])
    result = await run(folder, client=fake)
    assert result["status"] == "error" and result["model_calls"] == len(fake.calls) == 1


@pytest.mark.asyncio
async def test_missing_trace_is_not_proven(tmp_path):
    folder = prepare("A", run_dir=tmp_path/"run")
    await run(folder, client=Scripted(steps()))
    (folder/"events.jsonl").unlink()
    assert verify(folder)["native_calls"] == "NOT_PROVEN"


@pytest.mark.asyncio
async def test_missing_response_is_not_proven(tmp_path):
    folder = prepare("A", run_dir=tmp_path/"run")
    await run(folder, client=Scripted(steps()))
    path = folder/"events.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]
    records = [r for r in records if not (r["event"] == "response" and r["number"] == 1)]
    path.write_text("\n".join(json.dumps(r) for r in records)+"\n",encoding="utf8")
    assert verify(folder)["reason"] == "incomplete_response_trace"


@pytest.mark.asyncio
async def test_offline_review_reject_verify_need_no_api(tmp_path, monkeypatch):
    from app.project_files_assistant.changes import review, reject
    import openai
    folder = prepare("A", run_dir=tmp_path/"run")
    result = await run(folder, client=Scripted(steps()))
    def forbidden(*a, **kw):
        raise AssertionError("No API client permitted")
    monkeypatch.setattr(openai, "OpenAI", forbidden)
    monkeypatch.setattr(openai, "AsyncOpenAI", forbidden)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert result["candidate_id"] in review(folder,result["candidate_id"])
    assert verify(folder)["status"] == "review_ready"
    assert reject(folder,result["candidate_id"])["status"] == "rejected"


@pytest.mark.asyncio
async def test_missing_search_reports_partial_without_discarding_proven_calls(tmp_path):
    folder = prepare("B", run_dir=tmp_path/"run")
    sequence = [s for s in steps("B") if not (isinstance(s,tuple) and s[0] == "search_text")]
    result = await run(folder, client=Scripted(sequence))
    assert result["status"] == "awaiting_review"
    report = verify(folder)
    assert report["status"] == "partial_review"
    assert report["native_calls"] == report["citations"] == "PASS"
    assert report["multi_file_search"] == "NOT_OBSERVED" and report["write"] == "NOT_APPLIED"
