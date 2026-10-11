import builtins
import io
import json
from pathlib import Path

import httpx
import pytest

import assistant


def arguments(root):
    return ["--workspace", str(root), "--file", "A.kt", "--question", "Роль?", "--model", "test"]


def output():
    return {"facts": [{"text": "Класс A", "lines": [1]}], "assumptions": [], "limitations": ["Один файл"]}


@pytest.mark.parametrize("thinking", [True, False])
def test_whole_cli_two_http_one_inference_no_writes(tmp_path, capsys, monkeypatch, thinking):
    (tmp_path / "A.kt").write_text("class A", encoding="utf-8")
    (tmp_path / "Other.kt").write_text("DO_NOT_READ", encoding="utf-8")
    calls = []
    def handle(request):
        calls.append(request.url.path)
        data = json.loads(request.content)
        assert "DO_NOT_READ" not in request.content.decode()
        assert str(tmp_path) not in request.content.decode()
        if request.url.path == "/api/show":
            assert data == {"model": "test"}
            return httpx.Response(200, json={"capabilities": ["completion"] + (["thinking"] if thinking else [])})
        assert data.get("think") is False if thinking else "think" not in data
        return httpx.Response(200, json={"done": True, "done_reason": "stop",
            "message": {"content": json.dumps(output())}, "prompt_eval_count": 123, "eval_count": 45})
    original_open = builtins.open
    original_path_open = Path.open
    def checked_open(file, mode="r", *a, **k):
        assert not any(flag in mode for flag in "wax+")
        return original_open(file, mode, *a, **k)
    def checked_path_open(file, mode="r", *a, **k):
        assert not any(flag in mode for flag in "wax+")
        assert file.name != "Other.kt"
        return original_path_open(file, mode, *a, **k)
    monkeypatch.setattr(builtins, "open", checked_open)
    monkeypatch.setattr(Path, "open", checked_path_open)
    assert assistant.main(arguments(tmp_path), transport=httpx.MockTransport(handle)) == 0
    out = capsys.readouterr()
    assert "Класс A" in out.out and "строки 1" in out.out
    metrics = json.loads(out.err)
    assert metrics["status"] == "completed" and metrics["prompt_eval_count"] == 123
    assert metrics["total_duration"] == "unavailable"
    assert calls == ["/api/show", "/api/chat"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["A.kt", "Other.kt"]


@pytest.mark.parametrize("bad", ["../A.kt", "/A.kt", "C:A.kt"])
def test_rejected_path_no_http(tmp_path, bad):
    args = arguments(tmp_path)
    args[3] = bad
    assert assistant.main(args, transport=httpx.MockTransport(lambda r: pytest.fail("HTTP"))) == 2


def test_oversized_full_prompt_no_metadata_http(tmp_path):
    (tmp_path / "A.kt").write_text("x\n"*8000, encoding="utf-8")
    assert assistant.main(arguments(tmp_path), transport=httpx.MockTransport(lambda r: pytest.fail("HTTP"))) == 2


@pytest.mark.parametrize("mode", ["question", "empty", "eof", "cancel", "non-tty"])
def test_terminal_input(tmp_path, monkeypatch, mode):
    (tmp_path / "A.kt").write_text("class A", encoding="utf-8")
    class Terminal(io.StringIO):
        def isatty(self):
            return mode != "non-tty"
    monkeypatch.setattr(assistant.sys, "stdin", Terminal())
    def ask():
        if mode == "eof":
            raise EOFError
        if mode == "cancel":
            raise KeyboardInterrupt
        return "Роль?" if mode == "question" else " "
    monkeypatch.setattr(builtins, "input", ask)
    args = arguments(tmp_path)
    del args[4:6]
    calls = []
    def handle(request):
        calls.append(request.url.path)
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"]})
        return httpx.Response(200, json={"done": True,"done_reason": "stop", "message": {"content": json.dumps(output())}})
    assert assistant.main(args, transport=httpx.MockTransport(handle)) == (0 if mode == "question" else 130 if mode == "cancel" else 2)
    assert len(calls) == (2 if mode == "question" else 0)


def test_environment_precedence_and_missing_model(tmp_path, monkeypatch):
    monkeypatch.setenv("LAA_MODEL", "env-model")
    monkeypatch.setenv("LAA_BASE_URL", "http://127.0.0.1:1234")
    p = assistant.parser()
    args = p.parse_args(arguments(tmp_path))
    assert args.model == "test" and args.base_url.endswith(":1234")
    monkeypatch.delenv("LAA_MODEL")
    assert assistant.main(arguments(tmp_path)[:-2]) == 2


@pytest.mark.parametrize("show_error", [True, False])
def test_failure_redacts_content_and_does_not_repeat(tmp_path, capsys, show_error):
    (tmp_path / "A.kt").write_text("class A", encoding="utf-8")
    calls = []
    def handle(request):
        calls.append(request.url.path)
        if request.url.path == "/api/show" and not show_error:
            return httpx.Response(200, json={"capabilities": ["completion"]})
        return httpx.Response(500, content=b"SECRET SOURCE AND QUESTION")
    assert assistant.main(arguments(tmp_path), transport=httpx.MockTransport(handle)) == 1
    text = capsys.readouterr()
    assert not text.out and "SECRET" not in text.err and "Traceback" not in text.err
    assert len(calls) == (1 if show_error else 2)


def test_help_and_argparse_redaction(capsys):
    with pytest.raises(SystemExit) as e:
        assistant.main(["--help"])
    assert e.value.code == 0
    capsys.readouterr()
    assert assistant.main(["--unknown", "SECRET"]) == 2
    assert "SECRET" not in capsys.readouterr().err
