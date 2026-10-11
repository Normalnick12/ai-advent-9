import json
from pathlib import Path
import subprocess
import sys
import time

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import driver as d
import experiment as e
import scenarios as s
import grounded_explain as g
import rag_cli
from generation_settings import settings
from ollama_client import make_client, local_url
from workspace import Source


def mock_api(calls, *, missing=False, remote=False, version="0.40.2", params='stop "END"', digest="a" * 64,
             reason="stop", failure=None):
    def handle(req):
        body = json.loads(req.content) if req.content else {}
        calls.append((req.url.path, body))
        path = req.url.path
        if failure == path:
            raise httpx.ReadTimeout("PRIVATE_CODE PRIVATE_QUESTION PRIVATE_PATH", request=req)
        if path == "/api/version":
            return httpx.Response(200, json={"version": version})
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [] if missing else [{"name": m, "digest": digest} for m in (*s.CANDIDATES, "embed:latest")]})
        if path == "/api/show":
            if body["model"] == "embed":
                return httpx.Response(200, json={"capabilities": ["embedding"], "model_info": {"test.embedding_length": 2}})
            return httpx.Response(200, json={"capabilities": ["completion"] + (["thinking"] if body["model"] == s.CANDIDATES[0] else []),
                "details": {"quantization_level": "Q4_K_M"}, "template": "NATIVE_TEMPLATE_PRIVATE",
                "parameters": params, "remote_host": "https://example.invalid" if remote else ""})
        if path == "/api/ps":
            return httpx.Response(200, json={"models": [{"name": m, "digest": digest, "context_length": 8192,
                                                         "size": 500, "size_vram": 400} for m in s.CANDIDATES]})
        if path == "/api/generate":
            assert "prompt" not in body
            return httpx.Response(200, json={"done": True, "done_reason": "load"})
        if path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[1., 0.]] * len(body["input"])})
        assert path == "/api/chat", "unexpected inference endpoint"
        context = json.loads(body["messages"][1]["content"])
        answer = {"code_observations": [{"id": "C1", "text": "PRIVATE_ANSWER", "lines": [1]}],
            "documented_rules": [], "applications": [], "assumptions": [], "limitations": ["insufficient"],
            "knowledge_status": context["knowledge_status"]}
        return httpx.Response(200, json={"done": True, "done_reason": reason,
            "message": {"content": json.dumps(answer), "thinking": "PRIVATE_REASONING"}, "eval_duration": 2_000_000_000})
    return httpx.MockTransport(handle)


@pytest.fixture(autouse=True)
def no_resource_commands(monkeypatch):
    monkeypatch.setattr(d, "memory_snapshot", lambda: {"method": "mock_snapshot_not_peak"})


def test_frozen_inputs_equal_and_do_not_leak_rubric():
    s.verify_manifest()
    for sid in d.SCENARIOS:
        payloads = []
        for model in s.CANDIDATES:
            source, selected, _, raw = d.packet(sid, model, e.BASELINE, e.SAMPLING, model == s.CANDIDATES[0])
            p = json.loads(raw)
            assert len(selected) == len(s.scenario(sid)[2])
            assert p["keep_alive"] == "5m"
            assert "K1–K6" not in str(p) and "semantic verdict" not in str(p)
            p.pop("model"); p.pop("think", None)
            payloads.append(p)
        assert payloads[0] == payloads[1]


@pytest.mark.parametrize("temperature,keep", [(float("nan"), 0), (float("inf"), 0), (-1, 0), (3, 0), (True, 0), (0, -1), (0, "1h"), (0, True)])
def test_invalid_settings(temperature, keep):
    with pytest.raises(ValueError):
        settings(temperature, keep)


def test_defaults_compatible_and_override_bounds():
    source = Source("A.kt", "class A")
    original, _ = g.pack(source, "Explain", "gen", "none", [])
    explicit, _ = g.pack(source, "Explain", "gen", "none", [], overrides=settings())
    assert original == explicit
    changed, _ = g.pack(source, "Explain", "gen", "none", [], overrides=settings(.2, "5m"), thinking=False)
    p = json.loads(changed)
    assert p["options"]["temperature"] == .2 and p["keep_alive"] == "5m" and "think" not in p


@pytest.mark.parametrize("kw", [{"missing": True}, {"remote": True}, {"version": "0.40.3"}, {"params": "unknown 42"}, {"params": "temperature NaN"}])
def test_metadata_fail_closed(kw):
    calls = []
    with make_client(mock_api(calls, **kw)) as client, pytest.raises(RuntimeError):
        e.profile(client, d.BASE, s.CANDIDATES[0], e.BASELINE)
    assert not any(path in ("/api/chat", "/api/generate", "/api/pull") for path, _ in calls)


def test_profile_inheritance_digest_and_thinking():
    with make_client(mock_api([], params='top_p 0.8\nstop "END"\nnum_batch 256')) as client:
        profile, explicit = e.profile(client, d.BASE, s.CANDIDATES[0], e.BASELINE)
        assert profile["options"]["top_p"] == .95 and profile["provenance"]["top_p"] == "explicit"
        assert profile["options"]["num_batch"] == 256 and profile["provenance"]["num_batch"] == "model"
        assert profile["think"] is False and explicit["seed"] == 28
        assert "NATIVE_TEMPLATE_PRIVATE" not in json.dumps(profile)
        with pytest.raises(RuntimeError):
            e.profile(client, d.BASE, s.CANDIDATES[0], e.BASELINE, "b" * 64)
        coder, _ = e.profile(client, d.BASE, s.CANDIDATES[1], e.BASELINE)
        assert coder["think"] == "not_supported"
        with pytest.raises(ValueError):
            e.profile(client, d.BASE, "qwen3.5:9b-q4_K_M", e.BASELINE)


def test_one_factor_and_no_byte_token_equivalence():
    child = e.configuration(e.BASELINE, "temperature", .2)
    assert e.delta(e.BASELINE, child)["delta"] == {"temperature": .2}
    with pytest.raises(ValueError):
        e.delta(e.BASELINE, {**child, "num_predict": 1024})
    with pytest.raises(ValueError, match="Token fit"):
        e.configuration(e.BASELINE, "num_ctx", 4096)


@pytest.mark.parametrize("reason,failure,status", [("stop", None, "completed"), ("length", None, "error"), ("stop", "/api/chat", "error")])
def test_worker_frozen_privacy_metrics(reason, failure, status):
    calls = []
    result = d.run_worker({"model": s.CANDIDATES[0], "config": e.BASELINE, "operation": "chat", "scenario": "S6"},
                          mock_api(calls, reason=reason, failure=failure))
    metrics = result["metrics"]
    assert metrics["status"] == status and metrics["embedding_calls"] == 0
    assert metrics["ttft_seconds"] == "unavailable"
    assert "generation_seconds" in metrics and "user_request_seconds" in metrics
    if failure is None:
        assert metrics["eval_duration_seconds"] == 2
        assert metrics["load_duration_seconds"] == "unavailable"
        assert metrics["server_cleanup"] == "response_completed"
    else:
        assert metrics["server_cleanup"] == "unknown"
    serialized = json.dumps(metrics)
    for sentinel in ("PRIVATE_ANSWER", "PRIVATE_CODE", "PRIVATE_REASONING", "PRIVATE_PATH", "PRIVATE_QUESTION", "NATIVE_TEMPLATE_PRIVATE"):
        assert sentinel not in serialized
    assert not any(p in ("/api/embed", "/api/pull") for p, _ in calls)


def test_gate_reuses_s1_and_closes_branch_on_failure():
    calls = []
    def run(job):
        calls.append(job)
        if job["operation"] == "metadata":
            return {"status": "completed", "profile": {"digest": "a" * 64, "profile_sha256": "p"}}
        return {"status": "error" if job["model"] == s.CANDIDATES[0] and job.get("scenario") == "S1" else "completed",
                "server_cleanup": "response_completed"}
    summary = d.suite(s.CANDIDATES, e.BASELINE, run=run)
    assert summary[s.CANDIDATES[0]]["S2"] == "NOT RUN"
    assert len([j for j in calls if j["model"] == s.CANDIDATES[1] and j["operation"] == "chat"]) == 6
    assert len([j for j in calls if j.get("scenario") == "S1"]) == 2


def test_deadline_kills_and_reaps_real_owned_child():
    children = []
    def spawn(*a, **kw):
        child = subprocess.Popen(*a, **kw)
        children.append(child)
        return child
    start = time.monotonic()
    result = d.bounded([sys.executable, "-B", "-c", "import time; time.sleep(30)"], {}, .15, spawn=spawn)
    assert time.monotonic() - start < 5
    assert result["metrics"] == {"status": "deadline", "client_reaped": True, "server_cleanup": "unknown"}
    assert children[0].poll() is not None


def test_journal_keeps_failure_and_blocks_unknown_cleanup(tmp_path, capsys):
    path = tmp_path / "records.jsonl"
    job = {"model": s.CANDIDATES[0], "config": e.BASELINE, "operation": "chat", "scenario": "S1"}
    def failed(*args):
        return {"metrics": {"status": "deadline", "server_cleanup": "unknown", "answer": "PRIVATE_ANSWER"}, "rendered": "PRIVATE_ANSWER"}
    d.execute(job, path, failed)
    records, calls, _, blocked = d.history(path)
    assert len(records) == 2 and calls == 1 and blocked
    assert "PRIVATE_ANSWER" not in path.read_text()
    output = capsys.readouterr()
    assert "PRIVATE_ANSWER" in output.out and "PRIVATE_ANSWER" not in output.err
    with pytest.raises(RuntimeError):
        d.execute(job, path, lambda *a: pytest.fail("retry"))


@pytest.mark.parametrize("mode", ["incomplete", "calls", "time"])
def test_budget_and_interruption_gates(tmp_path, mode):
    path = tmp_path / "records.jsonl"
    records = []
    for n in range(32 if mode == "calls" else 1):
        records.append({"event": "start", "attempt": str(n), "operation": "chat"})
        if mode != "incomplete":
            records.append({"event": "end", "attempt": str(n), "client_wall_seconds": 5400 if mode == "time" else 1,
                            "metrics": {"server_cleanup": "response_completed"}})
    path.write_text("\n".join(json.dumps(r) for r in records))
    with pytest.raises(RuntimeError):
        d.execute({"model": s.CANDIDATES[0], "config": e.BASELINE, "operation": "chat"}, path, lambda *a: pytest.fail("gate"))


def test_unknown_residence_and_counter_units():
    with make_client(mock_api([], failure="/api/ps")) as client:
        assert e.residence(client, d.BASE, s.CANDIDATES[0]) == {"resident": "unavailable"}
    m = e.provider_metrics({"total_duration": 3_000_000_000, "load_duration": -1, "eval_count": True})
    assert m["total_duration_seconds"] == 3 and m["load_duration_seconds"] == "unavailable" and m["eval_count"] == "unavailable"
    with pytest.raises(ValueError):
        local_url("https://remote.example")


def test_preview_is_offline(monkeypatch, capsys):
    monkeypatch.setattr(d, "execute", lambda *a: pytest.fail("live"))
    assert d.main([]) == 0
    assert json.loads(capsys.readouterr().out)["live"] == "NOT RUN"
    with pytest.raises(SystemExit):
        d.main(["--stage", "quality"])


def test_real_rag_path_reuses_index_embedding_and_retrieval(tmp_path, monkeypatch):
    root = tmp_path / "knowledge"
    root.mkdir()
    for name, source in (("checkout.md", s.OLD / "knowledge/checkout.md"),
                         ("compose.md", s.HERE / "fixtures/knowledge/compose.md")):
        (root / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    calls = []
    transport = mock_api(calls)
    assert rag_cli.main(["knowledge", "index", "--knowledge", str(root), "--embedding-model", "embed", "--yes"], transport=transport) == 0
    calls.clear()
    monkeypatch.setattr(d, "RAG_ROOT", root)
    result = d.run_worker({"model": s.CANDIDATES[0], "config": e.BASELINE, "operation": "rag", "scenario": "S6"}, transport)
    assert result["metrics"]["status"] == "completed"
    paths = [path for path, _ in calls]
    assert paths.count("/api/embed") == 1 and paths.count("/api/chat") == 1
    assert paths.index("/api/embed") < paths.index("/api/chat")
    assert result["metrics"]["embedding_calls"] == 1
    assert result["metrics"]["retrieval_seconds"] > 0 and result["metrics"]["index_sha256"]
    (root / "private.md").write_text("PRIVATE_DOCUMENT", encoding="utf-8")
    calls.clear()
    failed = d.run_worker({"model": s.CANDIDATES[0], "config": e.BASELINE, "operation": "rag", "scenario": "S6"}, transport)
    assert failed["metrics"]["status"] == "error"
    assert not any(path in ("/api/embed", "/api/chat") for path, _ in calls)
    assert "PRIVATE_DOCUMENT" not in json.dumps(failed)


def test_cli_override_and_invalid_value_before_http(tmp_path, capsys):
    (tmp_path / "A.kt").write_text("class A")
    args = ["explain", "--workspace", str(tmp_path), "--file", "A.kt", "--question", "Explain",
            "--retrieval", "none", "--model", s.CANDIDATES[0]]
    calls = []
    assert rag_cli.main(args + ["--temperature", "nan"], transport=mock_api(calls)) == 2
    assert not calls
    assert rag_cli.main(args + ["--temperature", "0.2", "--keep-alive", "5m"], transport=mock_api(calls)) == 0
    request = next(body for path, body in calls if path == "/api/chat")
    assert request["keep_alive"] == "5m" and request["options"]["temperature"] == .2


def test_unknown_cleanup_stops_entire_suite():
    calls = []
    def run(job):
        calls.append(job)
        if job["operation"] == "metadata":
            return {"status": "completed", "profile": {"digest": "a" * 64, "profile_sha256": "p"}}
        return {"status": "deadline", "server_cleanup": "unknown"}
    result = d.suite(s.CANDIDATES, e.BASELINE, run=run)
    assert len(calls) == 2
    assert all(value == "NOT RUN" for rows in result.values() for value in rows.values())


def test_memory_unavailable_is_not_peak(monkeypatch):
    def unavailable(*a, **kw):
        raise FileNotFoundError
    monkeypatch.setattr(e.subprocess, "run", unavailable)
    snapshot = e.memory_snapshot()
    assert snapshot["system_gpu_used_mib"] == "unavailable"
    assert snapshot["runner_rss_bytes"] == "unavailable"
    assert snapshot["method"] == "before_after_snapshot_not_peak"


def test_existing_failed_branch_cannot_be_retried(tmp_path):
    path = tmp_path / "records.jsonl"
    job = {"model": s.CANDIDATES[0], "config": e.BASELINE, "operation": "chat", "scenario": "S1"}
    d.execute(job, path, lambda *a: {"metrics": {"status": "error", "server_cleanup": "response_completed"}, "rendered": ""})
    assert not d.history(path)[3]  # Runner finished, but this configuration still failed.
    with pytest.raises(RuntimeError, match="configuration is closed"):
        d.execute({**job, "scenario": "S2"}, path, lambda *a: pytest.fail("retry"))


def test_candidate_selection_requires_all_six_same_identity():
    rows = [{"event": "end", "model": s.CANDIDATES[0], "operation": "chat", "config": e.BASELINE,
             "scenario": sid, "manifest_sha256": s.fingerprint(s.manifest()),
             "metrics": {"status": "completed", "profile": {"digest": "a" * 64, "profile_sha256": "p"}}} for sid in d.SCENARIOS]
    assert d.reviewed_baseline(rows, s.CANDIDATES[0])["digest"] == "a" * 64
    with pytest.raises(ValueError):
        d.reviewed_baseline(rows[:-1], s.CANDIDATES[0])
    rows[-1]["metrics"]["profile"]["digest"] = "b" * 64
    with pytest.raises(ValueError, match="Mixed baseline"):
        d.reviewed_baseline(rows, s.CANDIDATES[0])


def test_keyboard_cancel_reaps_owned_client():
    class Child:
        killed = False
        def communicate(self, *a, **kw):
            if not self.killed:
                raise KeyboardInterrupt
            return "", ""
        def kill(self): self.killed = True
        def poll(self): return 1 if self.killed else None
    child = Child()
    result = d.bounded([], {}, 1, spawn=lambda *a, **kw: child)
    assert result["metrics"]["status"] == "cancelled" and result["metrics"]["client_reaped"]


def test_both_failed_admissions_propose_diagnostics_without_more_calls(capsys):
    calls = []
    def run(job):
        calls.append(job)
        if job["operation"] == "metadata":
            return {"status": "completed", "profile": {"digest": "a" * 64, "profile_sha256": "p"}}
        return {"status": "error", "server_cleanup": "response_completed", "failed_phase": "admission"}
    result = d.suite(s.CANDIDATES, e.BASELINE, run=run)
    assert len(calls) == 4 and all(j["operation"] in ("metadata", "load") for j in calls)
    assert "both_admissions_failed" in capsys.readouterr().err
    assert all(v == "NOT RUN" for values in result.values() for v in values.values())


@pytest.mark.parametrize("sid", ["S4", "S6"])
def test_prompt_correction_changes_only_system_message(sid):
    original_prompt = g.INSTRUCTIONS
    original_schema = json.dumps(g.SCHEMA, sort_keys=True)
    args = (sid, s.CANDIDATES[1], e.BASELINE, e.SAMPLING, False)
    baseline = json.loads(d.packet(*args)[3])
    variant = json.loads(d.packet(*args, prompt_variant=d.PROMPT_VARIANT)[3])
    corrected = variant["messages"][0]["content"]
    identity = d.prompt_identity(d.PROMPT_VARIANT)
    assert identity["prompt_sha256"] == s.fingerprint(corrected)
    assert identity["parent_manifest_sha256"] == s.fingerprint(s.manifest())
    assert identity["schema_sha256"] == s.fingerprint(g.SCHEMA)
    assert identity["prompt_sha256"] != identity["parent_prompt_sha256"]
    assert not any(hint in d.PROMPT_CORRECTION for hint in ("S4", "S6", "RPO", "RTO", "LaunchedEffect", "StateFlow"))
    variant["messages"][0]["content"] = baseline["messages"][0]["content"]
    assert variant == baseline  # Includes exact question, code, chunks/order, schema and sampler.
    assert g.INSTRUCTIONS == original_prompt and json.dumps(g.SCHEMA, sort_keys=True) == original_schema
    s.verify_manifest()


@pytest.mark.parametrize("sid", ["S4", "S6"])
def test_corrected_worker_uses_same_validation_and_safe_metrics(sid):
    calls = []
    job = {"model": s.CANDIDATES[1], "config": e.BASELINE, "operation": "chat",
           "scenario": sid, "prompt_variant": d.PROMPT_VARIANT}
    result = d.run_worker(job, mock_api(calls))
    assert result["metrics"]["status"] == "completed"
    assert result["metrics"]["prompt_correction"] == d.prompt_manifest()
    sent = next(body for path, body in calls if path == "/api/chat")
    assert sent["messages"][0]["content"] == g.INSTRUCTIONS + "\n\n" + d.PROMPT_CORRECTION
    assert "PRIVATE_ANSWER" not in json.dumps(result["metrics"])
    assert [p for p, _ in calls if p in ("/api/chat", "/api/generate", "/api/embed")] == ["/api/chat"]
    failed = d.run_worker(job, mock_api([], reason="length"))
    assert failed["metrics"]["status"] == "error" and failed["metrics"]["failed_phase"] == "validation"


@pytest.mark.parametrize("change", [{"scenario": "S2"}, {"model": s.CANDIDATES[0]},
    {"operation": "rag"}, {"config": {**e.BASELINE, "temperature": .2}}, {"prompt_variant": "unreviewed"}])
def test_prompt_correction_rejects_unapproved_work_before_http(change):
    calls = []
    job = {"model": s.CANDIDATES[1], "config": e.BASELINE, "operation": "chat",
           "scenario": "S4", "prompt_variant": d.PROMPT_VARIANT, **change}
    assert d.run_worker(job, mock_api(calls))["metrics"]["status"] == "error"
    assert not calls


def test_prompt_correction_rejects_unpinned_revision(monkeypatch):
    monkeypatch.setattr(d, "PROMPT_CORRECTION", d.PROMPT_CORRECTION + "changed")
    with pytest.raises(ValueError, match="changed"):
        d.prompt_identity(d.PROMPT_VARIANT)


@pytest.mark.parametrize("status", ["completed", "error"])
def test_prompt_correction_order_no_retry_and_journal_identity(tmp_path, status):
    path = tmp_path / "correction.jsonl"
    job = {"model": s.CANDIDATES[1], "config": e.BASELINE, "operation": "chat",
           "scenario": "S4", "prompt_variant": d.PROMPT_VARIANT}
    def run(*args):
        return {"metrics": {"status": status, "server_cleanup": "response_completed"}, "rendered": ""}
    with pytest.raises(RuntimeError, match="S4 must complete"):
        d.execute({**job, "scenario": "S6"}, path, run)
    d.execute(job, path, run)
    if status == "completed":
        d.execute({**job, "scenario": "S6"}, path, run)
    else:
        with pytest.raises(RuntimeError):
            d.execute({**job, "scenario": "S6"}, path, run)
    with pytest.raises(RuntimeError):
        d.execute(job, path, run)
    rows = d.history(path)[0]
    assert all(r["prompt_correction"] == d.prompt_manifest() for r in rows)
    assert d.PROMPT_CORRECTION not in path.read_text(encoding="utf-8")


def test_correction_cannot_be_mixed_into_baseline_or_candidate(tmp_path):
    path = tmp_path / "baseline.jsonl"
    job = {"model": s.CANDIDATES[1], "config": e.BASELINE, "operation": "chat", "scenario": "S4"}
    d.execute(job, path, lambda *a: {"metrics": {"status": "completed", "server_cleanup": "response_completed"}, "rendered": ""})
    with pytest.raises(RuntimeError, match="separate correction journal"):
        d.execute({**job, "prompt_variant": d.PROMPT_VARIANT}, path)
    rows = [{"event": "end", "model": s.CANDIDATES[1], "operation": "chat", "config": e.BASELINE,
             "scenario": sid, "manifest_sha256": s.fingerprint(s.manifest()),
             "metrics": {"status": "completed", "profile": {"digest": "a" * 64, "profile_sha256": "p"}}} for sid in d.SCENARIOS]
    rows[-1]["prompt_correction"] = d.prompt_manifest()
    with pytest.raises(ValueError, match="Six completed baseline"):
        d.reviewed_baseline(rows, s.CANDIDATES[1])
